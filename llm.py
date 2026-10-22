"""Draft a reply with any OpenAI-compatible chat API (DeepSeek by default) in JSON mode."""
import json
import os
import urllib.request
from pathlib import Path

API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
KB = "\n\n".join(p.read_text() for p in sorted((Path(__file__).parent / "kb").glob("*.md")))

SYSTEM = """You draft replies for the owner of this account. The owner reviews every draft and decides whether to send it.
Use ONLY the knowledge base below. If it does not contain what is needed, or the question needs a human decision
(money, personal data lookups, anything about a specific person), choose action "skip".
Personal data in the conversation is replaced with ⟦N⟧ keys: copy them verbatim, never invent values.
Reply in the language of the conversation, in the owner's style (see style.md): short and direct.
Answer with JSON: {"action": "answer" | "skip", "reply": "...", "reason": "one short sentence"}

KNOWLEDGE BASE:
""" + KB


def draft(history: list[dict], timeout: int = 60) -> dict:
    """history: [{"from": "them" | "me", "text": "..."}] with PII already redacted."""
    convo = "\n".join(("THEM: " if h["from"] == "them" else "ME: ") + h["text"] for h in history)
    body = {"model": MODEL, "temperature": 0.3, "max_tokens": 600,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": convo + "\n\nDraft the next reply."}]}
    req = urllib.request.Request(API_BASE + "/chat/completions", json.dumps(body).encode(),
                                 {"Authorization": "Bearer " + os.environ["LLM_API_KEY"],
                                  "Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=timeout))
    out = json.loads(res["choices"][0]["message"]["content"])
    if out.get("action") not in ("answer", "skip"):
        out["action"] = "skip"
    return out

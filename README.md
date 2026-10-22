# Reply Copilot

Human-in-the-loop automation for Telegram support-style chats. A userbot watches your private chats, an LLM drafts replies from your knowledge base, and you approve each one with a button in a control bot. **Nothing is sent without your click.**

```
incoming message ─► redact PII ─► LLM draft (knowledge base + style) ─► approval card ─► ✅ send / ✏️ edit / 🚫 reject
```

## Features
- **PII redaction** (emails, phones, cards, long numbers, passwords, invite links) before anything reaches the LLM, with reversible placeholders so the final reply is restored
- **Approval cards** with Send / Edit / Reject; edits are applied on the same card
- **Safety rails:** per-chat lock (no duplicate drafts), global cap on parallel LLM calls, drafts expire (TTL), allowlist of chats, "skip" for anything the knowledge base doesn't cover
- **Audit log:** every decision is appended to `logs/decisions.jsonl`; errors to `logs/errors.jsonl`
- Works with any OpenAI-compatible API (DeepSeek by default)

## Run
```bash
cp .env.example .env   # fill in Telegram API keys, control-bot token, your id, LLM key
pip install -r requirements.txt && python bot.py     # first run asks for the login code
pytest                 # redaction tests
```
Put your FAQ in `kb/knowledge.md` and your tone in `kb/style.md`.

**Stack:** Python, Telethon, asyncio, LLM JSON mode, Docker. Use only on your own account and chats you are entitled to automate.

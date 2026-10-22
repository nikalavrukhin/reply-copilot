"""PII redaction: replace sensitive values with labels before text is sent to an LLM.

With a vault, originals are stored under reversible keys so the final reply can be restored by unmask().
"""
import re

_RULES = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "email"),
    (re.compile(r"(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)"), "card"),
    (re.compile(r"(?<![\w\d])\+?\d[\d\s().-]{8,}\d(?!\d)"), "phone"),
    (re.compile(r"https?://t\.me/(?:\+|joinchat/)\S+"), "invite-link"),
    (re.compile(r"(?i)\b(password|passwd|pwd|пароль)\b(\s*[:=—-]?\s*)\S+"), "password"),
    (re.compile(r"(?i)\b(login|логин)\b(\s*[:=—-]?\s*)\S+"), "login"),
    (re.compile(r"(?<!\d)\d{9,}(?!\d)"), "number"),
]
_KEY = re.compile(r"⟦(\d+)⟧")


def redact(text: str, vault: dict | None = None) -> str:
    for pattern, label in _RULES:
        def repl(m, label=label):
            if vault is not None:
                key = f"⟦{len(vault)}⟧"
                vault[key] = m.group(0)
                return key
            if label in ("password", "login"):
                return f"{m.group(1)}{m.group(2)}[{label}]"
            return f"[{label}]"
        text = pattern.sub(repl, text)
    return text


def unmask(text: str, vault: dict) -> str:
    for _ in range(5):
        new = _KEY.sub(lambda m: vault.get(m.group(0), m.group(0)), text)
        if new == text:
            break
        text = new
    return text

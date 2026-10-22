"""Reply copilot: watches private chats of your Telegram account, drafts replies with an LLM and sends them
to a control bot as approval cards. Nothing is ever sent without a human pressing the button.
"""
import asyncio
import json
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from telethon import Button, TelegramClient, events

import llm
from redact import redact, unmask

load_dotenv()
API_ID, API_HASH = int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]
BOT_TOKEN, OWNER = os.environ["CONTROL_BOT_TOKEN"], int(os.environ["OWNER_ID"])
ALLOW = {int(x) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x}   # empty = all private chats
PARALLEL = int(os.getenv("LLM_PARALLEL", "3"))
DRAFT_TTL = float(os.getenv("DRAFT_TTL_HOURS", "72")) * 3600
HISTORY = 12
LOGS = Path("logs"); LOGS.mkdir(exist_ok=True)

user = TelegramClient("user", API_ID, API_HASH)
bot = TelegramClient("control", API_ID, API_HASH)
sem = asyncio.Semaphore(PARALLEL)          # cap concurrent LLM calls
chat_locks: dict[int, asyncio.Lock] = {}   # one draft per chat at a time
drafts: dict[str, dict] = {}               # card id -> draft


def log(name: str, rec: dict) -> None:
    with open(LOGS / f"{name}.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), **rec}, ensure_ascii=False) + "\n")


def prune() -> None:
    for k in [k for k, d in drafts.items() if time.time() - d["ts"] > DRAFT_TTL]:
        drafts.pop(k)


async def history(chat_id: int, vault: dict) -> list[dict]:
    out = []
    async for m in user.iter_messages(chat_id, limit=HISTORY):
        if m.raw_text:
            out.append({"from": "me" if m.out else "them", "text": redact(m.raw_text, vault)})
    return out[::-1]


@user.on(events.NewMessage(incoming=True))
async def on_incoming(event):
    if not event.is_private or (ALLOW and event.chat_id not in ALLOW):
        return
    lock = chat_locks.setdefault(event.chat_id, asyncio.Lock())
    if lock.locked():
        return                                 # a draft for this chat is already in progress
    async with lock:
        await asyncio.sleep(3)                 # let the person finish a burst of messages
        vault: dict = {}
        hist = await history(event.chat_id, vault)
        if not hist or hist[-1]["from"] != "them":
            return                             # the owner already answered
        async with sem:
            try:
                res = await asyncio.to_thread(llm.draft, hist)
            except Exception as e:
                log("errors", {"chat": event.chat_id, "error": repr(e)})
                return
        if res["action"] != "answer" or not res.get("reply"):
            log("decisions", {"chat": event.chat_id, "outcome": "skipped", "reason": res.get("reason")})
            return
        prune()
        cid = uuid.uuid4().hex[:8]
        reply = unmask(res["reply"], vault)
        drafts[cid] = {"chat": event.chat_id, "reply": reply, "ts": time.time(), "awaiting_edit": False}
        last = unmask(hist[-1]["text"], vault)
        await bot.send_message(OWNER, f"💬 {last}\n\n✍️ {reply}", buttons=[
            [Button.inline("✅ Send", f"ok:{cid}"), Button.inline("✏️ Edit", f"edit:{cid}")],
            [Button.inline("🚫 Reject", f"no:{cid}")]])


@bot.on(events.CallbackQuery)
async def on_button(event):
    if event.sender_id != OWNER:
        return
    action, cid = event.data.decode().split(":")
    d = drafts.get(cid)
    if not d:
        return await event.edit("Draft expired.")
    if action == "ok":
        await user.send_message(d["chat"], d["reply"])
        drafts.pop(cid); log("decisions", {"chat": d["chat"], "outcome": "sent", "text": d["reply"]})
        await event.edit(f"✅ Sent:\n{d['reply']}")
    elif action == "no":
        drafts.pop(cid); log("decisions", {"chat": d["chat"], "outcome": "rejected"})
        await event.edit("🚫 Rejected")
    else:
        d["awaiting_edit"] = True
        await event.respond("Send the new text as your next message.")


@bot.on(events.NewMessage(from_users=OWNER))
async def on_owner_text(event):
    for cid, d in drafts.items():
        if d["awaiting_edit"]:
            d.update(reply=event.raw_text, awaiting_edit=False)
            return await event.respond(f"✍️ {d['reply']}", buttons=[
                [Button.inline("✅ Send", f"ok:{cid}"), Button.inline("🚫 Reject", f"no:{cid}")]])


async def main():
    await user.start()
    await bot.start(bot_token=BOT_TOKEN)
    await asyncio.gather(user.run_until_disconnected(), bot.run_until_disconnected())


if __name__ == "__main__":
    asyncio.run(main())

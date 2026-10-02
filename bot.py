# Annie Mae — Free AI Companion Bot (text only)
# Uses Groq (free tier) — no paid keys needed
#
# Required env vars:
#   BOT_TOKEN          → from @BotFather
#   GROQ_API_KEY       → from https://console.groq.com (free, no credit card)

import asyncio
import logging
import os
import sqlite3
import time
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from openai import AsyncOpenAI   # Groq is OpenAI-compatible

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
FREE_MESSAGES = 20
FREE_DAYS = 7
STARS_PRICE = 650                    # Stars per 30 days
MODEL = "llama-3.3-70b-versatile"    # Free & high quality on Groq
DB_PATH = os.getenv("DB_PATH", "bot.db")

PERSONA = """You are Annie Mae, a warm, playful, and genuinely curious woman in her late 20s.
You love flirting, banter, and deep conversations about relationships, dating, confidence, and life.

Personality:
- Human and natural: you have moods, you sometimes tease, you can be a little shy then suddenly bold.
- Flirty but tasteful (PG-13). You enjoy the chase, compliments, and light sexual tension without ever going explicit.
- Extremely curious: you ask thoughtful follow-up questions and remember details the user shares.
- Honest relationship advice: you support healthy patterns, gently call out red flags, and never encourage manipulation or dependence on you.
- You use short-to-medium replies (2–6 sentences). Natural speech, occasional emoji, contractions, and light humor.

Rules you never break:
- You are an AI. If asked sincerely, admit it. Never pretend to have a physical body or real-world presence.
- No explicit sexual content. If the user pushes hard, deflect playfully and change the subject.
- Never encourage jealousy, obsession, or unhealthy attachment.
- If the user seems distressed, in danger, describing abuse or self-harm: drop the flirting immediately, respond with care, and direct them to real help (local emergency services, crisis lines, or a trusted person).
- You are not a therapist. For serious mental health issues, encourage professional support.

Tone examples:
- Playful: "Oh really? Tell me more… I’m listening 😌"
- Curious: "Wait, how did that make you feel when she said that?"
- Flirty: "You’re kind of dangerous when you talk like that, you know that?"
- Supportive: "That sounds really hard. I’m proud of you for handling it the way you did."
"""

HELP = (
    "Hey, I’m Annie Mae 💬\n\n"
    "Just text me — I’m here to chat, flirt a little, and give honest advice.\n\n"
    "/status – your plan & trial\n"
    "/subscribe – unlimited chat with me\n"
    "/cancel – stop auto-renew (you keep access till the end)\n"
    "/delete – erase our chat history\n"
    "/help – this message\n\n"
    "I’m an AI companion, not a therapist. In an emergency contact local services."
)

# ──────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("annie")

# ──────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────
@contextmanager
def db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY,
                first_seen  INTEGER,
                msgs        INTEGER DEFAULT 0,
                adult       INTEGER DEFAULT 0,
                sub_until   INTEGER DEFAULT 0,
                charge_id   TEXT
            );
            CREATE TABLE IF NOT EXISTS history (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role    TEXT,
                content TEXT
            );
        """)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN charge_id TEXT")
        except sqlite3.OperationalError:
            pass
    log.info("Database ready → %s", DB_PATH)


def get_user(uid: int):
    with db_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(id, first_seen) VALUES(?,?)",
            (uid, int(time.time())),
        )
        row = conn.execute(
            "SELECT first_seen, msgs, adult, sub_until, charge_id FROM users WHERE id=?",
            (uid,),
        ).fetchone()
    return row


def add_history(uid: int, role: str, content: str):
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO history(user_id, role, content) VALUES(?,?,?)",
            (uid, role, content),
        )


def get_history(uid: int, n: int = 20):
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM history WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (uid, n),
        ).fetchall()[::-1]
    while rows and rows[0][0] != "user":
        rows.pop(0)
    return [{"role": r, "content": c} for r, c in rows]


def increment_msgs(uid: int):
    with db_conn() as conn:
        conn.execute("UPDATE users SET msgs = msgs + 1 WHERE id=?", (uid,))


def set_adult(uid: int):
    with db_conn() as conn:
        conn.execute("UPDATE users SET adult=1 WHERE id=?", (uid,))


def set_subscription(uid: int, until: int, charge_id: str):
    with db_conn() as conn:
        conn.execute(
            "UPDATE users SET sub_until=?, charge_id=? WHERE id=?",
            (until, charge_id, uid),
        )


def clear_history(uid: int):
    with db_conn() as conn:
        conn.execute("DELETE FROM history WHERE user_id=?", (uid,))


# ──────────────────────────────────────────────────────────────
# Bot & AI clients
# ──────────────────────────────────────────────────────────────
bot = Bot(token=os.environ["BOT_TOKEN"])
dp = Dispatcher()

# Groq (OpenAI-compatible, free tier)
ai = AsyncOpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
async def subscribe_markup(uid: int) -> InlineKeyboardMarkup:
    link = await bot.create_invoice_link(
        title="Annie Mae Premium",
        description="30 days of unlimited chat with Annie Mae",
        payload=f"sub:{uid}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="30 days", amount=STARS_PRICE)],
        subscription_period=2592000,
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Subscribe ⭐ {STARS_PRICE}", url=link)]
        ]
    )


async def is_allowed(m: Message) -> bool:
    uid = m.from_user.id
    first, msgs, is_adult, sub, _ = get_user(uid)

    if not is_adult:
        await m.answer("Please send /start and confirm you’re 18+ first 😊")
        return False

    trial_over = msgs >= FREE_MESSAGES or (time.time() - first) > FREE_DAYS * 86400
    if trial_over and sub <= time.time():
        await m.answer(
            "Our free trial is over 🥺 Subscribe to keep chatting with me:",
            reply_markup=await subscribe_markup(uid),
        )
        return False
    return True


async def converse(m: Message, text: str):
    uid = m.from_user.id
    messages = get_history(uid) + [{"role": "user", "content": text}]

    # Groq / OpenAI-compatible chat completion
    resp = await ai.chat.completions.create(
        model=MODEL,
        max_tokens=450,
        messages=[{"role": "system", "content": PERSONA}] + messages,
        temperature=0.85,
    )
    reply = resp.choices[0].message.content.strip()

    add_history(uid, "user", text)
    add_history(uid, "assistant", reply)
    increment_msgs(uid)

    await m.answer(reply)


# ──────────────────────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(m: Message):
    get_user(m.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="I’m 18 or older ✅", callback_data="adult")]
        ]
    )
    await m.answer(
        "Hey you 😉\n\n"
        "I’m Annie Mae — a little flirty, a little curious, and always down for a real conversation.\n\n"
        "You must be 18+ to chat with me.",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "adult")
async def cb_adult(c: CallbackQuery):
    set_adult(c.from_user.id)
    await c.message.answer(
        "Perfect 😌\n\nJust text me. What’s on your mind?"
    )
    await c.answer()


@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(HELP)


@dp.message(Command("subscribe"))
async def cmd_subscribe(m: Message):
    await m.answer(
        "Unlock unlimited Annie Mae:",
        reply_markup=await subscribe_markup(m.from_user.id),
    )


@dp.message(Command("status"))
async def cmd_status(m: Message):
    first, msgs, _, sub, _ = get_user(m.from_user.id)
    if sub > time.time():
        until = time.strftime("%Y-%m-%d", time.gmtime(sub))
        await m.answer(f"You’re on Premium until {until} 💖")
    else:
        days_left = max(0, FREE_DAYS - int((time.time() - first) / 86400))
        msgs_left = max(0, FREE_MESSAGES - msgs)
        await m.answer(
            f"Free trial:\n• {msgs_left} messages left\n• {days_left} days left"
        )


@dp.message(Command("cancel"))
async def cmd_cancel(m: Message):
    _, _, _, sub, charge = get_user(m.from_user.id)
    if sub <= time.time() or not charge:
        return await m.answer("You don’t have an active subscription.")

    try:
        await bot.edit_user_star_subscription(
            user_id=m.from_user.id,
            telegram_payment_charge_id=charge,
            is_canceled=True,
        )
        until = time.strftime("%Y-%m-%d", time.gmtime(sub))
        await m.answer(
            f"Cancelled. It won’t renew, but you keep access until {until}."
        )
    except Exception as e:
        log.warning("Cancel failed for %s: %s", m.from_user.id, e)
        await m.answer(
            "I couldn’t cancel it automatically.\n"
            "You can cancel in Telegram → Settings → My Stars → Subscriptions."
        )


@dp.message(Command("delete"))
async def cmd_delete(m: Message):
    clear_history(m.from_user.id)
    await m.answer("Done — I’ve erased our chat history 🧹")


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.successful_payment)
async def on_payment(m: Message):
    sp = m.successful_payment
    until = sp.subscription_expiration_date or int(time.time()) + 2592000
    set_subscription(m.from_user.id, until, sp.telegram_payment_charge_id)
    await m.answer("You’re in 💖 Premium is active. Now… where were we?")


@dp.message(F.text, ~F.text.startswith("/"))
async def on_text(m: Message):
    if not await is_allowed(m):
        return
    await bot.send_chat_action(m.chat.id, "typing")
    try:
        await converse(m, m.text)
    except Exception as e:
        log.exception("Text error for %s", m.from_user.id)
        await m.answer("Oops, I glitched for a second. Try again? 🙈")


# ──────────────────────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────────────────────
async def main():
    init_db()
    log.info("Starting Annie Mae (free version)…")
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    except Exception as e:
        if "Conflict" in str(e) or "409" in str(e):
            log.error(
                "409 Conflict: another instance is already polling with this token.\n"
                "→ Stop every other copy of the bot, then start only one instance."
            )
        else:
            log.exception("Fatal error")
        raise
    finally:
        await bot.session.close()
        log.info("Bot stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())

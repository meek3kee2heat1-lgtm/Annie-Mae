# Annie Mae — Free Version (Text Only)

Warm, flirty, curious AI companion.  
Uses **Groq** (completely free tier) — no credit card needed.

## What you need (both free)

1. **Telegram bot token** → from [@BotFather](https://t.me/BotFather)
2. **Groq API key** → from [console.groq.com](https://console.groq.com)  
   (Sign up with Google/GitHub, create an API key — no payment required)

## Features
- Flirty + curious personality
- 18+ gate
- Free trial (20 messages or 7 days)
- Telegram Stars subscription
- Chat history
- Commands: `/start` `/status` `/subscribe` `/cancel` `/delete` `/help`

---

## 1. Get your free Groq key

1. Go to → https://console.groq.com
2. Sign up (Google or GitHub is fine)
3. Click **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_...`)

## 2. Create the Telegram bot

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. Annie Mae)
4. Choose a username ending in `bot`
5. Copy the token BotFather gives you

## 3. Run the bot

```bash
# Install
pip install -U -r requirements.txt

# Set keys (Mac/Linux)
export BOT_TOKEN="your_telegram_token"
export GROQ_API_KEY="your_groq_key"

# Windows PowerShell
# $env:BOT_TOKEN="your_telegram_token"
# $env:GROQ_API_KEY="your_groq_key"

# Start
python bot.py
```

You should see:
```
Database ready → bot.db
Starting Annie Mae (free version)…
```

Now open Telegram, search for your bot, and press **Start**.

---

## Deploy 24/7 (Railway / Fly.io / VPS)

Same instructions as the paid version:

- Add `BOT_TOKEN` and `GROQ_API_KEY` as environment variables
- Add a persistent volume and set `DB_PATH=/data/bot.db`
- Start command: `python bot.py`

---

## Notes

- This version has **no voice notes** (to stay completely free).
- Groq free tier is very generous for personal use.
- If you later want voice + Claude, we can switch back to the paid version.

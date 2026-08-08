# Atlas - AI Financial Assistant

A conversational AI financial assistant that lives inside Telegram. Built for the Atlas AI Financial Assistant Hackathon.

Atlas feels less like a chatbot and more like an experienced financial analyst — it remembers context, gives live market data, reads your documents, and proactively checks in when something worth knowing happens.

## What it does

- **Natural conversation** - no slash commands, menus, or buttons. Just talk to it.
- **Multilingual** - replies in English, Hindi, or Hinglish, matching whatever the user just wrote.
- **Memory** - remembers past messages and gradually learns your role and interests, without a signup form.
- **Live financial data**
  - Indian (NSE) stock prices, via NSE India's own data with a Yahoo Finance fallback
  - US stock prices, via Finnhub
  - Live Nifty 50 / Bank Nifty / Sensex index levels
  - Recent company news headlines
- **Multi-modal input** - text, voice notes (transcribed via Whisper), photos (analyzed via a vision model, e.g. stock chart screenshots), and PDF documents (annual reports, earnings statements, etc.)
- **Proactive daily briefing** - checks the market and the user's watchlist every morning, and only messages them if something actually moved enough to matter. Silence over noise.
- **Grounded, honest answers** - if live data isn't available, it says so instead of guessing. Tool calls are isolated per turn so the model can't blend unrelated context (e.g. an old image) into a new answer.

## Tech stack

| Layer | Choice |
|---|---|
| Bot framework | `python-telegram-bot` (polling) |
| AI | Groq (`openai/gpt-oss-120b` for chat + tool calling, `whisper-large-v3` for voice, `qwen/qwen3.6-27b` for vision) |
| Database | PostgreSQL (Neon), via SQLAlchemy |
| Scheduler | APScheduler |
| Indian stock/index data | `nse` library (NSE India), with `yfinance` fallback |
| US stock/news data | Finnhub |
| PDF parsing | `pdfplumber` |

## Setup

### 1. Create a Telegram bot
Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, and follow the prompts. You'll get a bot token.

### 2. Get API keys
- **Groq**: [console.groq.com](https://console.groq.com) → API Keys (free tier)
- **Finnhub**: [finnhub.io/register](https://finnhub.io/register) (free tier)
- **Neon (Postgres)**: [neon.tech](https://neon.tech) → create a project → copy the connection string

### 3. Set up the Python environment
```bash
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=your_neon_connection_string
FINNHUB_API_KEY=your_finnhub_api_key
```

### 5. Create the database tables
```bash
python create_tables.py
python add_profile_columns.py
```

### 6. Run the bot
```bash
python -m app.main
```
Open Telegram, find your bot, and send `/start`.

## Project structure
```
atlas-assistant/
├── app/
│   ├── main.py                  # Entry point - starts the bot + scheduler
│   ├── config.py                # Loads API keys/settings from .env
│   ├── scheduler.py             # Daily proactive market brief
│   ├── bot/
│   │   └── handlers.py          # Telegram message handlers (text/voice/photo/PDF)
│   ├── ai/
│   │   ├── orchestrator.py      # Core AI logic + tool-calling loop
│   │   ├── transcription.py     # Voice-to-text (Whisper)
│   │   └── vision.py            # Image analysis
│   ├── tools/
│   │   ├── nse_tool.py          # Indian stock prices
│   │   ├── finnhub_tool.py      # US stock prices
│   │   ├── index_tool.py        # Nifty/Bank Nifty/Sensex
│   │   ├── news_tool.py         # Company news
│   │   ├── pdf_tool.py          # PDF text extraction
│   │   └── profile_tool.py      # Onboarding/personalization
│   └── db/
│       ├── database.py          # DB connection
│       └── models.py            # User & Conversation tables
├── requirements.txt
└── .env.example
```

## Notes

- Google Workspace integrations (Gmail, Calendar) were deprioritized given the timeline — the task doc explicitly allows these to be skippable.
- The `nse` library talks directly to NSE India's site and is the primary source for Indian market data; `yfinance` is used only as a silent fallback if that fails.
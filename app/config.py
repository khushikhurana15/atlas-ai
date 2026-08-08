"""
This file loads all settings (API keys) from the .env file.
This way we don't have to write os.environ everywhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
# Optional - not currently required. Twelve Data's free tier doesn't
# cover individual NSE stock symbols (paid-plan only), so nse_tool.py
# and index_tool.py use the NSE library + yfinance fallback instead.
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing in the .env file!")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing in the .env file!")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing in the .env file!")

if not FINNHUB_API_KEY:
    raise ValueError("FINNHUB_API_KEY is missing in the .env file!")
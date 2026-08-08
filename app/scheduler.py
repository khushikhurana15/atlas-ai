"""
Sends a daily proactive market brief to every onboarded user. Runs as
a background job inside the same long-running bot process - no
separate worker needed for this prototype.

Core design principle from the task doc: "if there's nothing
important to share, stay silent - quality over frequency." So before
composing a message for any user, we check whether anything actually
moved enough to be worth a proactive ping. If nothing did, that user
is skipped entirely for the day - no filler, no "here's your update"
when there's nothing to update.
"""

import asyncio
from openai import OpenAI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo
from app.config import GROQ_API_KEY
from app.db.database import get_db_session
from app.db.models import User
from app.tools.index_tool import get_index_level
from app.tools.finnhub_tool import get_stock_quote
from app.tools.nse_tool import get_nse_stock_price
from app.bot.handlers import _fix_markdown_for_telegram

# Below this % move, a market/stock isn't "interesting enough" to
# proactively message someone about - it gets dropped from the brief.
SIGNIFICANCE_THRESHOLD = 0.3

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=20.0,
)


def _is_significant(percent_change) -> bool:
    try:
        return abs(float(percent_change)) >= SIGNIFICANCE_THRESHOLD
    except (TypeError, ValueError):
        return False


def _gather_brief_data(interests: str) -> list:
    """
    Collects live snapshots for the market index and any stocks the
    user has told us they follow (their `interests` string). Only
    the pieces that clear SIGNIFICANCE_THRESHOLD are kept - this is
    where the "silence over noise" filtering actually happens, before
    anything reaches the AI.
    """
    data_points = []

    index_data = get_index_level("nifty")
    if "error" not in index_data and _is_significant(index_data.get("percent_change")):
        data_points.append(("NIFTY 50", index_data))

    if interests:
        for raw_symbol in interests.split(","):
            symbol = raw_symbol.strip().upper()
            if not symbol:
                continue
            # Try the Indian tool first (this bot's primary market),
            # fall back to the US Finnhub tool if that's empty.
            quote = get_nse_stock_price(symbol)
            if "error" in quote:
                quote = get_stock_quote(symbol)
            if "error" not in quote and _is_significant(quote.get("percent_change")):
                data_points.append((symbol, quote))

    return data_points


def _compose_brief_text(data_points: list) -> str:
    """
    Turns raw data points into a short, natural-language brief -
    explains *why* the move matters, doesn't just recite numbers.
    Temperature kept low so it stays grounded to the data given.
    """
    raw_summary = "\n".join(f"{name}: {data}" for name, data in data_points)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        temperature=0.2,
        max_tokens=300,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Atlas, a financial analyst assistant sending a "
                    "short proactive morning brief on Telegram. You'll be "
                    "given raw live market data points below. Write a "
                    "natural 3-4 line brief - explain briefly why these "
                    "moves are worth knowing, don't just recite numbers. "
                    "Telegram Markdown only - single asterisk *bold*, no "
                    "tables. Never state a number that isn't in the data "
                    "given to you."
                ),
            },
            {"role": "user", "content": raw_summary},
        ],
    )
    return (response.choices[0].message.content or "").strip()


async def send_daily_briefs(bot):
    """The scheduled job itself - loops every user, decides whether
    today is worth messaging about, sends a brief only if so."""
    db = get_db_session()
    try:
        users = db.query(User).all()
    finally:
        db.close()

    for user in users:
        try:
            data_points = await asyncio.to_thread(_gather_brief_data, user.interests)
            if not data_points:
                continue  # nothing significant today - stay silent

            brief_text = await asyncio.to_thread(_compose_brief_text, data_points)
            if brief_text:
                await bot.send_message(
                    chat_id=int(user.telegram_id),
                    text=_fix_markdown_for_telegram(brief_text),
                    parse_mode="Markdown",
                )
        except Exception as e:
            # One user's failure (bad telegram_id, blocked bot, etc.)
            # should never stop the brief going out to everyone else.
            print(f"Failed to send daily brief to {user.telegram_id}: {e}")


def start_scheduler(bot, hour: int = 8, minute: int = 30):
    """
    Registers the daily brief job at 8:30 AM IST - timezone is set
    explicitly here so it always lands at the right IST time
    regardless of what timezone the server itself runs in (Render
    defaults to UTC).
    """
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_briefs,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=ZoneInfo("Asia/Kolkata")),
        args=[bot],
        id="daily_market_brief",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
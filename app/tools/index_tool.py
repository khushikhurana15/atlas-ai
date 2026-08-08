"""
Fetches live index levels (Nifty 50, Bank Nifty, Sensex).

Source routing: the NSE library's status feed only ever reports
NIFTY 50 - it has no way to answer a Bank Nifty or Sensex request, so
trying it first for those would always "succeed" with the wrong
index. Nifty requests try NSE first (best data when it works) with
yfinance as a fallback; Bank Nifty and Sensex go straight to
yfinance, which supports all three via distinct tickers.

Note: yfinance's `fast_info` (live bid/ask based) can be unreliable
for indices, especially outside market hours - we use `history()`
instead, which pulls recent daily closes and is much more consistent.
"""

import yfinance as yf
from pathlib import Path
from nse import NSE

DIR = Path(__file__).parent

YFINANCE_INDEX_MAP = {
    "nifty": "^NSEI",
    "nifty50": "^NSEI",
    "nifty 50": "^NSEI",
    "banknifty": "^NSEBANK",
    "bank nifty": "^NSEBANK",
    "sensex": "^BSESN",
}

NIFTY_ALIASES = {"nifty", "nifty50", "nifty 50"}


def _get_nifty_from_nse_library() -> dict:
    with NSE(download_folder=DIR, server=True) as nse:
        status_data = nse.status()

    capital_market = next(
        (row for row in status_data if row.get("market") == "Capital Market"),
        None,
    )
    if not capital_market or not capital_market.get("last"):
        raise ValueError("no Capital Market row in NSE status response")

    return {
        "index": capital_market.get("index"),
        "current_level": capital_market.get("last"),
        "change": capital_market.get("variation"),
        "percent_change": capital_market.get("percentChange"),
        "market_status": capital_market.get("marketStatusMessage"),
    }


def _get_from_yfinance(yf_ticker: str, display_name: str) -> dict:
    ticker = yf.Ticker(yf_ticker)
    hist = ticker.history(period="5d")

    if hist.empty or len(hist) < 2:
        raise ValueError(f"not enough historical data from yfinance for {yf_ticker}")

    current_level = float(hist["Close"].iloc[-1])
    previous_close = float(hist["Close"].iloc[-2])
    change = current_level - previous_close
    percent_change = (change / previous_close) * 100

    return {
        "index": display_name,
        "current_level": round(current_level, 2),
        "change": round(change, 2),
        "percent_change": round(percent_change, 2),
    }


def get_index_level(index_name: str) -> dict:
    normalized = index_name.strip().lower()
    is_known_index = normalized in YFINANCE_INDEX_MAP

    if normalized in NIFTY_ALIASES or not is_known_index:
        try:
            result = _get_nifty_from_nse_library()
        except Exception:
            try:
                result = _get_from_yfinance("^NSEI", "NIFTY 50")
            except Exception as e:
                return {"error": f"Could not fetch index data for '{index_name}': {e}"}

        if not is_known_index:
            result["note"] = (
                f"Showing NIFTY 50 as the live market snapshot - a dedicated "
                f"feed for '{index_name}' isn't available right now."
            )
        return result

    yf_ticker = YFINANCE_INDEX_MAP[normalized]
    display_name = "SENSEX" if normalized == "sensex" else "NIFTY BANK"
    try:
        return _get_from_yfinance(yf_ticker, display_name)
    except Exception as e:
        return {"error": f"Could not fetch index data for '{index_name}': {e}"}
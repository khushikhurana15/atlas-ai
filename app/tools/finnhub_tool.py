"""
This is our first "tool" - a Python function the AI can call
to get a real, live stock price from Finnhub.

Note: Finnhub's free tier is strongest for US-listed stocks
(e.g. AAPL, TSLA). Coverage for Indian NSE/BSE symbols
(e.g. RELIANCE.NS) can be limited or unavailable on the free
plan - if that happens, this function returns an error message
instead of guessing a price.
"""

import requests
from app.config import FINNHUB_API_KEY


def get_stock_quote(symbol: str) -> dict:
    """
    Fetches the current price and today's change for a stock symbol.
    Returns a dict with the data, or a dict with an "error" key if
    the symbol wasn't found or isn't supported on the free plan.
    """
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": symbol, "token": FINNHUB_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception as e:
        return {"error": f"Could not reach Finnhub: {e}"}

    # Finnhub returns all zeros when a symbol isn't found/supported
    if not data or data.get("c") in (0, None):
        return {
            "error": f"No data found for symbol '{symbol}'. It may not be "
                     f"supported on the free plan, or the symbol might be wrong."
        }

    return {
        "symbol": symbol,
        "current_price": data.get("c"),
        "change": data.get("d"),
        "percent_change": data.get("dp"),
        "high_today": data.get("h"),
        "low_today": data.get("l"),
        "previous_close": data.get("pc"),
    }
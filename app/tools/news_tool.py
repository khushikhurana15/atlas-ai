"""
Fetches recent company news headlines from Finnhub - reuses the same
FINNHUB_API_KEY already used by finnhub_tool.py (free tier includes
the /company-news endpoint, no new signup needed).

Coverage is strongest for US-listed companies. Indian tickers may
return little or nothing - this function is honest about that
instead of pretending otherwise (same philosophy as our other tools:
never fabricate, just say when data isn't available).
"""

import requests
from datetime import date, timedelta
from app.config import FINNHUB_API_KEY

MAX_HEADLINES = 5
LOOKBACK_DAYS = 7


def get_company_news(symbol: str) -> dict:
    """
    Fetches recent news headlines for a stock symbol (last 7 days).
    Returns a dict with a list of headlines, or a dict with an
    "error" key if nothing was found or the request failed.
    """
    today = date.today()
    from_date = today - timedelta(days=LOOKBACK_DAYS)

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": symbol.upper(),
        "from": from_date.isoformat(),
        "to": today.isoformat(),
        "token": FINNHUB_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception as e:
        return {"error": f"Could not reach the news source: {e}"}

    if not isinstance(data, list) or not data:
        return {
            "error": f"No recent news found for '{symbol}' in the last "
                     f"{LOOKBACK_DAYS} days (coverage is strongest for "
                     f"US-listed companies)."
        }

    headlines = [
        {
            "headline": item.get("headline"),
            "source": item.get("source"),
            "summary": (item.get("summary") or "")[:200],
        }
        for item in data[:MAX_HEADLINES]
        if item.get("headline")
    ]

    if not headlines:
        return {"error": f"No recent news found for '{symbol}'."}

    return {"symbol": symbol.upper(), "headlines": headlines}
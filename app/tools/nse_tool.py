"""
Primary Indian (NSE) stock price source: the `nse` library talking
directly to NSE India's own site. As a safety net for cloud
deployments where NSE's site blocks the request, we silently fall
back to Yahoo Finance (yfinance) - a different service with
different blocking behavior.

Uses yfinance's `history()` rather than `fast_info` for the fallback
- more consistent than the live bid/ask based fast_info, especially
outside market hours.
"""

import yfinance as yf
from pathlib import Path
from nse import NSE

DIR = Path(__file__).parent


def _get_from_nse_library(symbol: str) -> dict:
    with NSE(download_folder=DIR, server=True) as nse:
        quote = nse.quote(symbol)

    meta = quote.get("metaData") or {}
    current_price = meta.get("closePrice")
    if current_price is None:
        raise ValueError("no closePrice in NSE response")

    return {
        "symbol": symbol,
        "current_price": current_price,
        "previous_close": meta.get("previousClose"),
        "change": meta.get("change"),
        "percent_change": meta.get("pChange"),
    }


def _get_from_yfinance(symbol: str) -> dict:
    ticker = yf.Ticker(f"{symbol}.NS")
    hist = ticker.history(period="5d")

    if hist.empty or len(hist) < 2:
        raise ValueError(f"not enough historical data from yfinance for {symbol}")

    current_price = float(hist["Close"].iloc[-1])
    previous_close = float(hist["Close"].iloc[-2])
    change = current_price - previous_close
    percent_change = (change / previous_close) * 100

    return {
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "previous_close": round(previous_close, 2),
        "change": round(change, 2),
        "percent_change": round(percent_change, 2),
    }


def get_nse_stock_price(symbol: str) -> dict:
    """
    Fetches the current price for an NSE-listed stock. Tries the NSE
    library first (best data when it works); if that fails for any
    reason (most commonly: blocked on a cloud/server IP), silently
    falls back to Yahoo Finance before giving up.
    """
    clean_symbol = symbol.strip().upper().replace(".NS", "")

    try:
        return _get_from_nse_library(clean_symbol)
    except Exception as primary_error:
        try:
            return _get_from_yfinance(clean_symbol)
        except Exception as fallback_error:
            return {
                "error": (
                    f"Could not fetch data for NSE symbol '{clean_symbol}' "
                    f"from either source (primary: {primary_error}; "
                    f"fallback: {fallback_error})."
                )
            }
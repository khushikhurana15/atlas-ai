"""
A quick manual test script - calls our stock tools directly,
without going through the AI, so we can see exactly what each
one returns for a given input.

Run with: python test_tools.py
"""

from app.tools.finnhub_tool import get_stock_quote
from app.tools.nse_tool import get_nse_stock_price
from app.tools.index_tool import get_index_level

print("--- Testing get_nse_stock_price (NSE India) for TCS ---")
print(get_nse_stock_price("TCS"))

print("\n--- Testing get_stock_quote (Finnhub) for AAPL (sanity check) ---")
print(get_stock_quote("AAPL"))

print("\n--- Testing get_index_level for Nifty ---")
print(get_index_level("nifty"))
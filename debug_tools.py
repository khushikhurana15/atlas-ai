"""
Quick direct test - calls the Twelve Data tools directly and prints
the RAW dict returned, so we can see the exact error (rate limit,
bad key, wrong symbol, network issue) instead of the AI's generic
"sorry, couldn't retrieve" message.

Run with: python debug_tools.py
"""

from app.tools.nse_tool import get_nse_stock_price
from app.tools.index_tool import get_index_level

print("--- get_nse_stock_price('TCS') ---")
print(get_nse_stock_price("TCS"))

print("\n--- get_index_level('nifty') ---")
print(get_index_level("nifty"))

print("\n--- get_index_level('sensex') ---")
print(get_index_level("sensex"))

print("\n--- get_index_level('bank nifty') ---")
print(get_index_level("bank nifty"))
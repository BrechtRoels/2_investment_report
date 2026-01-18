#!/usr/bin/env python3
import sys
sys.path.insert(0, 'api')

from supabase_client import supabase

# Check NVDA prices in database
response = supabase.table("StockPrices").select("*").eq("Ticker", "NVDA").order("Date", desc=True).limit(3).execute()

print("NVDA prices in database (most recent 3):")
for record in response.data:
    print(f"  Date: {record['Date']}, Price: {record['StockPrice']}")

# Check INGA.AS prices
response2 = supabase.table("StockPrices").select("*").eq("Ticker", "INGA.AS").order("Date", desc=True).limit(3).execute()

print("\nINGA.AS prices in database (most recent 3):")
for record in response2.data:
    print(f"  Date: {record['Date']}, Price: {record['StockPrice']}")

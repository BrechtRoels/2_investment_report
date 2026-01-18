#!/usr/bin/env python3
import sys
sys.path.insert(0, 'api')

from supabase_client import supabase

print("Checking all Supabase tables...")

tables = ["Transactions", "Dividend", "MoneyInvested", "StockPrices"]

for table_name in tables:
    try:
        response = supabase.table(table_name).select("*").limit(1).execute()
        print(f"\n✅ {table_name} table exists")

        if response.data:
            print(f"   Columns: {list(response.data[0].keys())}")
        else:
            print(f"   Table is empty")
    except Exception as e:
        print(f"\n❌ Error accessing {table_name} table:")
        print(f"   {str(e)}")

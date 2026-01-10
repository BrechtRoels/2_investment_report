#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, 'api')

from supabase_client import supabase

print("Testing Supabase connection...")
print(f"URL: {os.getenv('SUPABASE_URL')}")

try:
    # Try to fetch transactions
    response = supabase.table("Transactions").select("*").limit(5).execute()
    print(f"\n✅ Connection successful!")
    print(f"Found {len(response.data)} transactions")

    if response.data:
        print("\nSample transaction:")
        print(response.data[0])
    else:
        print("\n⚠️ No transactions found in database")

except Exception as e:
    print(f"\n❌ Error connecting to Supabase:")
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")

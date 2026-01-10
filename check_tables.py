#!/usr/bin/env python3
import sys
sys.path.insert(0, 'api')

from supabase_client import supabase

print("Checking Supabase tables...")

# Try to get table info
try:
    # Check Transactions table
    response = supabase.table("Transactions").select("*", count="exact").execute()
    print(f"\n✅ Transactions table exists")
    print(f"   Total rows: {response.count if hasattr(response, 'count') else len(response.data)}")

    if response.data:
        print(f"   Columns: {list(response.data[0].keys())}")

except Exception as e:
    print(f"\n❌ Error accessing Transactions table:")
    print(f"   {str(e)}")

print("\n" + "="*60)
print("Your Transactions table is empty. You need to:")
print("1. Add some investments using the Holdings page")
print("2. Or manually insert data into the Transactions table in Supabase")
print("="*60)

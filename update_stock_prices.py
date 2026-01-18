"""
Script to update/overwrite StockPrices in Supabase with correct closing prices.
Run this script after market close to ensure all prices are accurate closing prices.

Usage:
    python update_stock_prices.py                    # Update all tickers from transactions
    python update_stock_prices.py --ticker AAPL     # Update specific ticker
    python update_stock_prices.py --days 30         # Update last 30 days (default: 365)
    python update_stock_prices.py --overwrite       # Overwrite existing prices (default: skip existing)
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
import yfinance as yf
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_ticker_currency(ticker):
    """Detect currency for a ticker"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info.get('currency', 'EUR')
    except:
        # Default based on suffix
        if ticker.endswith('.AS') or ticker.endswith('.PA') or ticker.endswith('.DE'):
            return 'EUR'
        elif ticker.endswith('.L'):
            return 'GBP'
        return 'USD'


def get_all_tickers_from_transactions():
    """Get unique tickers from the Transactions table"""
    try:
        response = supabase.table("Transactions").select("TICKER").execute()
        tickers = set()
        for row in response.data:
            ticker = row.get('TICKER')
            if ticker and ticker.upper() not in ['NOT AVAILABLE', 'N/A', 'UNKNOWN', '']:
                tickers.add(ticker)
        return list(tickers)
    except Exception as e:
        print(f"Error fetching tickers from transactions: {e}")
        return []


def fetch_closing_prices(ticker, start_date, end_date=None):
    """Fetch historical closing prices from yfinance"""
    try:
        stock = yf.Ticker(ticker)

        if end_date is None:
            end_date = datetime.now()

        hist = stock.history(start=start_date, end=end_date)

        if hist.empty:
            print(f"  [WARNING] No data returned for {ticker}")
            return []

        prices = []
        for date, row in hist.iterrows():
            prices.append({
                'date': date.date(),
                'close': float(row['Close'])
            })

        return prices
    except Exception as e:
        print(f"  [ERROR] Failed to fetch {ticker}: {e}")
        return []


def update_stock_prices(ticker, days=365, overwrite=False):
    """Update stock prices for a ticker in Supabase"""
    print(f"\n[{ticker}] Updating stock prices...")

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Get currency
    currency = get_ticker_currency(ticker)
    print(f"  Currency: {currency}")

    # Fetch prices from yfinance
    prices = fetch_closing_prices(ticker, start_date, end_date)

    if not prices:
        print(f"  [SKIP] No prices to update")
        return 0

    print(f"  Fetched {len(prices)} price records from yfinance")

    # Get existing dates if not overwriting
    existing_dates = set()
    if not overwrite:
        try:
            response = supabase.table("StockPrices").select("Date").eq("Ticker", ticker).gte("Date", start_date.isoformat()).execute()
            if response.data:
                for r in response.data:
                    try:
                        date_str = r['Date'].split('T')[0]  # Get just the date part
                        existing_dates.add(date_str)
                    except:
                        pass
            print(f"  Found {len(existing_dates)} existing records in database")
        except Exception as e:
            print(f"  [WARNING] Could not fetch existing dates: {e}")

    # If overwriting, delete existing records first
    if overwrite:
        try:
            supabase.table("StockPrices").delete().eq("Ticker", ticker).gte("Date", start_date.isoformat()).execute()
            print(f"  Deleted existing records for overwrite")
        except Exception as e:
            print(f"  [WARNING] Could not delete existing records: {e}")

    # Prepare records for insert
    records = []
    skipped = 0
    for price in prices:
        date_str = price['date'].isoformat()

        # Skip if already exists and not overwriting
        if date_str in existing_dates and not overwrite:
            skipped += 1
            continue

        records.append({
            "Date": f"{date_str}T00:00:00",
            "Ticker": ticker,
            "StockPrice": round(price['close'], 4),
            "Currency": currency
        })

    if skipped > 0:
        print(f"  Skipped {skipped} existing records")

    # Insert in batches (Supabase has limits)
    if records:
        batch_size = 100
        inserted = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            try:
                supabase.table("StockPrices").insert(batch).execute()
                inserted += len(batch)
            except Exception as e:
                print(f"  [ERROR] Failed to insert batch: {e}")

        print(f"  Inserted {inserted} new records")
        return inserted
    else:
        print(f"  No new records to insert")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Update StockPrices in Supabase')
    parser.add_argument('--ticker', '-t', help='Specific ticker to update (default: all from transactions)')
    parser.add_argument('--days', '-d', type=int, default=365, help='Number of days to fetch (default: 365)')
    parser.add_argument('--overwrite', '-o', action='store_true', help='Overwrite existing prices (default: skip)')

    args = parser.parse_args()

    print("=" * 60)
    print("Stock Price Database Updater")
    print("=" * 60)
    print(f"Date range: Last {args.days} days")
    print(f"Overwrite mode: {'ON' if args.overwrite else 'OFF'}")

    # Get tickers to update
    if args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = get_all_tickers_from_transactions()

    if not tickers:
        print("\nNo tickers found to update!")
        return

    print(f"\nTickers to update: {len(tickers)}")
    print(", ".join(tickers))

    # Update each ticker
    total_inserted = 0
    for ticker in sorted(tickers):
        try:
            inserted = update_stock_prices(ticker, days=args.days, overwrite=args.overwrite)
            total_inserted += inserted
        except Exception as e:
            print(f"\n[{ticker}] ERROR: {e}")

    print("\n" + "=" * 60)
    print(f"DONE! Total records inserted: {total_inserted}")
    print("=" * 60)


if __name__ == "__main__":
    main()

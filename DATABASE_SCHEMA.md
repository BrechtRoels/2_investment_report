# Database Schema Documentation

This document describes the database structure used in the Investment Portfolio Tracker application. The database is hosted on **Supabase** (PostgreSQL).

---

## Connection Setup

### Environment Variables

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-public-key
```

### Python Connection

```python
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
```

### Dependencies

```
supabase==2.27.1
python-dotenv==1.2.1
```

---

## Tables

### 1. Users

Stores user authentication data.

| Column | Type | Description |
|--------|------|-------------|
| `UserID` | INTEGER | Primary key, unique user identifier |
| `Username` | VARCHAR | Unique username for login |
| `Password` | VARCHAR | User password (plain text - should be hashed in production) |

#### Example Queries

```python
# Get user by ID
response = supabase.table("Users").select("*").eq("UserID", user_id).execute()

# Get user by username (for login)
response = supabase.table("Users").select("*").eq("Username", username).execute()
```

---

### 2. Transactions

Stores all buy/sell transactions for stocks and ETFs.

| Column | Type | Description |
|--------|------|-------------|
| `TransactionID` | INTEGER | Primary key, auto-increment |
| `UserID` | INTEGER | Foreign key to Users table |
| `DATE` | DATE | Transaction date (YYYY-MM-DD) |
| `TICKER` | VARCHAR | Stock/ETF ticker symbol (e.g., "AAPL", "VWCE.AS") |
| `NAME` | VARCHAR | Full name of the investment |
| `ACTION` | VARCHAR | Transaction type: "BUY", "SELL", "PURCHASE", "SALE", "SOLD" |
| `QUANTITY` | INTEGER | Number of shares |
| `PRICE` | VARCHAR | Price per share in EUR (e.g., "€150.00") |
| `PRICE BEFORE CURRENCY` | VARCHAR | Original price before currency conversion |
| `CURRENCY FROM` | VARCHAR | Original currency (e.g., "USD", "GBP") |
| `EXCHANGE RATE` | VARCHAR | Exchange rate used for conversion |
| `CURRENCY TO` | VARCHAR | Target currency (usually "EUR") |
| `TOTAL AMOUNT BT` | VARCHAR | Total amount before fees (Price × Quantity) |
| `BROKERAGE FEE` | VARCHAR | Broker commission fee |
| `STOCK MARKET FEE` | VARCHAR | Stock exchange fee |
| `TOTAL PURCHASE PRICE` | VARCHAR | Total cost including all fees |

#### Example Queries

```python
# Get all transactions for a user
response = supabase.table("Transactions").select("*").eq("UserID", user_id).execute()

# Get transactions ordered by date
response = supabase.table("Transactions").select("*").eq("UserID", user_id).order("DATE", desc=True).execute()

# Get transactions for a specific ticker
response = supabase.table("Transactions").select("*").eq("UserID", user_id).eq("TICKER", "AAPL").execute()

# Get next transaction ID
response = supabase.table("Transactions").select("TransactionID").order("TransactionID", desc=True).limit(1).execute()

# Insert new transaction
new_transaction = {
    "TransactionID": next_id,
    "UserID": user_id,
    "DATE": "2024-01-15",
    "TICKER": "AAPL",
    "NAME": "Apple Inc.",
    "ACTION": "BUY",
    "QUANTITY": 10,
    "PRICE": "€150.00",
    "TOTAL PURCHASE PRICE": "€1505.00"
}
supabase.table("Transactions").insert(new_transaction).execute()

# Update transaction
supabase.table("Transactions").update(updated_data).eq("TransactionID", transaction_id).execute()

# Delete transaction
supabase.table("Transactions").delete().eq("TransactionID", transaction_id).execute()
```

---

### 3. Dividend

Stores dividend payments received.

| Column | Type | Description |
|--------|------|-------------|
| `DividendID` | INTEGER | Primary key, auto-increment |
| `UserID` | INTEGER | Foreign key to Users table |
| `DATE` | DATE | Dividend payment date |
| `TICKER` | VARCHAR | Stock/ETF ticker symbol |
| `NAME` | VARCHAR | Full name of the investment |
| `ETF` | INTEGER | 1 if ETF, 0 if stock |
| `VALUE RECEIVED BEFORE TAX` | DECIMAL | Gross dividend amount |
| `BUITENLANDSE BRONHEFFING` | DECIMAL | Foreign withholding tax |
| `KOSTEN INCASSOSTELLING` | DECIMAL | Collection fee |
| `ROERENDE VOORHEFFING` | DECIMAL | Belgian withholding tax |
| `BTW` | DECIMAL | VAT |
| `TOTAL_DIVIDEND` | DECIMAL | Net dividend received |

#### Example Queries

```python
# Get all dividends for a user
response = supabase.table("Dividend").select("*").eq("UserID", user_id).order("DATE", desc=True).execute()

# Get dividends for specific ticker
response = supabase.table("Dividend").select("*").eq("UserID", user_id).eq("TICKER", "AAPL").execute()

# Insert new dividend
new_dividend = {
    "DividendID": next_id,
    "UserID": user_id,
    "DATE": "2024-03-15",
    "TICKER": "AAPL",
    "NAME": "Apple Inc.",
    "ETF": 0,
    "VALUE RECEIVED BEFORE TAX": 25.00,
    "ROERENDE VOORHEFFING": 7.50,
    "TOTAL_DIVIDEND": 17.50
}
supabase.table("Dividend").insert(new_dividend).execute()

# Update dividend
supabase.table("Dividend").update(updated_data).eq("DividendID", dividend_id).execute()

# Delete dividend
supabase.table("Dividend").delete().eq("DividendID", dividend_id).execute()
```

---

### 4. MoneyInvested

Tracks deposits and withdrawals to/from the investment account.

| Column | Type | Description |
|--------|------|-------------|
| `MoneyInvestedID` | INTEGER | Primary key, auto-increment |
| `UserID` | INTEGER | Foreign key to Users table |
| `DATE` | DATE | Date of deposit/withdrawal |
| `AMOUNT` | VARCHAR | Amount in EUR (e.g., "€1000.00") |
| `ACTION` | VARCHAR | "DEPOSIT" or "WITHDRAW" |

#### Example Queries

```python
# Get all money invested records
response = supabase.table("MoneyInvested").select("*").eq("UserID", user_id).order("DATE", desc=True).execute()

# Insert new deposit
new_record = {
    "MoneyInvestedID": next_id,
    "UserID": user_id,
    "DATE": "2024-01-01",
    "AMOUNT": "€1000.00",
    "ACTION": "DEPOSIT"
}
supabase.table("MoneyInvested").insert(new_record).execute()

# Update record
supabase.table("MoneyInvested").update(updated_data).eq("MoneyInvestedID", record_id).execute()

# Delete record
supabase.table("MoneyInvested").delete().eq("MoneyInvestedID", record_id).execute()
```

---

### 5. StockPrices

Caches historical stock prices to reduce API calls.

| Column | Type | Description |
|--------|------|-------------|
| `Ticker` | VARCHAR | Stock/ETF ticker symbol |
| `Date` | TIMESTAMP | Price date (ISO format) |
| `StockPrice` | DECIMAL | Closing price |
| `Currency` | VARCHAR | Price currency (e.g., "EUR", "USD") |

#### Example Queries

```python
# Get latest price for a ticker
response = supabase.table("StockPrices").select("StockPrice, Date").eq("Ticker", "AAPL").order("Date", desc=True).limit(1).execute()

# Get price history for date range
response = supabase.table("StockPrices").select("Date, StockPrice").eq("Ticker", "AAPL").gte("Date", "2024-01-01").lte("Date", "2024-12-31").order("Date").execute()

# Check existing dates (to avoid duplicates)
response = supabase.table("StockPrices").select("Date").eq("Ticker", "AAPL").gte("Date", start_date).execute()

# Bulk insert prices
records = [
    {"Date": "2024-01-01T00:00:00", "Ticker": "AAPL", "StockPrice": 185.50, "Currency": "USD"},
    {"Date": "2024-01-02T00:00:00", "Ticker": "AAPL", "StockPrice": 186.25, "Currency": "USD"}
]
supabase.table("StockPrices").insert(records).execute()
```

---

## Entity Relationships

```
Users (1) ──────< (N) Transactions
Users (1) ──────< (N) Dividend
Users (1) ──────< (N) MoneyInvested

StockPrices (standalone cache table - no foreign keys)
```

---

## Common Query Patterns

### Get Portfolio Holdings

```python
# Calculate current holdings from transactions
response = supabase.table("Transactions").select("*").eq("UserID", user_id).execute()

holdings = {}
for txn in response.data:
    ticker = txn.get('TICKER')
    action = txn.get('ACTION', '').upper()
    quantity = txn.get('QUANTITY', 0)

    if ticker not in holdings:
        holdings[ticker] = {'shares': 0, 'cost': 0}

    if action in ['BUY', 'PURCHASE']:
        holdings[ticker]['shares'] += quantity
        holdings[ticker]['cost'] += parse_price(txn.get('TOTAL PURCHASE PRICE', 0))
    elif action in ['SELL', 'SALE', 'SOLD']:
        holdings[ticker]['shares'] -= quantity

# Filter to active holdings only
active_holdings = {k: v for k, v in holdings.items() if v['shares'] > 0}
```

### Calculate Total Dividends

```python
response = supabase.table("Dividend").select("*").eq("UserID", user_id).execute()
total_dividends = sum(float(d.get('TOTAL_DIVIDEND', 0) or 0) for d in response.data)
```

### Calculate Net Invested

```python
response = supabase.table("MoneyInvested").select("*").eq("UserID", user_id).execute()
total = 0
for record in response.data:
    action = record.get('ACTION', '').upper()
    amount = parse_price(record.get('AMOUNT', 0))
    if action == 'DEPOSIT':
        total += amount
    elif action == 'WITHDRAW':
        total -= amount
```

---

## Utility Functions

### Parse Price String

Many price fields are stored as strings with currency symbols. Use this helper:

```python
def parse_price(price_str):
    """Parse price string with currency symbols (e.g., '€174.60') to float"""
    if not price_str:
        return 0.0
    if isinstance(price_str, (int, float)):
        return float(price_str)

    # Remove currency symbols and whitespace
    import re
    cleaned = re.sub(r'[€$£¥,\s]', '', str(price_str))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
```

---

## SQL Schema (for reference)

```sql
-- Users table
CREATE TABLE Users (
    UserID SERIAL PRIMARY KEY,
    Username VARCHAR(255) UNIQUE NOT NULL,
    Password VARCHAR(255) NOT NULL
);

-- Transactions table
CREATE TABLE Transactions (
    TransactionID SERIAL PRIMARY KEY,
    UserID INTEGER REFERENCES Users(UserID),
    DATE DATE,
    TICKER VARCHAR(50),
    NAME VARCHAR(255),
    ACTION VARCHAR(50),
    QUANTITY INTEGER,
    PRICE VARCHAR(50),
    "PRICE BEFORE CURRENCY" VARCHAR(50),
    "CURRENCY FROM" VARCHAR(10),
    "EXCHANGE RATE" VARCHAR(50),
    "CURRENCY TO" VARCHAR(10),
    "TOTAL AMOUNT BT" VARCHAR(50),
    "BROKERAGE FEE" VARCHAR(50),
    "STOCK MARKET FEE" VARCHAR(50),
    "TOTAL PURCHASE PRICE" VARCHAR(50)
);

-- Dividend table
CREATE TABLE Dividend (
    DividendID SERIAL PRIMARY KEY,
    UserID INTEGER REFERENCES Users(UserID),
    DATE DATE,
    TICKER VARCHAR(50),
    NAME VARCHAR(255),
    ETF INTEGER DEFAULT 0,
    "VALUE RECEIVED BEFORE TAX" DECIMAL(10,2),
    "BUITENLANDSE BRONHEFFING" DECIMAL(10,2),
    "KOSTEN INCASSOSTELLING" DECIMAL(10,2),
    "ROERENDE VOORHEFFING" DECIMAL(10,2),
    BTW DECIMAL(10,2),
    TOTAL_DIVIDEND DECIMAL(10,2)
);

-- MoneyInvested table
CREATE TABLE MoneyInvested (
    MoneyInvestedID SERIAL PRIMARY KEY,
    UserID INTEGER REFERENCES Users(UserID),
    DATE DATE,
    AMOUNT VARCHAR(50),
    ACTION VARCHAR(50)
);

-- StockPrices table (cache)
CREATE TABLE StockPrices (
    Ticker VARCHAR(50),
    Date TIMESTAMP,
    StockPrice DECIMAL(10,4),
    Currency VARCHAR(10),
    PRIMARY KEY (Ticker, Date)
);
```

---

## Notes

1. **Price Storage**: Prices are stored as VARCHAR with currency symbols (e.g., "€150.00"). Use `parse_price()` to convert to float.

2. **Date Format**: Dates are stored as DATE or TIMESTAMP in ISO format (YYYY-MM-DD).

3. **User Authentication**: Currently uses plain text passwords. For production, implement password hashing with `werkzeug.security`.

4. **StockPrices Cache**: The StockPrices table is a cache for historical prices. Live prices are fetched from yfinance API.

5. **Column Names with Spaces**: Some columns have spaces in their names (e.g., "TOTAL PURCHASE PRICE"). Access them using bracket notation or quotes.

---

## External APIs Used

| API | Purpose | Python Package |
|-----|---------|----------------|
| Supabase | Database | `supabase` |
| Yahoo Finance | Stock prices, news | `yfinance` |
| Ollama (local) | AI chat, news summaries | HTTP requests |

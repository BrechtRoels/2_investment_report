# 🚀 Quick Start Guide

## Start the Application

```bash
cd /Users/brechtroels/Documents/1_Projects/2_investment_report/2_investment_report
python api/index.py
```

## Access Your Portfolio

Open your browser and navigate to: **http://localhost:5000**

## Features Overview

### 📊 Dashboard (http://localhost:5000/)
- View portfolio summary and statistics
- **Interactive Performance Chart** with benchmarking
  - Toggle between S&P 500, BEL 20, Euro Stoxx 50
  - Select time ranges: 1M, 3M, 6M, 1Y, ALL
  - Dual Y-axis: Portfolio value (€) vs Benchmark (%)
- Asset allocation pie chart
- Top 5 holdings

### 💼 Holdings (http://localhost:5000/holdings)
- View all current stock positions
- Live price updates from yfinance
- Color-coded gains/losses
- Total portfolio value

### 📝 Transactions (http://localhost:5000/transactions)
- **NEW: Add Transaction button** - Create new buy/sell transactions
- Edit existing transactions
- View complete transaction history
- Filter and search capabilities

### 💰 Dividends (http://localhost:5000/dividends)
- **NEW: Edit & Delete** - Full control over dividend records
- Add new dividend payments
- Track taxes and fees
- View dividend statistics (Total, This Year, Last 12 Months)

### 💵 Money Invested (http://localhost:5000/money-invested) **NEW PAGE!**
- **Full CRUD Operations** - Add, Edit, Delete investment deposits
- Track all money you've invested
- Categories: Initial Deposit, Monthly Contribution, Bonus/Extra, Transfer, Other
- Statistics: Total Invested, This Year, This Month, Record Count

## Quick Actions

### Add a Dividend
1. Go to Dividends page
2. Click "+ Add Dividend"
3. Fill in ticker, amount, taxes
4. Click "Add Dividend"

### Add a Transaction
1. Go to Transactions page
2. Click "+ Add Transaction" (top right)
3. Fill in ticker, action, price, quantity
4. Click "Add Transaction"

### Track Money Invested
1. Go to Money Invested page
2. Click "+ Add Record"
3. Enter date, amount, category
4. Click "Save"

### Edit Any Record
1. Find the record in the table
2. Click "Edit" button
3. Modify fields
4. Click "Save"

### Delete Any Record
1. Find the record in the table
2. Click "Delete" button
3. Confirm deletion

## Key Features

✅ **Automatic Price Fetching** - Live prices from yfinance
✅ **Currency Conversion** - All prices converted to EUR
✅ **Weekend-Aware Caching** - Doesn't fetch on market closed days
✅ **Database Caching** - Fast performance with StockPrices cache
✅ **Benchmark Comparison** - Compare against S&P 500, BEL 20, Euro Stoxx 50
✅ **Full CRUD Operations** - Create, Read, Update, Delete on all pages
✅ **Responsive Design** - Works on desktop and mobile

## Navigation

All pages have unified navigation at the top:

```
Dashboard | Holdings | Transactions | Dividends | Money Invested
```

## File Structure

```
2_investment_report/
├── api/
│   ├── index.py           # Main Flask application (backend)
│   └── supabase_client.py # Database connection
├── templates/
│   ├── dashboard.html     # Portfolio overview + interactive chart
│   ├── holdings.html      # Current positions
│   ├── transactions.html  # Transaction history + Add button
│   ├── dividends.html     # Dividends + Edit/Delete
│   └── money_invested.html# Investment tracking (NEW!)
├── requirements.txt       # Python dependencies
└── .env                   # Supabase credentials

```

## Troubleshooting

**Port already in use?**
```bash
lsof -ti:5000 | xargs kill
```

**Missing dependencies?**
```bash
pip install -r requirements.txt
```

**Database connection issues?**
Check your `.env` file has correct Supabase credentials.

## What's New

### ✨ Recent Updates:
1. **Dividends Page** - Added Edit and Delete buttons for all dividend records
2. **Transactions Page** - Added "+ Add Transaction" button with modal form
3. **Money Invested Page** - Brand new page to track investment deposits
4. **Navigation** - All pages now have "Money Invested" link
5. **Portfolio Chart** - Interactive chart with benchmark comparison
6. **Ticker Filtering** - Automatically excludes "Not Available" tickers

## Support

For issues or questions, check:
- [COMPLETED_FEATURES.md](COMPLETED_FEATURES.md) - Detailed feature documentation
- [FRONTEND_CHANGES.md](FRONTEND_CHANGES.md) - Code changes reference
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical overview

Enjoy your fully functional investment portfolio tracker! 🎉

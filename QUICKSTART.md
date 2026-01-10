# Quick Start Guide

## Run the Application (3 steps)

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Run the app**:
```bash
python3 api/index.py
```

3. **Open in browser**:
```
http://localhost:5000
```

That's it! The database will be created automatically (empty and ready for your investments).

## Using the Application

### Dashboard Page (`/`)
Your portfolio command center showing:
- 💰 Total Portfolio Value
- 📈 Total Gain/Loss with percentage
- 📊 Number of Investments
- 💵 Total Amount Invested
- 📈 30-day Performance Chart
- 🥧 Asset Allocation Chart
- 🏆 Top 5 Holdings

### Holdings Page (`/holdings`)

**Add New Investment**
1. Click the "+ Add Investment" button in the top right
2. Fill in the form:
   - **Investment Name**: e.g., "Apple Stock"
   - **Symbol**: e.g., "AAPL"
   - **Number of Shares**: e.g., 100
   - **Purchase Price**: e.g., 150.00 (price per share when you bought)
   - **Current Price**: e.g., 175.00 (current price per share)
3. Click "Save Investment"
4. A "BUY" transaction is automatically created

**Edit Investment**
1. Find the investment card you want to edit
2. Click the "Edit" button
3. Modify any fields
4. Click "Save Investment"
5. An "UPDATE" transaction is automatically logged

**Delete Investment**
1. Find the investment card you want to delete
2. Click the "Delete" button
3. Confirm the deletion

### Transactions Page (`/transactions`)

View all your investment activity:
- **Filter by Type**: Buy, Sell, or Update
- **Filter by Investment**: Select specific investment
- **Filter by Date**: Date range picker
- **Sort**: Click any column header to sort
- **Clear Filters**: Reset all filters at once

Each transaction shows:
- Date and time
- Transaction type (color-coded)
- Investment name and symbol
- Number of shares
- Price per share
- Total transaction value
- Notes

## Viewing the Database

### Option 1: Using DBeaver (Recommended)
```bash
brew install --cask dbeaver-community
```
Then open the file: `database/investment.db`

### Option 2: Using DB Browser for SQLite
```bash
brew install --cask db-browser-for-sqlite
```
Then open the file: `database/investment.db`

### Option 3: Command Line
```bash
sqlite3 database/investment.db

# View all investments
SELECT * FROM investments;

# View specific columns
SELECT name, symbol, shares, current_price FROM investments;

# Exit
.quit
```

## Troubleshooting

**Error: ModuleNotFoundError: No module named 'flask'**
- Run: `pip install -r requirements.txt`

**Error: command not found: python**
- Use `python3` instead: `python3 api/index.py`

**Port 5000 already in use**
- Kill the existing process or edit `api/index.py` to use a different port

**Database is empty**
- Delete `database/investment.db` and restart the app to recreate with sample data

## Next Steps

1. Add your real investments
2. Update current prices regularly
3. Explore the database using DBeaver or DB Browser
4. Deploy to Vercel (see README.md)

Enjoy tracking your investments!

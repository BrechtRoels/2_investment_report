# 💎 Investment Portfolio Tracker

A beautiful, modern web application for tracking your investment portfolio with real-time data visualization and stunning gradient UI.

![Portfolio Tracker](https://img.shields.io/badge/Python-Flask-blue)
![Vercel](https://img.shields.io/badge/Deploy-Vercel-black)
![Database](https://img.shields.io/badge/Database-SQLite-green)

## Features

### 📊 Dashboard Page
- **Portfolio Overview**: Beautiful intro page with key statistics
- **Performance Charts**: 30-day historical performance and asset allocation
- **Top Holdings**: Quick view of your best performing investments
- **Real-time Calculations**: Automatic gain/loss calculations

### 💼 Holdings Page
- **Full CRUD Operations**: Add, edit, and delete investments through an intuitive interface
- **Investment Cards**: Detailed view of each investment with real-time data
- **Portfolio Summary**: Total value, gains/losses, and performance metrics
- **Modal Forms**: Beautiful forms for adding and editing investments

### 📝 Transactions Page
- **Complete Transaction History**: View all buy, sell, and update transactions
- **Advanced Filtering**: Filter by type, investment, and date range
- **Sortable Columns**: Click any column header to sort
- **Modern Table Design**: Clean, responsive table with hover effects

### 🎨 Design & UX
- **Modern Gradient UI**: Beautiful purple gradient theme
- **Smooth Animations**: Polished transitions and hover effects
- **Responsive Design**: Works perfectly on desktop, tablet, and mobile
- **Navigation**: Easy navigation between Dashboard, Holdings, and Transactions

## Tech Stack

- **Backend**: Python Flask
- **Database**: SQLite (built into Python)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Charts**: Chart.js
- **Deployment**: Vercel

## Local Development

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Run the application**:
```bash
python api/index.py
```

The database will be automatically created on first run (empty - ready for your data).

3. **Open your browser** and navigate to:
```
http://localhost:5000
```

4. **Start managing your investments**:
   - Click "+ Add Investment" to add new investments
   - Click "Edit" on any investment card to update it
   - Click "Delete" to remove an investment
   - All changes are saved to the SQLite database

## Database

The application uses **SQLite**, which is built into Python (no installation required).

### Database Location
- The database file is created at: `database/investment.db`
- It's automatically initialized when you first run the app

### Database Tables

**investments** - Stores your investment data
- `id` - Unique identifier
- `name` - Investment name (e.g., "Tech Growth Fund")
- `symbol` - Stock/fund symbol (e.g., "TGF")
- `shares` - Number of shares owned
- `purchase_price` - Price per share when purchased
- `current_price` - Current price per share
- `created_at` - Timestamp when added
- `updated_at` - Timestamp when last updated

**transactions** - Track buy/sell history (for future features)
**portfolio_history** - Track portfolio value over time (for future features)

### Viewing/Managing Database

You can view and edit the database using free tools:

**Option 1: DBeaver (Recommended)**
```bash
brew install --cask dbeaver-community
```
Then open `database/investment.db` in DBeaver

**Option 2: DB Browser for SQLite**
```bash
brew install --cask db-browser-for-sqlite
```
Then open `database/investment.db`

**Option 3: Command Line**
```bash
sqlite3 database/investment.db
# Type .tables to see all tables
# Type .schema investments to see table structure
# Type SELECT * FROM investments; to see all data
# Type .quit to exit
```

## Deploy to Vercel

### Option 1: Using Vercel CLI

1. Install Vercel CLI:
```bash
npm i -g vercel
```

2. Deploy:
```bash
vercel
```

### Option 2: Using Vercel Dashboard

1. Push this repository to GitHub
2. Go to [Vercel Dashboard](https://vercel.com)
3. Click "New Project"
4. Import your GitHub repository
5. Vercel will automatically detect the configuration
6. Click "Deploy"

That's it! Your application will be live in seconds.

## Project Structure

```
2_investment_report/
├── api/
│   └── index.py                # Flask application and API endpoints
├── database/
│   ├── init_db.py              # Database initialization script (optional)
│   └── investment.db           # SQLite database (auto-created)
├── templates/
│   ├── dashboard.html          # Main dashboard page
│   ├── holdings.html           # Holdings management page
│   └── transactions.html       # Transactions history page
├── vercel.json                 # Vercel configuration
├── requirements.txt            # Python dependencies
├── QUICKSTART.md              # Quick start guide
└── README.md                  # This file
```

## Pages

### Dashboard (`/`)
- Portfolio overview with key statistics
- Performance charts (line chart + doughnut chart)
- Top 5 holdings display
- Quick navigation to other pages

### Holdings (`/holdings`)
- View all investments in card format
- Add new investments
- Edit existing investments
- Delete investments
- Real-time portfolio calculations

### Transactions (`/transactions`)
- Complete transaction history
- Filter by type (buy/sell/update)
- Filter by investment
- Filter by date range
- Sortable table columns

## API Endpoints

### Pages
- `GET /` - Dashboard page
- `GET /holdings` - Holdings management page
- `GET /transactions` - Transactions history page

### API
- `GET /api/portfolio` - Get portfolio summary and all investments
- `GET /api/transactions` - Get all transactions with investment details
- `GET /api/chart-data` - Get 30-day historical portfolio data
- `POST /api/investments` - Add a new investment (auto-creates transaction)
- `PUT /api/investments/<id>` - Update an existing investment (auto-logs transaction)
- `DELETE /api/investments/<id>` - Delete an investment

## License

MIT
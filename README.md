# 💎 Investment Portfolio Tracker

A beautiful, modern web application for tracking your investment portfolio with real-time data visualization and stunning gradient UI.

![Portfolio Tracker](https://img.shields.io/badge/Python-Flask-blue)
![Vercel](https://img.shields.io/badge/Deploy-Vercel-black)
![Database](https://img.shields.io/badge/Database-SQLite-green)

## Features

- **Beautiful UI**: Modern gradient design with smooth animations and modal forms
- **Full CRUD Operations**: Add, edit, and delete investments through an intuitive interface
- **SQLite Database**: Local database storage with automatic initialization
- **Portfolio Dashboard**: View total portfolio value, gains/losses, and performance metrics
- **Interactive Charts**: 30-day historical performance visualization using Chart.js
- **Investment Management**: Track shares, purchase price, current price, and gains for each investment
- **Responsive Design**: Works perfectly on desktop, tablet, and mobile devices
- **Easy Deployment**: Ready to deploy to Vercel with one click

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

The database will be automatically created on first run with sample data.

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
│   └── index.py          # Flask application and API endpoints
├── database/
│   ├── init_db.py        # Database initialization script (optional)
│   └── investment.db     # SQLite database (auto-created)
├── templates/
│   └── index.html        # Main HTML template with embedded CSS/JS
├── vercel.json           # Vercel configuration
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## API Endpoints

- `GET /` - Main application page
- `GET /api/portfolio` - Get portfolio summary and all investments
- `GET /api/chart-data` - Get 30-day historical portfolio data
- `POST /api/investments` - Add a new investment
- `PUT /api/investments/<id>` - Update an existing investment
- `DELETE /api/investments/<id>` - Delete an investment

## License

MIT
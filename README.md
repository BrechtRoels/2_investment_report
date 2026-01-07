# 💎 Investment Portfolio Tracker

A beautiful, modern web application for tracking your investment portfolio with real-time data visualization and stunning gradient UI.

![Portfolio Tracker](https://img.shields.io/badge/Python-Flask-blue)
![Vercel](https://img.shields.io/badge/Deploy-Vercel-black)

## Features

- **Beautiful UI**: Modern gradient design with smooth animations
- **Portfolio Dashboard**: View total portfolio value, gains/losses, and performance metrics
- **Interactive Charts**: 30-day historical performance visualization using Chart.js
- **Investment Cards**: Detailed view of each investment with real-time changes
- **Responsive Design**: Works perfectly on desktop, tablet, and mobile devices
- **Easy Deployment**: Ready to deploy to Vercel with one click

## Tech Stack

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Charts**: Chart.js
- **Deployment**: Vercel

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python api/index.py
```

3. Open your browser and navigate to:
```
http://localhost:5000
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
├── templates/
│   └── index.html        # Main HTML template with embedded CSS/JS
├── vercel.json           # Vercel configuration
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## API Endpoints

- `GET /` - Main application page
- `GET /api/portfolio` - Get portfolio summary and investments
- `GET /api/chart-data` - Get 30-day historical portfolio data

## Customization

You can customize the investments by editing the `INVESTMENTS` array in [api/index.py](api/index.py):

```python
INVESTMENTS = [
    {"name": "Your Fund", "symbol": "YF", "shares": 100, "price": 150.00, "change": 2.5},
    # Add more investments...
]
```

## License

MIT
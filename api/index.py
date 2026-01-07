from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta
import random

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Sample investment data
INVESTMENTS = [
    {"name": "Tech Growth Fund", "symbol": "TGF", "shares": 150, "price": 245.30, "change": 2.45},
    {"name": "Global Equity", "symbol": "GEQ", "shares": 200, "price": 89.75, "change": -0.82},
    {"name": "Sustainable Energy", "symbol": "SENG", "shares": 75, "price": 312.40, "change": 5.67},
    {"name": "Real Estate Trust", "symbol": "RET", "shares": 120, "price": 156.20, "change": 1.23},
    {"name": "Crypto Index", "symbol": "CRIX", "shares": 50, "price": 523.90, "change": -3.45},
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio')
def get_portfolio():
    total_value = sum(inv['shares'] * inv['price'] for inv in INVESTMENTS)
    total_gain = sum(inv['shares'] * inv['price'] * (inv['change'] / 100) for inv in INVESTMENTS)

    return jsonify({
        'investments': INVESTMENTS,
        'total_value': round(total_value, 2),
        'total_gain': round(total_gain, 2),
        'gain_percentage': round((total_gain / total_value) * 100, 2)
    })

@app.route('/api/chart-data')
def get_chart_data():
    # Generate sample historical data for the last 30 days
    base_value = 95000
    data = []
    current_date = datetime.now() - timedelta(days=30)

    for i in range(31):
        value = base_value + random.uniform(-5000, 8000) + (i * 300)
        data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'value': round(value, 2)
        })
        current_date += timedelta(days=1)

    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)

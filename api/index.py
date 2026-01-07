from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import sqlite3
import os
import random

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'investment.db')

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db_if_needed():
    """Initialize database if it doesn't exist"""
    if not os.path.exists(DB_PATH):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

        # Create database tables directly
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create investments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                symbol TEXT NOT NULL UNIQUE,
                shares INTEGER NOT NULL,
                purchase_price REAL NOT NULL,
                current_price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investment_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                shares INTEGER NOT NULL,
                price REAL NOT NULL,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (investment_id) REFERENCES investments (id)
            )
        ''')

        # Create portfolio_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                total_value REAL NOT NULL,
                total_gain REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Insert sample data
        sample_investments = [
            ('Tech Growth Fund', 'TGF', 150, 200.00, 245.30),
            ('Global Equity', 'GEQ', 200, 85.00, 89.75),
            ('Sustainable Energy', 'SENG', 75, 280.00, 312.40),
            ('Real Estate Trust', 'RET', 120, 145.00, 156.20),
            ('Crypto Index', 'CRIX', 50, 500.00, 523.90),
        ]

        cursor.executemany('''
            INSERT INTO investments (name, symbol, shares, purchase_price, current_price)
            VALUES (?, ?, ?, ?, ?)
        ''', sample_investments)

        conn.commit()
        conn.close()
        print(f"✅ Database initialized at: {DB_PATH}")

# Initialize database on startup
init_db_if_needed()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio')
def get_portfolio():
    """Get all investments and portfolio summary"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, symbol, shares, purchase_price, current_price
        FROM investments
        ORDER BY name
    ''')

    investments = []
    total_value = 0
    total_cost = 0

    for row in cursor.fetchall():
        current_value = row['shares'] * row['current_price']
        cost = row['shares'] * row['purchase_price']
        change_percent = ((row['current_price'] - row['purchase_price']) / row['purchase_price']) * 100

        investments.append({
            'id': row['id'],
            'name': row['name'],
            'symbol': row['symbol'],
            'shares': row['shares'],
            'purchase_price': round(row['purchase_price'], 2),
            'current_price': round(row['current_price'], 2),
            'change': round(change_percent, 2),
            'value': round(current_value, 2)
        })

        total_value += current_value
        total_cost += cost

    conn.close()

    total_gain = total_value - total_cost
    gain_percentage = (total_gain / total_cost * 100) if total_cost > 0 else 0

    return jsonify({
        'investments': investments,
        'total_value': round(total_value, 2),
        'total_gain': round(total_gain, 2),
        'gain_percentage': round(gain_percentage, 2)
    })

@app.route('/api/investments', methods=['POST'])
def add_investment():
    """Add a new investment"""
    data = request.json

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO investments (name, symbol, shares, purchase_price, current_price)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['symbol'].upper(),
            int(data['shares']),
            float(data['purchase_price']),
            float(data.get('current_price', data['purchase_price']))
        ))

        conn.commit()
        investment_id = cursor.lastrowid
        conn.close()

        return jsonify({'success': True, 'id': investment_id, 'message': 'Investment added successfully'}), 201

    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': f'Investment with symbol {data["symbol"]} already exists'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/investments/<int:investment_id>', methods=['PUT'])
def update_investment(investment_id):
    """Update an existing investment"""
    data = request.json

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE investments
            SET name = ?, symbol = ?, shares = ?, purchase_price = ?, current_price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            data['name'],
            data['symbol'].upper(),
            int(data['shares']),
            float(data['purchase_price']),
            float(data['current_price']),
            investment_id
        ))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Investment updated successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/investments/<int:investment_id>', methods=['DELETE'])
def delete_investment(investment_id):
    """Delete an investment"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM investments WHERE id = ?', (investment_id,))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Investment deleted successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/chart-data')
def get_chart_data():
    """Generate sample historical data for the last 30 days"""
    conn = get_db()
    cursor = conn.cursor()

    # Get current total value
    cursor.execute('SELECT SUM(shares * current_price) as total FROM investments')
    result = cursor.fetchone()
    current_value = result['total'] if result['total'] else 100000
    conn.close()

    # Generate historical data
    base_value = current_value * 0.85
    data = []
    current_date = datetime.now() - timedelta(days=30)

    for i in range(31):
        value = base_value + random.uniform(-5000, 8000) + (i * ((current_value - base_value) / 30))
        data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'value': round(value, 2)
        })
        current_date += timedelta(days=1)

    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)

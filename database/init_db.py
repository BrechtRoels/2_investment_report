import sqlite3
import os

def init_database():
    """Initialize the database with tables and sample data"""

    # Get the directory where this script is located
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, 'investment.db')

    # Connect to database (creates file if it doesn't exist)
    conn = sqlite3.connect(db_path)
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

    # Create transactions table for tracking buy/sell history
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

    # Create portfolio_history table for tracking daily values
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL UNIQUE,
            total_value REAL NOT NULL,
            total_gain REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Check if we already have data
    cursor.execute('SELECT COUNT(*) FROM investments')
    count = cursor.fetchone()[0]

    # Insert sample data only if table is empty
    if count == 0:
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

        print(f"✅ Database initialized at: {db_path}")
        print(f"✅ Created {len(sample_investments)} sample investments")
    else:
        print(f"✅ Database already exists at: {db_path}")
        print(f"✅ Found {count} existing investments")

    conn.commit()
    conn.close()

    return db_path

if __name__ == '__main__':
    db_path = init_database()
    print(f"\n🎉 Database ready to use!")
    print(f"📁 Location: {db_path}")

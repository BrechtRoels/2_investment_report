from flask import Flask, render_template, jsonify, request, redirect, url_for, session, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os
import re
import json
import yfinance as yf
import pandas as pd
import xml.etree.ElementTree as ET
import urllib.request
from werkzeug.security import check_password_hash
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: SUPABASE_URL and SUPABASE_KEY environment variables not set!")
    print("Please set these in Vercel Environment Variables or your local .env file")
    supabase = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from io import BytesIO

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    try:
        response = supabase.table("Users").select("*").eq("UserID", user_id).execute()
        if response.data and len(response.data) > 0:
            user_data = response.data[0]
            return User(user_data['UserID'], user_data.get('Username', ''))
        return None
    except Exception as e:
        print(f"Error loading user: {e}")
        return None

def parse_price(price_str):
    """Parse price string with currency symbols (e.g., '€174.60') to float"""
    if not price_str:
        return 0.0

    if isinstance(price_str, (int, float)):
        return float(price_str)

    # Remove currency symbols and keep only digits, dots, and commas
    price_clean = ''.join(c for c in str(price_str) if c.isdigit() or c in '.,')

    if not price_clean:
        return 0.0

    # Handle European format (1.234,56) vs US format (1,234.56)
    if ',' in price_clean and '.' in price_clean:
        # Determine format by position
        comma_pos = price_clean.rfind(',')
        dot_pos = price_clean.rfind('.')
        if comma_pos > dot_pos:
            # European format: 1.234,56 -> 1234.56
            price_clean = price_clean.replace('.', '').replace(',', '.')
        else:
            # US format: 1,234.56 -> 1234.56
            price_clean = price_clean.replace(',', '')
    elif ',' in price_clean:
        # Could be either 1,56 (European) or 1,234 (US)
        # Assume European if only 2 digits after comma
        parts = price_clean.split(',')
        if len(parts[-1]) == 2:
            price_clean = price_clean.replace(',', '.')
        else:
            price_clean = price_clean.replace(',', '')

    try:
        return float(price_clean)
    except ValueError:
        return 0.0

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        try:
            # Check if supabase is configured
            if supabase is None:
                print("ERROR: Supabase not configured. Check SUPABASE_URL and SUPABASE_KEY environment variables.")
                return jsonify({'success': False, 'message': 'Database not configured. Please check server configuration.'}), 500

            # Query user from database
            response = supabase.table("Users").select("*").eq("Username", username).execute()

            if response.data and len(response.data) > 0:
                user_data = response.data[0]
                stored_password = user_data.get('Password', '')

                # Check password (plain text comparison for now)
                # TODO: In production, use hashed passwords with check_password_hash
                if password == stored_password:
                    user = User(user_data['UserID'], user_data['Username'])
                    login_user(user)
                    return jsonify({'success': True, 'message': 'Login successful'})

            return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

        except Exception as e:
            print(f"Login error: {e}")
            return jsonify({'success': False, 'message': 'An error occurred'}), 500

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('dashboard.html')

@app.route('/holdings')
@login_required
def holdings():
    return render_template('holdings.html')

@app.route('/transactions')
@login_required
def transactions():
    return render_template('transactions.html')

@app.route('/dividends')
@login_required
def dividends():
    return render_template('dividends.html')

@app.route('/money-invested')
@login_required
def money_invested():
    return render_template('money_invested.html')

@app.route('/capital-gains-tax')
@login_required
def capital_gains_tax():
    return render_template('capital_gains_tax.html')

@app.route('/api/capital-gains-tax')
@login_required
def get_capital_gains_tax():
    """Calculate capital gains tax based on Dec 31, 2025 baseline"""
    try:
        # Get all transactions for current user
        response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).execute()
        transactions = response.data

        holdings = {}

        # Calculate current holdings
        for txn in transactions:
            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)
            currency = txn.get('CURRENCY_BEFORE', 'EUR')

            if not ticker:
                continue

            if ticker not in holdings:
                holdings[ticker] = {
                    'name': txn.get('NAME', ticker),
                    'ticker': ticker,
                    'quantity': 0,
                    'currency': currency
                }

            if action in ['BUY', 'PURCHASE']:
                holdings[ticker]['quantity'] += quantity
            elif action in ['SELL', 'SALE', 'SOLD']:
                holdings[ticker]['quantity'] -= quantity

        # Calculate tax for each holding
        tax_calculations = []
        total_capital_gains = 0

        baseline_date = '2025-12-31'

        for ticker, holding in holdings.items():
            if holding['quantity'] <= 0:
                continue

            # Get the stock's actual currency based on ticker
            stock_currency = get_ticker_currency(ticker)
            print(f"[CAPITAL GAINS] {ticker}: Stock currency is {stock_currency}")

            # Get baseline price (Dec 31, 2025) - returns price in original currency
            baseline_price_original = get_historical_price(ticker, baseline_date)

            # Get current price - NOTE: fetch_live_price already converts to EUR
            # So we need to get the raw price for proper comparison
            current_price_original = get_current_price_raw(ticker)

            if baseline_price_original is None or current_price_original is None:
                continue

            # Get exchange rates for currency conversion based on stock's actual currency
            baseline_exchange_rate = get_historical_exchange_rate(stock_currency, 'EUR', baseline_date) if stock_currency != 'EUR' else 1.0
            current_exchange_rate = get_exchange_rate(stock_currency, 'EUR') if stock_currency != 'EUR' else 1.0

            # Convert to EUR
            baseline_price_eur = baseline_price_original * baseline_exchange_rate
            current_price_eur = current_price_original * current_exchange_rate

            print(f"[CAPITAL GAINS] {ticker}: Baseline {baseline_price_original} {stock_currency} = {baseline_price_eur:.2f} EUR (rate: {baseline_exchange_rate})")
            print(f"[CAPITAL GAINS] {ticker}: Current {current_price_original} {stock_currency} = {current_price_eur:.2f} EUR (rate: {current_exchange_rate})")

            # Calculate capital gain per share and total
            capital_gain_per_share = current_price_eur - baseline_price_eur
            total_capital_gain = capital_gain_per_share * holding['quantity']

            total_capital_gains += total_capital_gain

            tax_calculations.append({
                'ticker': ticker,
                'name': holding['name'],
                'quantity': holding['quantity'],
                'currency': stock_currency,
                'baseline_price': round(baseline_price_eur, 2),
                'current_price': round(current_price_eur, 2),
                'baseline_value': round(baseline_price_eur * holding['quantity'], 2),
                'current_value': round(current_price_eur * holding['quantity'], 2),
                'capital_gain': round(total_capital_gain, 2)
            })

        # Calculate tax
        tax_free_allowance = 10000
        taxable_amount = max(0, total_capital_gains - tax_free_allowance)
        estimated_tax = taxable_amount * 0.10

        return jsonify({
            'holdings': tax_calculations,
            'total_capital_gains': round(total_capital_gains, 2),
            'tax_free_allowance': tax_free_allowance,
            'taxable_amount': round(taxable_amount, 2),
            'estimated_tax': round(estimated_tax, 2),
            'exceeds_allowance': total_capital_gains > tax_free_allowance
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_historical_price(ticker, date):
    """Get historical price for a specific date"""
    try:
        stock = yf.Ticker(ticker)
        # Get data for the specific date (need a range)
        start_date = datetime.strptime(date, '%Y-%m-%d')
        end_date = start_date + timedelta(days=5)  # Get a few days to handle weekends

        hist = stock.history(start=start_date, end=end_date)

        if not hist.empty:
            # Get the first available price (handles weekends/holidays)
            return float(hist['Close'].iloc[0])

        return None
    except Exception as e:
        print(f"Error fetching historical price for {ticker} on {date}: {e}")
        return None

def get_current_price_raw(ticker):
    """Get current price in original currency (no EUR conversion)"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")

        if not hist.empty:
            return float(hist['Close'].iloc[-1])

        return None
    except Exception as e:
        print(f"Error fetching current raw price for {ticker}: {e}")
        return None

def get_historical_exchange_rate(from_currency, to_currency, date):
    """Get historical exchange rate for a specific date"""
    if from_currency == to_currency:
        return 1.0

    try:
        pair = f"{from_currency}{to_currency}=X"
        forex = yf.Ticker(pair)

        start_date = datetime.strptime(date, '%Y-%m-%d')
        end_date = start_date + timedelta(days=5)

        hist = forex.history(start=start_date, end=end_date)

        if not hist.empty:
            return float(hist['Close'].iloc[0])

        return 1.0
    except Exception as e:
        print(f"Error fetching historical exchange rate for {pair} on {date}: {e}")
        return 1.0

def get_exchange_rate(from_currency, to_currency='EUR'):
    """Get exchange rate with database caching"""
    if from_currency == to_currency:
        return 1.0

    pair = f"{from_currency}{to_currency}=X"
    today = datetime.now().date()

    try:
        # Check if we have the most recent exchange rate in the database
        response = supabase.table("StockPrices").select("StockPrice, Date").eq("Ticker", pair).order("Date", desc=True).limit(1).execute()

        if response.data:
            last_record = response.data[0]
            last_date = datetime.fromisoformat(last_record['Date'].replace('Z', '+00:00')).date()
            days_since_update = (today - last_date).days

            # If we have today's rate, use it
            if last_date == today:
                print(f"[CACHE] {pair}: Using cached exchange rate from {last_date}")
                return float(last_record['StockPrice'])
            # If today is weekend/holiday and we have recent data (within 3 days), use it
            elif not is_market_open_day(today) and days_since_update <= 3:
                print(f"[CACHE] {pair}: Market closed, using last rate from {last_date}")
                return float(last_record['StockPrice'])
            # If it's a weekday and data is stale, try to fetch new data
            elif is_market_open_day(today) and days_since_update > 0:
                rate = fetch_and_cache_price(pair, last_date)
                if rate is not None:
                    return rate
                # Fallback to last known rate
                print(f"[FALLBACK] {pair}: Using last known rate from {last_date}")
                return float(last_record['StockPrice'])
            else:
                # Use cached rate if it's recent enough
                print(f"[CACHE] {pair}: Using recent rate from {last_date}")
                return float(last_record['StockPrice'])
        else:
            # No data in database, fetch from yfinance
            rate = fetch_and_cache_price(pair, today - timedelta(days=30))
            if rate is not None:
                return rate

    except Exception as e:
        print(f"Error fetching exchange rate for {from_currency} to {to_currency}: {e}")

    # Fallback rates if all else fails (updated Jan 2026)
    fallback_rates = {
        'USD': 0.86,  # 1 USD = 0.86 EUR
        'GBP': 1.20,  # 1 GBP = 1.20 EUR
        'JPY': 0.0057, # 1 JPY = 0.0057 EUR
        'CHF': 0.98,  # 1 CHF = 0.98 EUR
        'CAD': 0.61,  # 1 CAD = 0.61 EUR
        'AUD': 0.55,  # 1 AUD = 0.55 EUR
    }

    return fallback_rates.get(from_currency, 1.0)

def is_market_open_day(date):
    """Check if the date is likely a trading day (Monday-Friday)"""
    # 0 = Monday, 6 = Sunday
    return date.weekday() < 5

def get_ticker_currency(ticker):
    """Determine the currency for a ticker symbol based on exchange suffix"""
    # Infer from ticker suffix (most reliable method)
    if ticker.endswith('.AS') or ticker.endswith('.PA') or ticker.endswith('.BR') or ticker.endswith('.MI') or ticker.endswith('.DE') or ticker.endswith('.AT') or ticker.endswith('.SW'):
        return 'EUR'
    elif ticker.endswith('.L') or ticker.endswith('.LON'):
        return 'GBP'
    elif ticker.endswith('.T') or ticker.endswith('.TYO'):
        return 'JPY'

    # For tickers without suffix (US stocks), default to USD
    if '.' not in ticker:
        return 'USD'

    # For unknown suffixes, try yfinance as fallback
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        currency = info.get('currency', None)
        if currency:
            print(f"[CURRENCY] {ticker}: Detected {currency} from yfinance")
            return currency
    except Exception as e:
        print(f"[CURRENCY] {ticker}: Failed to get currency from yfinance: {e}")

    # Ultimate fallback
    return 'USD'

def fetch_live_price(ticker):
    """Fetch live stock price with database caching and currency conversion to EUR"""
    try:
        today = datetime.now().date()

        # First, determine the currency of this stock
        currency = get_ticker_currency(ticker)
        print(f"[CURRENCY] {ticker}: Using currency {currency}")

        # 1. Check if we have the most recent price in the database
        response = supabase.table("StockPrices").select("StockPrice, Date").eq("Ticker", ticker).order("Date", desc=True).limit(1).execute()

        if response.data:
            last_record = response.data[0]
            last_date = datetime.fromisoformat(last_record['Date'].replace('Z', '+00:00')).date()

            # Calculate days since last update
            days_since_update = (today - last_date).days

            # If we have today's price, use it
            if last_date == today:
                price_in_original_currency = float(last_record['StockPrice'])
                print(f"[CACHE] {ticker}: Using cached price from {last_date}")
            # If today is weekend/holiday and we have recent data (within 3 days), use it
            elif not is_market_open_day(today) and days_since_update <= 3:
                price_in_original_currency = float(last_record['StockPrice'])
                print(f"[CACHE] {ticker}: Market closed, using last price from {last_date}")
            # If it's a weekday and data is stale, try to fetch new data
            elif is_market_open_day(today) and days_since_update > 0:
                price_in_original_currency = fetch_and_cache_price(ticker, last_date, currency)
                if price_in_original_currency is None:
                    # If fetch fails, use last known price
                    price_in_original_currency = float(last_record['StockPrice'])
                    print(f"[FALLBACK] {ticker}: Using last known price from {last_date}")
            else:
                # Use cached price if it's recent enough
                price_in_original_currency = float(last_record['StockPrice'])
                print(f"[CACHE] {ticker}: Using recent price from {last_date}")
        else:
            # No data in database, fetch from yfinance
            price_in_original_currency = fetch_and_cache_price(ticker, today - timedelta(days=5*365), currency)
            if price_in_original_currency is None:
                return None

        # Convert to EUR if not already in EUR
        if currency != 'EUR':
            exchange_rate = get_exchange_rate(currency, 'EUR')
            price_in_eur = price_in_original_currency * exchange_rate
            print(f"{ticker}: {price_in_original_currency} {currency} = {price_in_eur:.2f} EUR (rate: {exchange_rate})")
            return price_in_eur

        return price_in_original_currency

    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None

def fetch_and_cache_price(ticker, start_date, currency=None):
    """Fetch price data from yfinance and cache in database"""
    try:
        print(f"[FETCH] {ticker}: Fetching from yfinance since {start_date}...")

        # Get currency if not provided
        if currency is None:
            currency = get_ticker_currency(ticker)

        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date)

        if hist.empty:
            return None

        # Get existing dates for this ticker from database to avoid duplicates
        existing_response = supabase.table("StockPrices").select("Date").eq("Ticker", ticker).gte("Date", start_date.isoformat()).execute()

        existing_dates = set()
        if existing_response.data:
            existing_dates = {datetime.fromisoformat(r['Date'].replace('Z', '+00:00')).date() for r in existing_response.data}

        # Prepare records for bulk insert, excluding existing dates
        records = []
        for date, row in hist.iterrows():
            date_only = date.date()
            if date_only not in existing_dates:
                records.append({
                    "Date": date.isoformat(),
                    "Ticker": ticker,
                    "StockPrice": float(row['Close']),
                    "Currency": currency
                })

        # Bulk insert to database only if there are new records
        if records:
            supabase.table("StockPrices").insert(records).execute()
            print(f"[CACHE] {ticker}: Stored {len(records)} new price records in database")
        else:
            print(f"[CACHE] {ticker}: All prices already in database, no new records added")

        # Return the most recent price
        return float(hist['Close'].iloc[-1])

    except Exception as e:
        print(f"Error fetching and caching price for {ticker}: {e}")
        # Still return the price if we fetched it, even if caching failed
        try:
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except:
            pass
        return None

@app.route('/api/portfolio')
@login_required
def get_portfolio():
    """Get portfolio summary from Transactions table with live prices"""
    try:
        response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).execute()

        transactions = response.data

        holdings = {}

        for txn in transactions:
            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)
            price = parse_price(txn.get('PRICE'))
            total_purchase_price = parse_price(txn.get('TOTAL PURCHASE PRICE', 0))

            # Get currency info for FX impact calculation
            currency_from = txn.get('CURRENCY FROM', 'EUR')
            exchange_rate_at_purchase = parse_price(txn.get('EXCHANGE RATE', 1.0)) or 1.0
            price_before_currency = parse_price(txn.get('PRICE BEFORE CURRENCY', 0)) or price

            if not ticker:
                continue

            if ticker not in holdings:
                holdings[ticker] = {
                    'name': txn.get('NAME', ticker),
                    'ticker': ticker,
                    'total_shares': 0,
                    'total_cost': 0,
                    'transactions': [],
                    'currency_from': currency_from,
                    'original_prices': []  # Store original prices in foreign currency
                }

            if action in ['BUY', 'PURCHASE']:
                holdings[ticker]['total_shares'] += quantity
                # Use actual TOTAL PURCHASE PRICE from database (includes fees)
                holdings[ticker]['total_cost'] += total_purchase_price if total_purchase_price > 0 else (quantity * price)

                # Store original purchase info for FX calculation
                holdings[ticker]['original_prices'].append({
                    'quantity': quantity,
                    'price_foreign': price_before_currency if price_before_currency > 0 else price,
                    'exchange_rate': exchange_rate_at_purchase,
                    'currency': currency_from
                })
            elif action in ['SELL', 'SALE', 'SOLD']:
                holdings[ticker]['total_shares'] -= quantity

            holdings[ticker]['transactions'].append({
                'date': txn.get('DATE'),
                'action': action,
                'quantity': quantity,
                'price': price,
                'total_purchase_price': total_purchase_price
            })

        investments = []
        total_value = 0
        total_cost = 0

        for ticker, holding in holdings.items():
            if holding['total_shares'] <= 0:
                continue

            avg_purchase_price = holding['total_cost'] / holding['total_shares'] if holding['total_shares'] > 0 else 0

            # Fetch live price for active holdings
            live_price = fetch_live_price(ticker)

            if live_price is not None:
                current_price = live_price
            else:
                # Fallback to last transaction price if live price unavailable
                last_price = 0
                for txn in reversed(holding['transactions']):
                    if txn['price'] > 0:
                        last_price = txn['price']
                        break
                current_price = last_price if last_price > 0 else avg_purchase_price

            current_value = holding['total_shares'] * current_price
            cost = holding['total_cost']
            change_percent = ((current_price - avg_purchase_price) / avg_purchase_price * 100) if avg_purchase_price > 0 else 0

            # Calculate absolute gain/loss
            absolute_gain_loss = current_value - cost

            # Calculate FX impact for non-EUR stocks
            fx_impact = 0
            currency_from = holding.get('currency_from', 'EUR')

            if currency_from != 'EUR' and holding.get('original_prices'):
                # Get current exchange rate
                current_fx_rate = get_exchange_rate(currency_from, 'EUR')

                # Calculate what the value would be with original exchange rate vs current
                for purchase in holding['original_prices']:
                    original_rate = purchase['exchange_rate']
                    price_foreign = purchase['price_foreign']
                    qty = purchase['quantity']

                    # Value with original exchange rate
                    value_at_original_rate = price_foreign * original_rate * qty

                    # Value with current exchange rate (if we still had it at purchase price)
                    value_at_current_rate = price_foreign * current_fx_rate * qty

                    # FX impact is the difference
                    fx_impact += (value_at_current_rate - value_at_original_rate)

            investments.append({
                'id': ticker,
                'name': holding['name'],
                'symbol': ticker,
                'shares': holding['total_shares'],
                'purchase_price': round(avg_purchase_price, 2),
                'current_price': round(current_price, 2),
                'change': round(change_percent, 2),
                'value': round(current_value, 2),
                'absolute_gain_loss': round(absolute_gain_loss, 2),
                'fx_impact': round(fx_impact, 2),
                'currency': currency_from
            })

            total_value += current_value
            total_cost += cost

        # Get total deposits and refunds from MoneyInvested table
        money_invested_response = supabase.table("MoneyInvested").select("*").eq("UserID", current_user.id).execute()
        money_invested = money_invested_response.data

        total_deposits = 0
        total_refunds = 0
        total_withdrawals = 0
        for record in money_invested:
            action = record.get('ACTION', '').upper()
            amount = parse_price(record.get('AMOUNT', 0)) or 0

            if action == 'DEPOSIT':
                total_deposits += amount
            elif action == 'REFUND':
                total_refunds += amount
            elif action == 'WITHDRAW':
                total_withdrawals += amount

        # Get total dividends received
        dividends_response = supabase.table("Dividend").select("*").eq("UserID", current_user.id).execute()
        dividends = dividends_response.data

        total_dividends = 0
        for div in dividends:
            net_dividend = float(div.get('TOTAL_DIVIDEND', 0) or 0)
            total_dividends += net_dividend

        # Calculate cash spent on stocks (from transactions)
        cash_spent_on_stocks = 0
        cash_from_sales = 0
        for txn in transactions:
            action = txn.get('ACTION', '').upper()
            total_purchase_price = parse_price(txn.get('TOTAL PURCHASE PRICE', 0))

            if action in ['BUY', 'PURCHASE']:
                cash_spent_on_stocks += total_purchase_price
            elif action in ['SELL', 'SALE', 'SOLD']:
                # For sales, the total purchase price is actually the proceeds
                cash_from_sales += total_purchase_price

        # Calculate current cash position
        # Cash In: Deposits + Refunds + Dividends + Stock Sales
        # Cash Out: Stock Purchases (including fees) + Withdrawals
        cash_in = total_deposits + total_refunds + total_dividends + cash_from_sales
        cash_out = cash_spent_on_stocks + total_withdrawals
        cash_position = cash_in - cash_out

        # Calculate gain based on deposits (not transaction costs)
        total_gain = total_value - total_deposits
        gain_percentage = (total_gain / total_deposits * 100) if total_deposits > 0 else 0

        return jsonify({
            'investments': investments,
            'total_value': round(total_value, 2),
            'cash_position': round(cash_position, 2),
            'total_invested': round(total_deposits, 2),
            'total_gain': round(total_gain, 2),
            'gain_percentage': round(gain_percentage, 2)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/investments', methods=['POST'])
def add_investment():
    """Add a new transaction (buy)"""
    data = request.json

    try:
        response = supabase.table("Transactions").select("TransactionID").order("TransactionID", desc=True).limit(1).execute()

        next_id = 1
        if response.data and len(response.data) > 0:
            next_id = response.data[0]['TransactionID'] + 1

        shares = int(data['shares'])
        purchase_price = float(data['purchase_price'])

        new_transaction = {
            'TransactionID': next_id,
            'DATE': datetime.now().strftime('%Y-%m-%d'),
            'TICKER': data['symbol'].upper(),
            'NAME': data['name'],
            'ACTION': 'BUY',
            'PRICE BEFORE CURRENCY': data.get('price_before_currency', ''),
            'CURRENCY FROM': data.get('currency_from', ''),
            'EXCHANGE RATE': data.get('exchange_rate', ''),
            'CURRENCY TO': data.get('currency_to', 'EUR'),
            'PRICE': str(purchase_price),
            'QUANTITY': shares,
            'TOTAL AMOUNT BT': data.get('total_amount_bt', ''),
            'BROKERAGE FEE': data.get('brokerage_fee', ''),
            'STOCK MARKET FEE': data.get('stock_market_fee', ''),
            'TOTAL PURCHASE PRICE': str(shares * purchase_price),
            'UserID': 1
        }

        supabase.table("Transactions").insert(new_transaction).execute()

        return jsonify({'success': True, 'id': next_id, 'message': 'Investment added successfully'}), 201

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/investments/<string:ticker>', methods=['PUT'])
def update_investment(ticker):
    """Update an investment by adding a new transaction"""
    data = request.json

    try:
        response = supabase.table("Transactions").select("TransactionID").order("TransactionID", desc=True).limit(1).execute()

        next_id = 1
        if response.data and len(response.data) > 0:
            next_id = response.data[0]['TransactionID'] + 1

        shares = int(data['shares'])
        price = float(data['current_price'])

        new_transaction = {
            'TransactionID': next_id,
            'DATE': datetime.now().strftime('%Y-%m-%d'),
            'TICKER': ticker.upper(),
            'NAME': data['name'],
            'ACTION': 'UPDATE',
            'PRICE BEFORE CURRENCY': data.get('price_before_currency', ''),
            'CURRENCY FROM': data.get('currency_from', ''),
            'EXCHANGE RATE': data.get('exchange_rate', ''),
            'CURRENCY TO': data.get('currency_to', 'EUR'),
            'PRICE': str(price),
            'QUANTITY': shares,
            'TOTAL AMOUNT BT': data.get('total_amount_bt', ''),
            'BROKERAGE FEE': data.get('brokerage_fee', ''),
            'STOCK MARKET FEE': data.get('stock_market_fee', ''),
            'TOTAL PURCHASE PRICE': str(shares * price),
            'UserID': 1
        }

        supabase.table("Transactions").insert(new_transaction).execute()

        return jsonify({'success': True, 'message': 'Investment updated successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/investments/<string:ticker>', methods=['DELETE'])
def delete_investment(ticker):
    """Delete all transactions for a ticker"""
    try:
        supabase.table("Transactions").delete().eq("TICKER", ticker.upper()).execute()

        return jsonify({'success': True, 'message': 'Investment deleted successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/investments/<string:ticker>/sell', methods=['POST'])
def sell_investment(ticker):
    """Sell shares of an investment"""
    data = request.json

    try:
        response = supabase.table("Transactions").select("*").eq("TICKER", ticker.upper()).execute()

        total_shares = 0
        for txn in response.data:
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)
            if action in ['BUY', 'PURCHASE']:
                total_shares += quantity
            elif action in ['SELL', 'SALE', 'SOLD']:
                total_shares -= quantity

        shares_to_sell = int(data['shares'])

        if shares_to_sell > total_shares:
            return jsonify({
                'success': False,
                'message': f'Cannot sell {shares_to_sell} shares. Only {total_shares} shares available.'
            }), 400

        response = supabase.table("Transactions").select("TransactionID").order("TransactionID", desc=True).limit(1).execute()

        next_id = 1
        if response.data and len(response.data) > 0:
            next_id = response.data[0]['TransactionID'] + 1

        sell_price = float(data['price'])
        notes = data.get('notes', 'Stock sale')

        ticker_info = supabase.table("Transactions").select("NAME").eq("TICKER", ticker.upper()).limit(1).execute()
        name = ticker_info.data[0]['NAME'] if ticker_info.data else ticker.upper()

        new_transaction = {
            'TransactionID': next_id,
            'DATE': datetime.now().strftime('%Y-%m-%d'),
            'TICKER': ticker.upper(),
            'NAME': name,
            'ACTION': 'SELL',
            'PRICE BEFORE CURRENCY': '',
            'CURRENCY FROM': '',
            'EXCHANGE RATE': '',
            'CURRENCY TO': 'EUR',
            'PRICE': str(sell_price),
            'QUANTITY': shares_to_sell,
            'TOTAL AMOUNT BT': '',
            'BROKERAGE FEE': '',
            'STOCK MARKET FEE': '',
            'TOTAL PURCHASE PRICE': str(shares_to_sell * sell_price),
            'UserID': 1
        }

        supabase.table("Transactions").insert(new_transaction).execute()

        remaining_shares = total_shares - shares_to_sell

        if remaining_shares == 0:
            message = f'All shares sold successfully'
        else:
            message = f'{shares_to_sell} shares sold successfully. {remaining_shares} shares remaining.'

        return jsonify({'success': True, 'message': message})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/portfolio-statistics')
@login_required
def get_portfolio_statistics():
    """Get portfolio statistics: fees, taxes, and deposits"""
    try:
        # Get all transactions for fees
        transactions_response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).execute()
        transactions = transactions_response.data

        # Get all dividends for taxes/fees
        dividends_response = supabase.table("Dividend").select("*").eq("UserID", current_user.id).execute()
        dividends = dividends_response.data

        # Get all money invested records for deposits
        money_invested_response = supabase.table("MoneyInvested").select("*").eq("UserID", current_user.id).execute()
        money_invested = money_invested_response.data

        # Calculate transaction fees
        total_brokerage_fees = 0
        total_stock_market_fees = 0

        for txn in transactions:
            brokerage_fee = parse_price(txn.get('BROKERAGE FEE', 0)) or 0
            stock_market_fee = parse_price(txn.get('STOCK MARKET FEE', 0)) or 0

            total_brokerage_fees += brokerage_fee
            total_stock_market_fees += stock_market_fee

        # Calculate dividend taxes and fees
        total_withholding_tax = 0
        total_foreign_tax = 0
        total_collection_fee = 0
        total_vat = 0

        for div in dividends:
            withholding_tax = float(div.get('ROERENDE VOORHEFFING', 0) or 0)
            foreign_tax = float(div.get('BUITENLANDSE BRONHEFFING', 0) or 0)
            collection_fee = float(div.get('KOSTEN INCASSOSTELLING', 0) or 0)
            vat = float(div.get('BTW', 0) or 0)

            total_withholding_tax += withholding_tax
            total_foreign_tax += foreign_tax
            total_collection_fee += collection_fee
            total_vat += vat

        # Calculate total deposits
        total_deposits = 0

        for record in money_invested:
            action = record.get('ACTION', '').upper()
            amount = parse_price(record.get('AMOUNT', 0)) or 0

            if action == 'DEPOSIT':
                total_deposits += amount

        # Calculate totals
        total_transaction_fees = total_brokerage_fees + total_stock_market_fees
        total_dividend_fees = total_collection_fee + total_vat
        total_taxes = total_withholding_tax + total_foreign_tax
        total_fees_and_taxes = total_transaction_fees + total_dividend_fees + total_taxes

        statistics = {
            'transaction_fees': {
                'brokerage_fees': round(total_brokerage_fees, 2),
                'stock_market_fees': round(total_stock_market_fees, 2),
                'total': round(total_transaction_fees, 2)
            },
            'dividend_fees': {
                'collection_fees': round(total_collection_fee, 2),
                'vat': round(total_vat, 2),
                'total': round(total_dividend_fees, 2)
            },
            'taxes': {
                'withholding_tax': round(total_withholding_tax, 2),
                'foreign_tax': round(total_foreign_tax, 2),
                'total': round(total_taxes, 2)
            },
            'totals': {
                'total_deposits': round(total_deposits, 2),
                'total_fees': round(total_transaction_fees + total_dividend_fees, 2),
                'total_taxes': round(total_taxes, 2),
                'total_fees_and_taxes': round(total_fees_and_taxes, 2)
            }
        }

        return jsonify(statistics)

    except Exception as e:
        print(f"Error in portfolio statistics: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart-data')
@login_required
def get_chart_data():
    """Generate portfolio value history from transactions - optimized version"""
    try:
        # Get all transactions for current user
        response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).order("DATE").execute()
        transactions = response.data

        if not transactions:
            return jsonify([])

        # Build holdings over time (only on transaction dates)
        holdings_timeline = {}
        current_holdings = {}

        for txn in transactions:
            date = txn.get('DATE')
            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)
            total_cost = parse_price(txn.get('TOTAL PURCHASE PRICE', 0))

            if not ticker or not date:
                continue

            if ticker not in current_holdings:
                current_holdings[ticker] = {'shares': 0, 'total_cost': 0}

            if action in ['BUY', 'PURCHASE']:
                current_holdings[ticker]['shares'] += quantity
                current_holdings[ticker]['total_cost'] += total_cost
            elif action in ['SELL', 'SALE', 'SOLD']:
                # Calculate average cost for sold shares
                if current_holdings[ticker]['shares'] > 0:
                    avg_cost = current_holdings[ticker]['total_cost'] / current_holdings[ticker]['shares']
                    current_holdings[ticker]['shares'] -= quantity
                    current_holdings[ticker]['total_cost'] -= (avg_cost * quantity)

            # Take snapshot at this date (store total cost, not price)
            holdings_timeline[date] = {
                ticker: {'shares': data['shares'], 'total_cost': data['total_cost']}
                for ticker, data in current_holdings.items()
                if data['shares'] > 0
            }

        # Convert to simple data points (date and cost-based value)
        data = []
        for date in sorted(holdings_timeline.keys()):
            total_value = sum(h['total_cost'] for h in holdings_timeline[date].values())
            data.append({
                'date': date,
                'value': round(total_value, 2)
            })

        # If we have data, add current market value as the last point
        if data:
            # Get current portfolio value
            current_holdings_active = {t: h for t, h in current_holdings.items() if h['shares'] > 0}
            current_market_value = 0

            for ticker, holding in current_holdings_active.items():
                live_price = fetch_live_price(ticker)
                if live_price:
                    current_market_value += live_price * holding['shares']
                else:
                    # Fallback to cost if no live price
                    current_market_value += holding['total_cost']

            # Add today's market value
            data.append({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'value': round(current_market_value, 2)
            })

        return jsonify(data)

    except Exception as e:
        print(f"Error in chart-data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/realized-holdings')
@login_required
def get_realized_holdings():
    """Get realized holdings (sold stocks) with their gains/losses"""
    try:
        response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).order("DATE").execute()
        transactions = response.data

        # Group transactions by ticker
        ticker_transactions = {}

        for txn in transactions:
            ticker = txn.get('TICKER')
            if not ticker:
                continue

            if ticker not in ticker_transactions:
                ticker_transactions[ticker] = {
                    'name': txn.get('NAME', ticker),
                    'buys': [],
                    'sells': []
                }

            action = txn.get('ACTION', '').upper()

            if action in ['BUY', 'PURCHASE']:
                ticker_transactions[ticker]['buys'].append(txn)
            elif action in ['SELL', 'SALE', 'SOLD']:
                ticker_transactions[ticker]['sells'].append(txn)

        # Calculate realized gains for each ticker (aggregated across all sells)
        realized_holdings = []

        for ticker, data in ticker_transactions.items():
            # Skip tickers with no sells
            if not data['sells']:
                continue

            # Calculate total purchase cost for this ticker
            total_purchase_cost = 0
            total_shares_bought = 0

            for buy_txn in data['buys']:
                total_purchase_price = parse_price(buy_txn.get('TOTAL PURCHASE PRICE', '0'))
                total_purchase_cost += total_purchase_price
                total_shares_bought += buy_txn.get('QUANTITY', 0)

            print(f"\n{'='*60}")
            print(f"Ticker: {ticker}")
            print(f"Total shares bought: {total_shares_bought}")
            print(f"Total purchase cost: €{total_purchase_cost}")

            # Aggregate all sells for this ticker
            total_shares_sold = 0
            total_proceeds_all_sells = 0
            latest_sale_date = None
            weighted_sale_price = 0

            for sell_txn in data['sells']:
                shares_sold = sell_txn.get('QUANTITY', 0)
                sale_price = parse_price(sell_txn.get('PRICE', '0'))
                proceeds = parse_price(sell_txn.get('TOTAL PURCHASE PRICE', '0'))
                sale_date = sell_txn.get('DATE')

                total_shares_sold += shares_sold
                total_proceeds_all_sells += proceeds
                weighted_sale_price += shares_sold * sale_price

                # Track the latest sale date
                if latest_sale_date is None or sale_date > latest_sale_date:
                    latest_sale_date = sale_date

                print(f"\nSELL on {sale_date}:")
                print(f"  Shares sold: {shares_sold}")
                print(f"  Sale price: €{sale_price}")
                print(f"  Proceeds: €{proceeds}")

            # Calculate average sale price
            avg_sale_price = (weighted_sale_price / total_shares_sold) if total_shares_sold > 0 else 0

            # Calculate total cost basis as proportional to total shares sold
            if total_shares_bought > 0:
                total_cost_basis = (total_shares_sold / total_shares_bought) * total_purchase_cost
            else:
                total_cost_basis = 0

            total_realized_gain = total_proceeds_all_sells - total_cost_basis
            total_realized_gain_percent = (total_realized_gain / total_cost_basis * 100) if total_cost_basis > 0 else 0

            print(f"\nAGGREGATED TOTALS:")
            print(f"  Total shares sold: {total_shares_sold}")
            print(f"  Average sale price: €{avg_sale_price}")
            print(f"  Total proceeds: €{total_proceeds_all_sells}")
            print(f"  Total cost basis: €{total_cost_basis}")
            print(f"  Total realized gain: €{total_realized_gain}")
            print(f"  Realized gain %: {total_realized_gain_percent}%")

            realized_holdings.append({
                'ticker': ticker,
                'name': data['name'],
                'shares_sold': total_shares_sold,
                'sale_price': round(avg_sale_price, 2),
                'sale_date': latest_sale_date,
                'cost_basis': round(total_cost_basis, 2),
                'proceeds': round(total_proceeds_all_sells, 2),
                'realized_gain': round(total_realized_gain, 2),
                'realized_gain_percent': round(total_realized_gain_percent, 2),
                'complete_exit': total_shares_bought == total_shares_sold
            })

            print(f"{'='*60}\n")

        # Sort by latest sale date (most recent first)
        realized_holdings.sort(key=lambda x: x['sale_date'], reverse=True)

        # Calculate totals
        total_proceeds = sum(h['proceeds'] for h in realized_holdings)
        total_cost_basis = sum(h['cost_basis'] for h in realized_holdings)
        total_realized_gain = total_proceeds - total_cost_basis
        total_realized_gain_percent = (total_realized_gain / total_cost_basis * 100) if total_cost_basis > 0 else 0

        return jsonify({
            'realized_holdings': realized_holdings,
            'total_proceeds': round(total_proceeds, 2),
            'total_cost_basis': round(total_cost_basis, 2),
            'total_realized_gain': round(total_realized_gain, 2),
            'total_realized_gain_percent': round(total_realized_gain_percent, 2)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions', methods=['GET', 'POST'])
@login_required
def transactions_api():
    """Get all transactions or add a new one"""
    if request.method == 'GET':
        try:
            response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).order("DATE", desc=True).execute()

            transactions = []
            for txn in response.data:
                price = parse_price(txn.get('PRICE'))
                quantity = txn.get('QUANTITY', 0)

                transactions.append({
                    'id': txn.get('TransactionID'),
                    'transaction_id': txn.get('TransactionID'),  # Add this field for frontend
                    'transaction_type': txn.get('ACTION', '').lower(),
                    'shares': quantity,
                    'price': round(price, 2),
                    'transaction_date': txn.get('DATE'),
                    'notes': txn.get('NAME', ''),
                    'investment_name': txn.get('NAME', ''),
                    'investment_symbol': txn.get('TICKER', ''),
                    'total_value': round(quantity * price, 2),
                    # Additional fields from database
                    'price_before_currency': txn.get('PRICE BEFORE CURRENCY', ''),
                    'currency_from': txn.get('CURRENCY FROM', ''),
                    'exchange_rate': txn.get('EXCHANGE RATE', ''),
                    'currency_to': txn.get('CURRENCY TO', ''),
                    'total_amount_bt': txn.get('TOTAL AMOUNT BT', ''),
                    'brokerage_fee': txn.get('BROKERAGE FEE', ''),
                    'stock_market_fee': txn.get('STOCK MARKET FEE', ''),
                    'total_purchase_price': txn.get('TOTAL PURCHASE PRICE', '')
                })

            return jsonify({'transactions': transactions})

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        data = request.json

        try:
            # Get next TransactionID
            response = supabase.table("Transactions").select("TransactionID").order("TransactionID", desc=True).limit(1).execute()

            next_id = 1
            if response.data and len(response.data) > 0:
                next_id = response.data[0]['TransactionID'] + 1

            # Create new transaction
            new_transaction = {
                'TransactionID': next_id,
                'DATE': data.get('date'),
                'TICKER': data.get('ticker').upper(),
                'NAME': data.get('name'),
                'ACTION': data.get('action').upper(),
                'PRICE BEFORE CURRENCY': data.get('price_before_currency') or None,
                'CURRENCY FROM': data.get('currency_from', ''),
                'EXCHANGE RATE': data.get('exchange_rate') or None,
                'CURRENCY TO': data.get('currency_to', 'EUR'),
                'PRICE': str(data.get('price')),
                'QUANTITY': int(data.get('quantity')),
                'TOTAL AMOUNT BT': data.get('total_amount_bt') or None,
                'BROKERAGE FEE': data.get('brokerage_fee') or None,
                'STOCK MARKET FEE': data.get('stock_market_fee') or None,
                'TOTAL PURCHASE PRICE': str(data.get('total_purchase_price')),
                'UserID': current_user.id
            }

            supabase.table("Transactions").insert(new_transaction).execute()

            return jsonify({'success': True, 'id': next_id, 'message': 'Transaction added successfully'}), 201

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/dividends', methods=['GET', 'POST'])
@login_required
def dividends_api():
    """Get all dividends or add a new dividend"""
    if request.method == 'GET':
        try:
            response = supabase.table("Dividend").select("*").eq("UserID", current_user.id).order("DATE", desc=True).execute()

            dividends = []
            for div in response.data:
                dividends.append({
                    'id': div.get('DividendID'),
                    'date': div.get('DATE'),
                    'ticker': div.get('TICKER'),
                    'name': div.get('NAME'),
                    'is_etf': div.get('ETF') == 1,
                    'gross_amount': float(div.get('VALUE RECEIVED BEFORE TAX', 0)),
                    'foreign_tax': float(div.get('BUITENLANDSE BRONHEFFING', 0)),
                    'collection_fee': float(div.get('KOSTEN INCASSOSTELLING', 0)),
                    'withholding_tax': float(div.get('ROERENDE VOORHEFFING', 0)),
                    'vat': float(div.get('BTW', 0)),
                    'total_dividend': float(div.get('TOTAL_DIVIDEND', 0))
                })

            return jsonify({'dividends': dividends})

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        data = request.json

        try:
            # Get next DividendID
            response = supabase.table("Dividend").select("DividendID").order("DividendID", desc=True).limit(1).execute()

            next_id = 1
            if response.data and len(response.data) > 0:
                next_id = response.data[0]['DividendID'] + 1

            # Create new dividend record
            new_dividend = {
                'DividendID': next_id,
                'DATE': data.get('date'),
                'TICKER': data.get('ticker'),
                'NAME': data.get('name'),
                'ETF': data.get('is_etf', 0),
                'VALUE RECEIVED BEFORE TAX': data.get('gross_amount'),
                'CURRENCY BEFORE': data.get('currency_before', ''),
                'EXCHANGE RATE': data.get('exchange_rate', 0),
                'CURRENCY AFTER': data.get('currency_after', 'EUR'),
                'BUITENLANDSE BRONHEFFING': data.get('foreign_tax', 0),
                'KOSTEN INCASSOSTELLING': data.get('collection_fee', 0),
                'ROERENDE VOORHEFFING': data.get('withholding_tax', 0),
                'BTW': data.get('vat', 0),
                'TOTAL_DIVIDEND': data.get('total_dividend'),
                'UserID': current_user.id
            }

            supabase.table("Dividend").insert(new_dividend).execute()

            return jsonify({'success': True, 'id': next_id, 'message': 'Dividend added successfully'}), 201

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/dividends/<int:dividend_id>', methods=['PUT', 'DELETE'])
@login_required
def dividend_operations(dividend_id):
    """Update or delete a specific dividend"""
    if request.method == 'PUT':
        data = request.json

        try:
            updated_dividend = {
                'DATE': data.get('date'),
                'TICKER': data.get('ticker'),
                'NAME': data.get('name'),
                'ETF': data.get('is_etf', 0),
                'VALUE RECEIVED BEFORE TAX': data.get('gross_amount'),
                'CURRENCY BEFORE': data.get('currency_before', ''),
                'EXCHANGE RATE': data.get('exchange_rate', 0),
                'CURRENCY AFTER': data.get('currency_after', 'EUR'),
                'BUITENLANDSE BRONHEFFING': data.get('foreign_tax', 0),
                'KOSTEN INCASSOSTELLING': data.get('collection_fee', 0),
                'ROERENDE VOORHEFFING': data.get('withholding_tax', 0),
                'BTW': data.get('vat', 0),
                'TOTAL_DIVIDEND': data.get('total_dividend')
            }

            supabase.table("Dividend").update(updated_dividend).eq("DividendID", dividend_id).execute()

            return jsonify({'success': True, 'message': 'Dividend updated successfully'})

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            supabase.table("Dividend").delete().eq("DividendID", dividend_id).execute()

            return jsonify({'success': True, 'message': 'Dividend deleted successfully'})

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions/<int:transaction_id>', methods=['PUT'])
@login_required
def update_transaction(transaction_id):
    """Update an existing transaction"""
    data = request.json

    try:
        # First, verify the transaction exists
        check_response = supabase.table("Transactions").select("TransactionID").eq("TransactionID", transaction_id).execute()

        if not check_response.data:
            return jsonify({'success': False, 'message': f'Transaction with ID {transaction_id} not found'}), 404

        # Prepare updated transaction data with all fields
        updated_transaction = {
            'DATE': data.get('transaction_date'),
            'TICKER': data.get('ticker').upper(),
            'NAME': data.get('name'),
            'ACTION': data.get('action').upper(),
            'PRICE BEFORE CURRENCY': data.get('price_before_currency', ''),
            'CURRENCY FROM': data.get('currency_from', ''),
            'EXCHANGE RATE': data.get('exchange_rate', ''),
            'CURRENCY TO': data.get('currency_to', ''),
            'PRICE': str(data.get('price')),
            'QUANTITY': int(data.get('quantity')),
            'TOTAL AMOUNT BT': data.get('total_amount_bt', ''),
            'BROKERAGE FEE': data.get('brokerage_fee', ''),
            'STOCK MARKET FEE': data.get('stock_market_fee', ''),
            'TOTAL PURCHASE PRICE': data.get('total_purchase_price', '')
            # UserID and TransactionID are not updated
        }

        # Update the transaction in Supabase
        try:
            response = supabase.table("Transactions").update(updated_transaction).eq("TransactionID", transaction_id).execute()

            # Supabase update may return empty data due to RLS policies, but no error means success
            # Verify the update worked by fetching the record again
            verify_response = supabase.table("Transactions").select("TransactionID").eq("TransactionID", transaction_id).execute()

            if verify_response.data:
                return jsonify({'success': True, 'message': 'Transaction updated successfully'})
            else:
                return jsonify({'success': False, 'message': 'Update failed - transaction not found after update'}), 500

        except Exception as update_error:
            return jsonify({'success': False, 'message': f'Update error: {str(update_error)}'}), 500

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/portfolio-history', methods=['GET'])
@login_required
def get_portfolio_history():
    """Get historical portfolio value with optional benchmark comparison"""
    try:
        # Get query parameters
        time_range = request.args.get('range', '1Y')  # 1M, 3M, 6M, 1Y, ALL
        include_benchmarks = request.args.get('benchmarks', '')  # Comma-separated: ^GSPC,^BFX,^STOXX50E

        # Calculate date range
        end_date = datetime.now().date()

        range_map = {
            '1M': timedelta(days=30),
            '3M': timedelta(days=90),
            '6M': timedelta(days=180),
            '1Y': timedelta(days=365),
            'ALL': None
        }

        if time_range == 'ALL':
            # Get earliest transaction date for current user
            response = supabase.table("Transactions").select("DATE").eq("UserID", current_user.id).order("DATE").limit(1).execute()
            if response.data:
                start_date = datetime.fromisoformat(response.data[0]['DATE']).date()
            else:
                start_date = end_date - timedelta(days=365)
        else:
            delta = range_map.get(time_range, timedelta(days=365))
            start_date = end_date - delta

        # Fetch all transactions for current user
        response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).order("DATE").execute()
        transactions = response.data

        # Build portfolio state over time
        holdings_by_date = {}
        current_holdings = {}
        unique_tickers = set()

        for txn in transactions:
            date_str = txn.get('DATE')
            if not date_str:
                continue

            txn_date = datetime.fromisoformat(date_str).date()

            # Only include transactions up to end_date
            if txn_date > end_date:
                continue

            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)

            # Skip invalid or unavailable tickers
            if not ticker or ticker.upper() == 'NOT AVAILABLE' or ticker.strip() == '':
                continue

            unique_tickers.add(ticker)

            if ticker not in current_holdings:
                current_holdings[ticker] = 0

            if action in ['BUY', 'PURCHASE']:
                current_holdings[ticker] += quantity
            elif action in ['SELL', 'SALE', 'SOLD']:
                current_holdings[ticker] -= quantity

            # Store snapshot of holdings at this date
            holdings_by_date[txn_date] = {ticker: shares for ticker, shares in current_holdings.items() if shares > 0}

        # Get all unique dates where we need prices (from start_date to end_date)
        # Create daily snapshots by forward-filling holdings
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)

        # Forward-fill holdings for each day
        last_holdings = {}
        holdings_timeline = {}

        for date in date_range:
            if date in holdings_by_date:
                last_holdings = holdings_by_date[date].copy()
            holdings_timeline[date] = last_holdings.copy()

        # Fetch historical prices for all tickers from cache
        print(f"[PORTFOLIO] Fetching prices for {len(unique_tickers)} tickers from {start_date} to {end_date}")

        ticker_prices = {}
        for ticker in unique_tickers:
            # Query cached prices for this ticker
            response = supabase.table("StockPrices").select("Date, StockPrice").eq("Ticker", ticker).gte("Date", start_date.isoformat()).lte("Date", end_date.isoformat()).order("Date").execute()

            if response.data:
                ticker_prices[ticker] = {
                    datetime.fromisoformat(r['Date'].replace('Z', '+00:00')).date(): float(r['StockPrice'])
                    for r in response.data
                }
                print(f"[CACHE] {ticker}: Found {len(ticker_prices[ticker])} cached prices")
            else:
                # Need to fetch from yfinance
                print(f"[FETCH] {ticker}: Fetching from yfinance...")
                price = fetch_and_cache_price(ticker, start_date)

                # Re-query after caching
                response = supabase.table("StockPrices").select("Date, StockPrice").eq("Ticker", ticker).gte("Date", start_date.isoformat()).lte("Date", end_date.isoformat()).order("Date").execute()

                if response.data:
                    ticker_prices[ticker] = {
                        datetime.fromisoformat(r['Date'].replace('Z', '+00:00')).date(): float(r['StockPrice'])
                        for r in response.data
                    }

        # Get stock currencies for EUR conversion
        ticker_currencies = {}
        for ticker in unique_tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                ticker_currencies[ticker] = info.get('currency', 'USD')
            except Exception as e:
                print(f"[WARNING] Could not get currency for {ticker}: {e}")
                ticker_currencies[ticker] = 'USD'

        # Calculate portfolio value for each date
        portfolio_data = []
        for date in date_range:
            holdings = holdings_timeline.get(date, {})
            total_value = 0

            for ticker, shares in holdings.items():
                # Find closest price for this date
                if ticker in ticker_prices:
                    # Get exact date or closest prior date
                    available_dates = sorted([d for d in ticker_prices[ticker].keys() if d <= date])

                    if available_dates:
                        closest_date = available_dates[-1]
                        price_original = ticker_prices[ticker][closest_date]

                        # Convert to EUR
                        currency = ticker_currencies.get(ticker, 'USD')
                        if currency != 'EUR':
                            exchange_rate = get_exchange_rate(currency, 'EUR')
                            price_eur = price_original * exchange_rate
                        else:
                            price_eur = price_original

                        total_value += shares * price_eur

            portfolio_data.append({
                'date': date.isoformat(),
                'value': round(total_value, 2)
            })

        # Calculate portfolio as percentage from start
        if portfolio_data and portfolio_data[0]['value'] > 0:
            start_value = portfolio_data[0]['value']
            for entry in portfolio_data:
                entry['value_percent'] = round(((entry['value'] - start_value) / start_value * 100), 2)
        else:
            for entry in portfolio_data:
                entry['value_percent'] = 0

        # Fetch benchmark data if requested
        benchmarks = {}
        if include_benchmarks:
            benchmark_tickers = [b.strip() for b in include_benchmarks.split(',') if b.strip()]

            for benchmark in benchmark_tickers:
                print(f"[BENCHMARK] Fetching {benchmark}...")

                # Check cache first
                response = supabase.table("StockPrices").select("Date, StockPrice").eq("Ticker", benchmark).gte("Date", start_date.isoformat()).lte("Date", end_date.isoformat()).order("Date").execute()

                if response.data:
                    benchmark_prices = {
                        datetime.fromisoformat(r['Date'].replace('Z', '+00:00')).date(): float(r['StockPrice'])
                        for r in response.data
                    }
                    print(f"[CACHE] {benchmark}: Found {len(benchmark_prices)} cached prices")
                else:
                    # Fetch from yfinance
                    print(f"[FETCH] {benchmark}: Fetching from yfinance...")
                    fetch_and_cache_price(benchmark, start_date)

                    # Re-query
                    response = supabase.table("StockPrices").select("Date, StockPrice").eq("Ticker", benchmark).gte("Date", start_date.isoformat()).lte("Date", end_date.isoformat()).order("Date").execute()

                    if response.data:
                        benchmark_prices = {
                            datetime.fromisoformat(r['Date'].replace('Z', '+00:00')).date(): float(r['StockPrice'])
                            for r in response.data
                        }

                # Normalize to percentage from start date
                benchmark_data = []
                start_price = None

                for date in date_range:
                    # Find closest price
                    available_dates = sorted([d for d in benchmark_prices.keys() if d <= date])

                    if available_dates:
                        closest_date = available_dates[-1]
                        price = benchmark_prices[closest_date]

                        if start_price is None:
                            start_price = price

                        percent_change = ((price - start_price) / start_price * 100) if start_price > 0 else 0

                        benchmark_data.append({
                            'date': date.isoformat(),
                            'value_percent': round(percent_change, 2)
                        })

                benchmarks[benchmark] = benchmark_data

        # Debug logging
        print(f"[PORTFOLIO] Returning {len(portfolio_data)} portfolio data points")
        print(f"[PORTFOLIO] Date range: {start_date} to {end_date}")
        print(f"[PORTFOLIO] Unique tickers: {unique_tickers}")
        if portfolio_data:
            print(f"[PORTFOLIO] Sample data - First: {portfolio_data[0]}, Last: {portfolio_data[-1]}")

        return jsonify({
            'portfolio': portfolio_data,
            'benchmarks': benchmarks,
            'range': time_range,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })

    except Exception as e:
        print(f"Error in portfolio history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock-price/<string:ticker>', methods=['GET'])
@login_required
def get_stock_price(ticker):
    """Fetch current and historical stock price with database caching and EUR conversion"""
    try:
        # Get optional date parameter for historical prices
        date_str = request.args.get('date')

        # Get stock info for company name and currency
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            company_name = info.get('longName', info.get('shortName', ticker))
            original_currency = info.get('currency', None)

            # If currency not found, try to infer from ticker suffix
            if not original_currency:
                if ticker.endswith('.AS') or ticker.endswith('.PA') or ticker.endswith('.BR') or ticker.endswith('.MI') or ticker.endswith('.DE'):
                    original_currency = 'EUR'
                elif ticker.endswith('.L'):
                    original_currency = 'GBP'
                else:
                    original_currency = 'USD'
        except:
            company_name = ticker
            # Try to infer from ticker suffix
            if ticker.endswith('.AS') or ticker.endswith('.PA') or ticker.endswith('.BR') or ticker.endswith('.MI') or ticker.endswith('.DE'):
                original_currency = 'EUR'
            elif ticker.endswith('.L'):
                original_currency = 'GBP'
            else:
                original_currency = 'USD'

        if date_str:
            # Fetch historical price for specific date from database
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

                # Check database first for this specific date
                response = supabase.table("StockPrices").select("StockPrice, Date").eq("Ticker", ticker).gte("Date", (target_date - timedelta(days=7)).isoformat()).lte("Date", (target_date + timedelta(days=1)).isoformat()).execute()

                if response.data:
                    # Find closest date to target
                    dates = [(datetime.fromisoformat(r['Date'].replace('Z', '+00:00')).date(), float(r['StockPrice'])) for r in response.data]
                    closest_date, price_original = min(dates, key=lambda x: abs((x[0] - target_date).days))
                    print(f"[CACHE] {ticker}: Using cached historical price for {closest_date}")
                else:
                    # Not in database, fetch from yfinance
                    print(f"[FETCH] {ticker}: Fetching historical data from yfinance")
                    stock = yf.Ticker(ticker)
                    hist = stock.history(start=target_date - timedelta(days=7), end=target_date + timedelta(days=1))

                    if hist.empty:
                        return jsonify({
                            'success': False,
                            'message': f'No price data available for {ticker} on {date_str}'
                        }), 404

                    # Find the closest date to the target date
                    closest_date = min(hist.index, key=lambda x: abs(x.date() - target_date)).date()
                    price_original = float(hist.loc[hist.index[hist.index.date == closest_date][0]]['Close'])

                    # Cache the fetched data, avoiding duplicates
                    existing_check = supabase.table("StockPrices").select("Date").eq("Ticker", ticker).gte("Date", (target_date - timedelta(days=7)).isoformat()).lte("Date", (target_date + timedelta(days=1)).isoformat()).execute()

                    existing_dates = set()
                    if existing_check.data:
                        existing_dates = {datetime.fromisoformat(r['Date'].replace('Z', '+00:00')).date() for r in existing_check.data}

                    records = []
                    for date, row in hist.iterrows():
                        if date.date() not in existing_dates:
                            records.append({
                                "Date": date.isoformat(),
                                "Ticker": ticker,
                                "StockPrice": float(row['Close'])
                            })
                    if records:
                        supabase.table("StockPrices").insert(records).execute()
                        print(f"[CACHE] {ticker}: Stored {len(records)} historical records")

                # Convert to EUR
                if original_currency != 'EUR':
                    exchange_rate = get_exchange_rate(original_currency, 'EUR')
                    price_eur = price_original * exchange_rate
                else:
                    exchange_rate = 1.0
                    price_eur = price_original

                return jsonify({
                    'success': True,
                    'ticker': ticker.upper(),
                    'name': company_name,
                    'price': round(price_eur, 2),
                    'price_original': round(price_original, 2),
                    'currency_original': original_currency,
                    'currency': 'EUR',
                    'exchange_rate': round(exchange_rate, 4),
                    'date': closest_date.isoformat()
                })

            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid date format. Use YYYY-MM-DD'
                }), 400
        else:
            # Fetch current price using existing cached function
            price_eur = fetch_live_price(ticker)

            if price_eur is None:
                return jsonify({
                    'success': False,
                    'message': f'No price data available for ticker {ticker}'
                }), 404

            # Get original price from database
            response = supabase.table("StockPrices").select("StockPrice, Date").eq("Ticker", ticker).order("Date", desc=True).limit(1).execute()

            if response.data:
                price_original = float(response.data[0]['StockPrice'])
                date_str = response.data[0]['Date']
            else:
                price_original = price_eur
                date_str = datetime.now().isoformat()

            # Calculate exchange rate
            if original_currency != 'EUR':
                exchange_rate = get_exchange_rate(original_currency, 'EUR')
            else:
                exchange_rate = 1.0

            return jsonify({
                'success': True,
                'ticker': ticker.upper(),
                'name': company_name,
                'price': round(price_eur, 2),
                'price_original': round(price_original, 2),
                'currency_original': original_currency,
                'currency': 'EUR',
                'exchange_rate': round(exchange_rate, 4),
                'date': datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching price for {ticker}: {str(e)}'
        }), 500

@app.route('/api/money-invested', methods=['GET', 'POST'])
@login_required
def money_invested_api():
    """Get all money invested records or add a new one"""
    if request.method == 'GET':
        try:
            response = supabase.table("MoneyInvested").select("*").eq("UserID", current_user.id).order("DATE", desc=True).execute()

            records = []
            for record in response.data:
                records.append({
                    'id': record.get('MoneyInvestedID'),
                    'date': record.get('DATE'),
                    'amount': parse_price(record.get('AMOUNT', 0)),
                    'action': record.get('ACTION', '')
                })

            return jsonify({'records': records})

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        data = request.json

        try:
            # Get next MoneyInvestedID
            response = supabase.table("MoneyInvested").select("MoneyInvestedID").order("MoneyInvestedID", desc=True).limit(1).execute()

            next_id = 1
            if response.data and len(response.data) > 0:
                next_id = response.data[0]['MoneyInvestedID'] + 1

            # Create new record
            new_record = {
                'MoneyInvestedID': next_id,
                'DATE': data.get('date'),
                'AMOUNT': data.get('amount'),
                'ACTION': data.get('action', ''),
                'UserID': current_user.id
            }

            supabase.table("MoneyInvested").insert(new_record).execute()

            return jsonify({'success': True, 'id': next_id, 'message': 'Record added successfully'}), 201

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/money-invested/<int:investment_id>', methods=['PUT', 'DELETE'])
@login_required
def money_invested_operations(investment_id):
    """Update or delete a specific money invested record"""
    if request.method == 'PUT':
        data = request.json

        try:
            updated_record = {
                'DATE': data.get('date'),
                'AMOUNT': data.get('amount'),
                'ACTION': data.get('action', '')
            }

            supabase.table("MoneyInvested").update(updated_record).eq("MoneyInvestedID", investment_id).execute()

            return jsonify({'success': True, 'message': 'Record updated successfully'})

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            supabase.table("MoneyInvested").delete().eq("MoneyInvestedID", investment_id).execute()

            return jsonify({'success': True, 'message': 'Record deleted successfully'})

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/stock-actions/<string:ticker>', methods=['GET'])
@login_required
def get_stock_actions(ticker):
    """Get all actions (transactions and dividends) for a specific stock with summary"""
    try:
        # Get transactions for this ticker
        transactions_response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).eq("TICKER", ticker).order("DATE", desc=True).execute()
        transactions = transactions_response.data

        # Get dividends for this ticker
        dividends_response = supabase.table("Dividend").select("*").eq("UserID", current_user.id).eq("TICKER", ticker).order("DATE", desc=True).execute()
        dividends = dividends_response.data

        # Calculate summary statistics
        total_shares = 0
        total_cost = 0
        currency_from = 'EUR'
        original_prices = []

        for txn in transactions:
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)
            total_purchase_price = parse_price(txn.get('TOTAL PURCHASE PRICE', 0))
            currency_from = txn.get('CURRENCY FROM', 'EUR')
            exchange_rate_at_purchase = parse_price(txn.get('EXCHANGE RATE', 1.0)) or 1.0
            price_before_currency = parse_price(txn.get('PRICE BEFORE CURRENCY', 0)) or parse_price(txn.get('PRICE', 0))

            if action in ['BUY', 'PURCHASE']:
                total_shares += quantity
                total_cost += total_purchase_price if total_purchase_price > 0 else (quantity * parse_price(txn.get('PRICE', 0)))

                original_prices.append({
                    'quantity': quantity,
                    'price_foreign': price_before_currency,
                    'exchange_rate': exchange_rate_at_purchase,
                    'currency': currency_from
                })
            elif action in ['SELL', 'SALE', 'SOLD']:
                total_shares -= quantity

        # Calculate total dividends received
        total_dividends = 0
        for div in dividends:
            total_dividends += float(div.get('TOTAL_DIVIDEND', 0) or 0)

        # Get current price
        current_price = fetch_live_price(ticker) or 0
        avg_purchase_price = total_cost / total_shares if total_shares > 0 else 0

        # Calculate values
        total_market_value = current_price * total_shares
        gain_loss_stock = total_market_value - total_cost
        gain_loss_percent_stock = (gain_loss_stock / total_cost * 100) if total_cost > 0 else 0

        # Calculate gain/loss including dividends
        gain_loss_with_dividends = gain_loss_stock + total_dividends
        gain_loss_percent_with_dividends = (gain_loss_with_dividends / total_cost * 100) if total_cost > 0 else 0

        # Calculate FX impact for non-EUR stocks
        fx_impact = 0
        if currency_from != 'EUR' and original_prices:
            current_fx_rate = get_exchange_rate(currency_from, 'EUR')

            for purchase in original_prices:
                original_rate = purchase['exchange_rate']
                price_foreign = purchase['price_foreign']
                qty = purchase['quantity']

                value_at_original_rate = price_foreign * original_rate * qty
                value_at_current_rate = price_foreign * current_fx_rate * qty
                fx_impact += (value_at_current_rate - value_at_original_rate)

        # Calculate gain/loss including FX
        gain_loss_with_fx = gain_loss_stock + fx_impact
        gain_loss_percent_with_fx = (gain_loss_with_fx / total_cost * 100) if total_cost > 0 else 0

        summary = {
            'total_shares': total_shares,
            'avg_purchase_price': round(avg_purchase_price, 2),
            'total_purchase_cost': round(total_cost, 2),
            'current_price': round(current_price, 2),
            'total_market_value': round(total_market_value, 2),
            'gain_loss_stock': round(gain_loss_stock, 2),
            'gain_loss_percent_stock': round(gain_loss_percent_stock, 2),
            'total_dividends': round(total_dividends, 2),
            'gain_loss_with_dividends': round(gain_loss_with_dividends, 2),
            'gain_loss_percent_with_dividends': round(gain_loss_percent_with_dividends, 2),
            'fx_impact': round(fx_impact, 2),
            'gain_loss_with_fx': round(gain_loss_with_fx, 2),
            'gain_loss_percent_with_fx': round(gain_loss_percent_with_fx, 2),
            'currency': currency_from
        }

        return jsonify({
            'transactions': transactions,
            'dividends': dividends,
            'summary': summary
        })

    except Exception as e:
        print(f"Error fetching stock actions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/holdings-pdf', methods=['GET'])
@login_required
def generate_holdings_pdf():
    """Generate a PDF report of current holdings"""
    try:
        # Get portfolio data (reusing existing logic)
        response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).execute()
        transactions = response.data

        holdings = {}

        # Calculate holdings
        for txn in transactions:
            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)
            price = parse_price(txn.get('PRICE'))
            total_price = parse_price(txn.get('TOTAL PURCHASE PRICE'))

            if not ticker:
                continue

            if ticker not in holdings:
                holdings[ticker] = {
                    'name': txn.get('NAME', ticker),
                    'ticker': ticker,
                    'quantity': 0,
                    'total_cost': 0,
                    'currency': txn.get('CURRENCY TO', 'EUR')
                }

            if action in ['BUY', 'PURCHASE']:
                holdings[ticker]['quantity'] += quantity
                holdings[ticker]['total_cost'] += total_price
            elif action in ['SELL', 'SALE', 'SOLD']:
                holdings[ticker]['quantity'] -= quantity
                avg_cost = holdings[ticker]['total_cost'] / (holdings[ticker]['quantity'] + quantity) if (holdings[ticker]['quantity'] + quantity) > 0 else 0
                holdings[ticker]['total_cost'] -= avg_cost * quantity

        # Filter out zero/negative holdings and get live prices
        portfolio_data = []
        total_value = 0
        total_cost = 0

        for ticker, holding in holdings.items():
            if holding['quantity'] <= 0:
                continue

            current_price = fetch_live_price(ticker)
            if current_price is None:
                current_price = 0

            current_value = current_price * holding['quantity']
            avg_cost = holding['total_cost'] / holding['quantity'] if holding['quantity'] > 0 else 0
            gain_loss = current_value - holding['total_cost']
            gain_loss_percent = (gain_loss / holding['total_cost'] * 100) if holding['total_cost'] > 0 else 0

            total_value += current_value
            total_cost += holding['total_cost']

            portfolio_data.append({
                'ticker': ticker,
                'name': holding['name'],
                'quantity': holding['quantity'],
                'avg_cost': avg_cost,
                'current_price': current_price,
                'current_value': current_value,
                'total_cost': holding['total_cost'],
                'gain_loss': gain_loss,
                'gain_loss_percent': gain_loss_percent
            })

        # Sort by current value descending
        portfolio_data.sort(key=lambda x: x['current_value'], reverse=True)

        # Create PDF with professional styling
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )

        # Container for PDF elements
        elements = []
        styles = getSampleStyleSheet()

        # =========================
        # HEADER SECTION - Professional letterhead style
        # =========================

        # Company/Report Header Box
        header_data = [[Paragraph('<b>INVESTMENT PORTFOLIO REPORT</b>', ParagraphStyle(
            'HeaderTitle',
            parent=styles['Normal'],
            fontSize=18,
            textColor=colors.white,
            alignment=1,
            spaceAfter=0
        ))]]

        header_table = Table(header_data, colWidths=[7*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 5))

        # Report metadata bar
        report_date = datetime.now().strftime('%B %d, %Y')
        report_time = datetime.now().strftime('%H:%M')

        metadata_data = [[
            Paragraph(f'<b>Account:</b> {current_user.username}', ParagraphStyle('MetaLeft', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#555555'))),
            Paragraph(f'<b>Date:</b> {report_date}', ParagraphStyle('MetaCenter', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#555555'), alignment=1)),
            Paragraph(f'<b>Time:</b> {report_time}', ParagraphStyle('MetaRight', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#555555'), alignment=2))
        ]]

        metadata_table = Table(metadata_data, colWidths=[2.33*inch, 2.33*inch, 2.33*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7f9fc')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e4eb')),
        ]))
        elements.append(metadata_table)
        elements.append(Spacer(1, 30))

        # =========================
        # EXECUTIVE SUMMARY SECTION
        # =========================

        total_gain_loss = total_value - total_cost
        total_gain_loss_percent = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0

        # Section title
        summary_title_style = ParagraphStyle(
            'SummaryTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=15,
            spaceBefore=0,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("EXECUTIVE SUMMARY", summary_title_style))

        # Key metrics in grid layout
        summary_grid_data = [
            [
                Paragraph('<b>Total Market Value</b><br/><font size="16" color="#667eea">€{:,.2f}</font>'.format(total_value),
                    ParagraphStyle('MetricStyle', parent=styles['Normal'], fontSize=10, alignment=1, leading=20)),
                Paragraph('<b>Total Investment</b><br/><font size="16" color="#34495e">€{:,.2f}</font>'.format(total_cost),
                    ParagraphStyle('MetricStyle', parent=styles['Normal'], fontSize=10, alignment=1, leading=20)),
            ],
            [
                Paragraph('<b>Total Gain/Loss</b><br/><font size="16" color="{}">{}{:,.2f}</font>'.format(
                    '#27ae60' if total_gain_loss >= 0 else '#e74c3c',
                    '€' if total_gain_loss >= 0 else '-€',
                    abs(total_gain_loss)
                ), ParagraphStyle('MetricStyle', parent=styles['Normal'], fontSize=10, alignment=1, leading=20)),
                Paragraph('<b>Total Return</b><br/><font size="16" color="{}">{}{:.2f}%</font>'.format(
                    '#27ae60' if total_gain_loss_percent >= 0 else '#e74c3c',
                    '+' if total_gain_loss_percent >= 0 else '',
                    total_gain_loss_percent
                ), ParagraphStyle('MetricStyle', parent=styles['Normal'], fontSize=10, alignment=1, leading=20)),
            ]
        ]

        summary_grid = Table(summary_grid_data, colWidths=[3.5*inch, 3.5*inch], rowHeights=[0.8*inch, 0.8*inch])
        summary_grid.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#e0e4eb')),
            ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#e0e4eb')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20),
        ]))
        elements.append(summary_grid)

        # Portfolio stats bar
        elements.append(Spacer(1, 15))
        stats_data = [[
            Paragraph(f'<b>Number of Holdings:</b> {len(portfolio_data)}',
                ParagraphStyle('StatsStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555555'))),
            Paragraph(f'<b>Report Currency:</b> EUR (€)',
                ParagraphStyle('StatsStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555555'), alignment=2))
        ]]
        stats_table = Table(stats_data, colWidths=[3.5*inch, 3.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7f9fc')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 35))

        # =========================
        # HOLDINGS BREAKDOWN SECTION
        # =========================

        elements.append(Paragraph("DETAILED HOLDINGS", summary_title_style))
        elements.append(Spacer(1, 15))

        if portfolio_data:
            # Professional table with better formatting
            table_data = [
                ['TICKER', 'SECURITY NAME', 'QTY', 'AVG COST', 'CURRENT\nPRICE', 'MARKET\nVALUE', 'GAIN/LOSS', 'RETURN\n%']
            ]

            # Add holdings data with conditional formatting
            for holding in portfolio_data:
                gain_color = '#27ae60' if holding['gain_loss'] >= 0 else '#e74c3c'

                table_data.append([
                    Paragraph(f"<b>{holding['ticker']}</b>", ParagraphStyle('TickerStyle', parent=styles['Normal'], fontSize=9)),
                    Paragraph(holding['name'][:30] + ('...' if len(holding['name']) > 30 else ''),
                        ParagraphStyle('NameStyle', parent=styles['Normal'], fontSize=8)),
                    str(int(holding['quantity'])),
                    f"€{holding['avg_cost']:.2f}",
                    f"€{holding['current_price']:.2f}",
                    f"€{holding['current_value']:,.2f}",
                    Paragraph(f'<font color="{gain_color}">{"" if holding["gain_loss"] < 0 else ""}€{holding["gain_loss"]:,.2f}</font>',
                        ParagraphStyle('GainStyle', parent=styles['Normal'], fontSize=9, alignment=2)),
                    Paragraph(f'<font color="{gain_color}"><b>{holding["gain_loss_percent"]:+.2f}%</b></font>',
                        ParagraphStyle('PercentStyle', parent=styles['Normal'], fontSize=9, alignment=2))
                ])

            holdings_table = Table(table_data, colWidths=[0.7*inch, 1.8*inch, 0.5*inch, 0.75*inch, 0.75*inch, 1*inch, 0.95*inch, 0.75*inch])
            holdings_table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),

                # Body styling
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Ticker left
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Name left
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Numbers right
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),

                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f9fc')]),

                # Grid lines
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#667eea')),
                ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e0e4eb')),
                ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#2c3e50')),
            ]))

            elements.append(holdings_table)
        else:
            elements.append(Paragraph("No holdings found in portfolio.",
                ParagraphStyle('NoData', parent=styles['Normal'], fontSize=11, textColor=colors.grey, alignment=1)))

        # =========================
        # FOOTER SECTION
        # =========================

        elements.append(Spacer(1, 40))

        # Disclaimer
        disclaimer_text = """
        <i>This report is generated for informational purposes only. Market values are based on real-time data
        at the time of report generation and may fluctuate. Past performance does not guarantee future results.
        Please consult with a financial advisor before making investment decisions.</i>
        """
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.HexColor('#888888'),
            alignment=1,
            leading=10
        )
        elements.append(Paragraph(disclaimer_text, disclaimer_style))

        elements.append(Spacer(1, 15))

        # Footer branding
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#667eea'),
            alignment=1,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("Portfolio Tracker • Investment Management Platform", footer_style))

        # Build PDF
        doc.build(elements)

        # Prepare response
        buffer.seek(0)
        filename = f"holdings_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio-stocks')
@login_required
def get_portfolio_stocks():
    """Get all unique stocks from user's portfolio (both active and closed positions)"""
    try:
        response = supabase.table("Transactions").select("TICKER, NAME").eq("UserID", current_user.id).execute()
        transactions = response.data

        # Create a dictionary to store unique ticker-name pairs
        stocks_dict = {}
        for txn in transactions:
            ticker = txn.get('TICKER')
            name = txn.get('NAME')
            if ticker and name:
                stocks_dict[ticker] = name

        # Convert to list of objects
        stocks = [{'ticker': ticker, 'name': name} for ticker, name in sorted(stocks_dict.items())]

        return jsonify({'stocks': stocks})

    except Exception as e:
        print(f"Error fetching portfolio stocks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/roerende-voorheffing-pdf/<int:year>')
@login_required
def generate_roerende_voorheffing_pdf(year):
    """Generate PDF overview of Roerende Voorheffing (withholding tax) for a specific year"""
    try:
        # Get all dividends for the selected year
        dividends_response = supabase.table("Dividend").select("*").eq("UserID", current_user.id).execute()
        dividends = dividends_response.data

        # Filter dividends by year
        year_dividends = []
        for div in dividends:
            div_date = datetime.strptime(div['DATE'], '%Y-%m-%d')
            if div_date.year == year:
                year_dividends.append(div)

        # Calculate totals
        total_gross_dividends = 0
        total_withholding_tax = 0
        total_foreign_tax = 0
        total_net_dividends = 0

        for div in year_dividends:
            gross = float(div.get('VALUE RECEIVED BEFORE TAX', 0) or 0)
            withholding = float(div.get('ROERENDE VOORHEFFING', 0) or 0)
            foreign = float(div.get('BUITENLANDSE BRONHEFFING', 0) or 0)
            net = float(div.get('TOTAL_DIVIDEND', 0) or 0)

            total_gross_dividends += gross
            total_withholding_tax += withholding
            total_foreign_tax += foreign
            total_net_dividends += net

        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=30
        )
        elements.append(Paragraph(f'Roerende Voorheffing Overview {year}', title_style))
        elements.append(Spacer(1, 0.3*inch))

        # Summary section
        summary_style = ParagraphStyle(
            'Summary',
            parent=styles['Normal'],
            fontSize=12,
            leading=20
        )

        elements.append(Paragraph('<b>What is Roerende Voorheffing?</b>', summary_style))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(
            'Roerende voorheffing (withholding tax) is a tax on income from capital and movable property in Belgium, '
            'including dividends, interest, and royalties. For dividends, the standard rate is 30%. '
            'This tax is withheld at source before you receive your dividend payment.',
            summary_style
        ))
        elements.append(Spacer(1, 0.3*inch))

        # Summary statistics
        summary_data = [
            ['Summary Statistics', ''],
            ['Total Gross Dividends Received', f'€{total_gross_dividends:.2f}'],
            ['Roerende Voorheffing (Belgian Withholding Tax)', f'€{total_withholding_tax:.2f}'],
            ['Buitenlandse Bronheffing (Foreign Withholding Tax)', f'€{total_foreign_tax:.2f}'],
            ['Total Withholding Tax', f'€{(total_withholding_tax + total_foreign_tax):.2f}'],
            ['Net Dividends Received', f'€{total_net_dividends:.2f}']
        ]

        summary_table = Table(summary_data, colWidths=[4*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4ff')]),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.4*inch))

        # Detailed breakdown
        elements.append(Paragraph('<b>Detailed Breakdown by Stock</b>', summary_style))
        elements.append(Spacer(1, 0.2*inch))

        # Table data
        table_data = [['Date', 'Stock', 'Gross Amount', 'RV (Belgian)', 'Foreign Tax', 'Net Amount']]

        for div in sorted(year_dividends, key=lambda x: x['DATE']):
            date = datetime.strptime(div['DATE'], '%Y-%m-%d').strftime('%d/%m/%Y')
            ticker = div['TICKER']
            gross = float(div.get('VALUE RECEIVED BEFORE TAX', 0) or 0)
            withholding = float(div.get('ROERENDE VOORHEFFING', 0) or 0)
            foreign = float(div.get('BUITENLANDSE BRONHEFFING', 0) or 0)
            net = float(div.get('TOTAL_DIVIDEND', 0) or 0)

            table_data.append([
                date,
                ticker,
                f'€{gross:.2f}',
                f'€{withholding:.2f}',
                f'€{foreign:.2f}',
                f'€{net:.2f}'
            ])

        detail_table = Table(table_data, colWidths=[0.9*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4ff')]),
        ]))
        elements.append(detail_table)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Roerende_Voorheffing_{year}.pdf'
        )

    except Exception as e:
        print(f"Error generating RV PDF: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/cash-debug')
@login_required
def cash_debug():
    """Debug endpoint to see cash position breakdown"""
    try:
        # Get money invested
        money_invested_response = supabase.table("MoneyInvested").select("*").eq("UserID", current_user.id).execute()
        money_invested = money_invested_response.data

        total_deposits = 0
        total_refunds = 0
        total_withdrawals = 0
        for record in money_invested:
            action = record.get('ACTION', '').upper()
            amount = parse_price(record.get('AMOUNT', 0)) or 0

            if action == 'DEPOSIT':
                total_deposits += amount
            elif action == 'REFUND':
                total_refunds += amount
            elif action == 'WITHDRAW':
                total_withdrawals += amount

        # Get dividends
        dividends_response = supabase.table("Dividend").select("*").eq("UserID", current_user.id).execute()
        dividends = dividends_response.data

        total_dividends = 0
        for div in dividends:
            net_dividend = float(div.get('TOTAL_DIVIDEND', 0) or 0)
            total_dividends += net_dividend

        # Get transactions
        transactions_response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).execute()
        transactions = transactions_response.data

        cash_spent_on_stocks = 0
        cash_from_sales = 0
        for txn in transactions:
            action = txn.get('ACTION', '').upper()
            total_purchase_price = parse_price(txn.get('TOTAL PURCHASE PRICE', 0))

            if action in ['BUY', 'PURCHASE']:
                cash_spent_on_stocks += total_purchase_price
            elif action in ['SELL', 'SALE', 'SOLD']:
                cash_from_sales += total_purchase_price

        cash_in = total_deposits + total_refunds + total_dividends + cash_from_sales
        cash_out = cash_spent_on_stocks + total_withdrawals
        cash_position = cash_in - cash_out

        return jsonify({
            'cash_in': {
                'deposits': round(total_deposits, 2),
                'refunds': round(total_refunds, 2),
                'dividends': round(total_dividends, 2),
                'stock_sales': round(cash_from_sales, 2),
                'total': round(cash_in, 2)
            },
            'cash_out': {
                'stock_purchases': round(cash_spent_on_stocks, 2),
                'withdrawals': round(total_withdrawals, 2),
                'total': round(cash_out, 2)
            },
            'cash_position': round(cash_position, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock-analysis')
@login_required
def get_stock_analysis():
    """Get fundamental analysis metrics for all active holdings"""
    try:
        # Get all active holdings (shares > 0)
        response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).execute()
        transactions = response.data

        # Calculate current holdings
        holdings = {}
        for txn in transactions:
            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)

            if not ticker:
                continue

            if ticker not in holdings:
                holdings[ticker] = {
                    'name': txn.get('NAME', ticker),
                    'ticker': ticker,
                    'total_shares': 0
                }

            if action in ['BUY', 'PURCHASE']:
                holdings[ticker]['total_shares'] += quantity
            elif action in ['SELL', 'SALE', 'SOLD']:
                holdings[ticker]['total_shares'] -= quantity

        # Filter to only active holdings
        active_holdings = {k: v for k, v in holdings.items() if v['total_shares'] > 0}

        stocks_data = []

        for ticker, holding in active_holdings.items():
            try:
                print(f"[ANALYSIS] Fetching metrics for {ticker}...")
                stock = yf.Ticker(ticker)
                info = stock.info

                # Check if it's an ETF
                quote_type = info.get('quoteType', '').upper()
                is_etf = quote_type == 'ETF'

                if is_etf:
                    print(f"[ANALYSIS] {ticker} is an ETF, skipping analysis")
                    # Still add to list but mark as ETF
                    stocks_data.append({
                        'ticker': ticker,
                        'name': holding['name'],
                        'is_etf': True,
                        'pe_ratio': None,
                        'pb_ratio': None,
                        'roe': None,
                        'debt_to_equity': None,
                        'free_cash_flow': None
                    })
                    continue

                # Extract valuation metrics
                pe_ratio = info.get('trailingPE', None) or info.get('forwardPE', None)
                pb_ratio = info.get('priceToBook', None)

                # Extract profitability metrics
                roe = info.get('returnOnEquity', None)
                profit_margin = info.get('profitMargins', None)
                operating_margin = info.get('operatingMargins', None)
                gross_margin = info.get('grossMargins', None)

                # Extract financial health metrics
                debt_to_equity = info.get('debtToEquity', None)
                current_ratio = info.get('currentRatio', None)
                quick_ratio = info.get('quickRatio', None)
                free_cash_flow = info.get('freeCashflow', None)

                # Extract growth metrics
                eps = info.get('trailingEps', None)
                earnings_growth = info.get('earningsGrowth', None)
                revenue_growth = info.get('revenueGrowth', None)

                # Extract dividend metrics
                dividend_yield = info.get('dividendYield', None)
                payout_ratio = info.get('payoutRatio', None)

                # Extract risk metrics
                beta = info.get('beta', None)

                # Convert percentages from decimal to percentage
                if roe is not None:
                    roe = roe * 100
                if profit_margin is not None:
                    profit_margin = profit_margin * 100
                if operating_margin is not None:
                    operating_margin = operating_margin * 100
                if gross_margin is not None:
                    gross_margin = gross_margin * 100
                if earnings_growth is not None:
                    earnings_growth = earnings_growth * 100
                if revenue_growth is not None:
                    revenue_growth = revenue_growth * 100
                if dividend_yield is not None:
                    dividend_yield = dividend_yield * 100
                if payout_ratio is not None:
                    payout_ratio = payout_ratio * 100

                # Convert debt to equity from percentage to ratio if needed
                if debt_to_equity is not None and debt_to_equity > 10:
                    debt_to_equity = debt_to_equity / 100

                # Calculate technical indicators
                rsi = None
                distance_from_ma_200 = None
                macd_histogram = None
                bollinger_band_percent_b = None
                adx = None

                try:
                    # Fetch historical data for technical analysis
                    hist = stock.history(period="1y")

                    if not hist.empty and len(hist) >= 200:
                        # Calculate RSI (14-day)
                        delta = hist['Close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        rsi_series = 100 - (100 / (1 + rs))
                        if not pd.isna(rsi_series.iloc[-1]):
                            rsi = rsi_series.iloc[-1]

                        # Calculate 200-day MA and distance
                        ma_200 = hist['Close'].rolling(window=200).mean()
                        if not pd.isna(ma_200.iloc[-1]):
                            current_price = hist['Close'].iloc[-1]
                            distance_from_ma_200 = ((current_price - ma_200.iloc[-1]) / ma_200.iloc[-1]) * 100

                        # Calculate MACD Histogram
                        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
                        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
                        macd = exp1 - exp2
                        signal = macd.ewm(span=9, adjust=False).mean()
                        histogram = macd - signal
                        if not pd.isna(histogram.iloc[-1]):
                            macd_histogram = histogram.iloc[-1]

                        # Calculate Bollinger Bands %B
                        ma_20 = hist['Close'].rolling(window=20).mean()
                        std_20 = hist['Close'].rolling(window=20).std()
                        upper_band = ma_20 + (std_20 * 2)
                        lower_band = ma_20 - (std_20 * 2)
                        bb_width = upper_band - lower_band
                        bb_percent = (hist['Close'] - lower_band) / bb_width
                        if not pd.isna(bb_percent.iloc[-1]):
                            bollinger_band_percent_b = bb_percent.iloc[-1]

                        # Calculate ADX (Average Directional Index)
                        high = hist['High']
                        low = hist['Low']
                        close = hist['Close']

                        plus_dm = high.diff()
                        minus_dm = low.diff()
                        plus_dm[plus_dm < 0] = 0
                        minus_dm[minus_dm > 0] = 0
                        minus_dm = abs(minus_dm)

                        tr1 = high - low
                        tr2 = abs(high - close.shift())
                        tr3 = abs(low - close.shift())
                        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                        atr = tr.rolling(window=14).mean()

                        plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
                        minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)
                        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
                        adx_series = dx.rolling(window=14).mean()
                        if not pd.isna(adx_series.iloc[-1]):
                            adx = adx_series.iloc[-1]

                        print(f"[TECHNICAL] {ticker}: RSI={rsi:.2f if rsi else 'N/A'}, 200-MA Dist={distance_from_ma_200:.2f if distance_from_ma_200 else 'N/A'}%, MACD={macd_histogram:.4f if macd_histogram else 'N/A'}, BB%B={bollinger_band_percent_b:.4f if bollinger_band_percent_b else 'N/A'}, ADX={adx:.2f if adx else 'N/A'}")

                except Exception as tech_error:
                    print(f"[TECHNICAL] Error calculating technical indicators for {ticker}: {tech_error}")

                stocks_data.append({
                    'ticker': ticker,
                    'name': holding['name'],
                    'is_etf': False,
                    # Valuation
                    'pe_ratio': pe_ratio,
                    'pb_ratio': pb_ratio,
                    # Profitability
                    'roe': roe,
                    'profit_margin': profit_margin,
                    'operating_margin': operating_margin,
                    'gross_margin': gross_margin,
                    # Financial Health
                    'debt_to_equity': debt_to_equity,
                    'current_ratio': current_ratio,
                    'quick_ratio': quick_ratio,
                    'free_cash_flow': free_cash_flow,
                    # Growth
                    'eps': eps,
                    'earnings_growth': earnings_growth,
                    'revenue_growth': revenue_growth,
                    # Dividends
                    'dividend_yield': dividend_yield,
                    'payout_ratio': payout_ratio,
                    # Risk
                    'beta': beta,
                    # Technical Indicators
                    'rsi': rsi,
                    'distance_from_ma_200': distance_from_ma_200,
                    'macd_histogram': macd_histogram,
                    'bollinger_band_percent_b': bollinger_band_percent_b,
                    'adx': adx
                })

                print(f"[ANALYSIS] {ticker}: PE={pe_ratio}, PB={pb_ratio}, ROE={roe}%, Profit Margin={profit_margin}%")

            except Exception as e:
                print(f"[ANALYSIS] Error fetching metrics for {ticker}: {e}")
                # Add stock with N/A metrics if fetch fails
                stocks_data.append({
                    'ticker': ticker,
                    'name': holding['name'],
                    'is_etf': False,
                    'pe_ratio': None,
                    'pb_ratio': None,
                    'roe': None,
                    'profit_margin': None,
                    'operating_margin': None,
                    'gross_margin': None,
                    'debt_to_equity': None,
                    'current_ratio': None,
                    'quick_ratio': None,
                    'free_cash_flow': None,
                    'eps': None,
                    'earnings_growth': None,
                    'revenue_growth': None,
                    'dividend_yield': None,
                    'payout_ratio': None,
                    'beta': None,
                    'rsi': None,
                    'distance_from_ma_200': None,
                    'macd_histogram': None,
                    'bollinger_band_percent_b': None,
                    'adx': None
                })

        return jsonify({'stocks': stocks_data})

    except Exception as e:
        print(f"Error in stock analysis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/metric-history')
@login_required
def get_metric_history():
    """Get historical data for a specific metric"""
    try:
        ticker = request.args.get('ticker')
        metric = request.args.get('metric')
        period = request.args.get('period', '1y')  # Default to 1 year

        if not ticker or not metric:
            return jsonify({'error': 'Missing ticker or metric parameter'}), 400

        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty:
            return jsonify({'error': 'No historical data available'}), 404

        # Prepare data based on metric type
        dates = [date.strftime('%Y-%m-%d') for date in hist.index]
        values = []

        # Technical indicators that need calculation
        if metric == 'rsi':
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            values = rsi_series.fillna(0).tolist()

        elif metric == 'distance_from_ma_200':
            ma_200 = hist['Close'].rolling(window=200).mean()
            distance = ((hist['Close'] - ma_200) / ma_200) * 100
            values = distance.fillna(0).tolist()

        elif metric == 'macd_histogram':
            exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
            exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            values = histogram.fillna(0).tolist()

        elif metric == 'bollinger_band_percent_b':
            ma_20 = hist['Close'].rolling(window=20).mean()
            std_20 = hist['Close'].rolling(window=20).std()
            upper_band = ma_20 + (std_20 * 2)
            lower_band = ma_20 - (std_20 * 2)
            bb_width = upper_band - lower_band
            bb_percent = (hist['Close'] - lower_band) / bb_width
            values = bb_percent.fillna(0).tolist()

        elif metric == 'adx':
            high = hist['High']
            low = hist['Low']
            close = hist['Close']

            plus_dm = high.diff()
            minus_dm = low.diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm > 0] = 0
            minus_dm = abs(minus_dm)

            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean()

            plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)
            dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
            adx_series = dx.rolling(window=14).mean()
            values = adx_series.fillna(0).tolist()

        # For fundamental metrics, we need to fetch quarterly data
        elif metric in ['pe_ratio', 'pb_ratio', 'roe', 'profit_margin', 'operating_margin',
                       'gross_margin', 'debt_to_equity', 'current_ratio', 'quick_ratio',
                       'eps', 'earnings_growth', 'revenue_growth', 'beta']:
            # For fundamental metrics, we'll use price history and current value
            # (Fundamental data is not available historically via yfinance easily)
            info = stock.info
            current_value = None

            if metric == 'pe_ratio':
                current_value = info.get('trailingPE') or info.get('forwardPE')
            elif metric == 'pb_ratio':
                current_value = info.get('priceToBook')
            elif metric == 'roe':
                current_value = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else None
            elif metric == 'profit_margin':
                current_value = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else None
            elif metric == 'operating_margin':
                current_value = info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else None
            elif metric == 'gross_margin':
                current_value = info.get('grossMargins', 0) * 100 if info.get('grossMargins') else None
            elif metric == 'debt_to_equity':
                debt = info.get('debtToEquity')
                current_value = debt / 100 if debt and debt > 10 else debt
            elif metric == 'current_ratio':
                current_value = info.get('currentRatio')
            elif metric == 'quick_ratio':
                current_value = info.get('quickRatio')
            elif metric == 'eps':
                current_value = info.get('trailingEps')
            elif metric == 'earnings_growth':
                current_value = info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else None
            elif metric == 'revenue_growth':
                current_value = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else None
            elif metric == 'beta':
                current_value = info.get('beta')

            if current_value is not None:
                # Create a flat line at current value for fundamental metrics
                values = [current_value] * len(dates)
            else:
                return jsonify({'error': 'Metric value not available'}), 404
        else:
            return jsonify({'error': 'Unknown metric type'}), 400

        return jsonify({
            'dates': dates,
            'values': values,
            'ticker': ticker,
            'metric': metric
        })

    except Exception as e:
        print(f"Error fetching metric history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock-news')
@login_required
def get_stock_news():
    """Get news articles for portfolio tickers using yfinance"""
    try:
        # Get all active holdings
        response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).execute()
        transactions = response.data

        # Calculate current holdings
        holdings = {}
        for txn in transactions:
            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)

            if not ticker:
                continue

            if ticker not in holdings:
                holdings[ticker] = {'name': txn.get('NAME', ticker), 'ticker': ticker, 'total_shares': 0}

            if action in ['BUY', 'PURCHASE']:
                holdings[ticker]['total_shares'] += quantity
            elif action in ['SELL', 'SALE', 'SOLD']:
                holdings[ticker]['total_shares'] -= quantity

        # Filter to only active holdings
        active_tickers = [k for k, v in holdings.items() if v['total_shares'] > 0]

        # Fetch news for each ticker using yfinance
        all_news = []
        seen_titles = set()  # To avoid duplicate articles

        for ticker in active_tickers:
            try:
                stock = yf.Ticker(ticker)
                news = stock.news

                if news:
                    for article in news[:10]:  # Get up to 5 articles per ticker
                        # New yfinance format has nested 'content' object
                        content = article.get('content', article)

                        title = content.get('title', '')

                        if not title or title in seen_titles:
                            continue
                        seen_titles.add(title)

                        # Parse timestamp - try new format first, then old format
                        date_str = ""
                        timestamp = 0

                        # New format uses pubDate string
                        if 'pubDate' in content:
                            try:
                                pub_date_str = content['pubDate']
                                parsed_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                                timestamp = parsed_date.timestamp()
                                date_str = parsed_date.strftime('%b %d, %Y %H:%M')
                            except:
                                pass
                        # Old format uses providerPublishTime timestamp
                        elif 'providerPublishTime' in article:
                            try:
                                timestamp = article['providerPublishTime']
                                parsed_date = datetime.fromtimestamp(timestamp)
                                date_str = parsed_date.strftime('%b %d, %Y %H:%M')
                            except:
                                pass

                        # Get publisher - try new format first
                        publisher = 'Yahoo Finance'
                        if 'provider' in content and content['provider']:
                            publisher = content['provider'].get('displayName', 'Yahoo Finance')
                        elif 'publisher' in article:
                            publisher = article.get('publisher', 'Yahoo Finance')

                        # Get link - try new format first
                        link = ''
                        if 'clickThroughUrl' in content and content['clickThroughUrl']:
                            link = content['clickThroughUrl'].get('url', '')
                        elif 'canonicalUrl' in content and content['canonicalUrl']:
                            link = content['canonicalUrl'].get('url', '')
                        elif 'link' in article:
                            link = article.get('link', '')

                        # Get description/summary
                        description = content.get('summary', '') or content.get('description', '')

                        all_news.append({
                            'ticker': ticker,
                            'ticker_name': holdings[ticker]['name'],
                            'title': title,
                            'link': link,
                            'date': date_str,
                            'timestamp': timestamp,
                            'description': description,
                            'publisher': publisher
                        })

                print(f"[NEWS] Fetched {len(news) if news else 0} articles for {ticker}")

            except Exception as e:
                print(f"[NEWS] Error fetching news for {ticker}: {e}")
                continue

        # Sort by timestamp (most recent first) and limit to 10
        all_news.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        all_news = all_news[:20]

        return jsonify({'news': all_news})

    except Exception as e:
        print(f"Error fetching stock news: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def normalize_summary_format(raw_text, ollama_url):
    """
    Use a second LLM call to normalize/clean the summary into exact format.
    This is more reliable than regex parsing for handling LLM output variations.
    """
    normalize_prompt = f"""Reformat this text into EXACTLY these 4 lines. Keep the content but fix the format:

Price Movements & Financial Performance: [content]
Important Company Announcements/Events: [content]
Market Sentiment & Analyst Views: [content]
Risks & Opportunities: [content]

RULES:
- Output ONLY these 4 lines, nothing else
- Use EXACTLY these labels (copy them exactly)
- Keep each line to 1-2 sentences max
- If a category has no info, write "No significant updates"
- NO intro, NO conclusion, NO numbering, NO bullet points

TEXT TO REFORMAT:
{raw_text}"""

    try:
        normalize_request = urllib.request.Request(
            ollama_url,
            data=json.dumps({
                "model": "gemma3:1b",  # Use smaller/faster model for formatting
                "prompt": normalize_prompt,
                "stream": False
            }).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(normalize_request, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            normalized = result.get('response', raw_text).strip()

            # Quick validation: check if output has the expected labels
            if 'Price Movements' in normalized and 'Risks & Opportunities' in normalized:
                return normalized
            else:
                # Fallback to original if normalization failed
                return raw_text

    except Exception as e:
        print(f"[OLLAMA] Normalization failed, using raw text: {e}")
        return raw_text


def is_ollama_available():
    """Check if Ollama is running locally"""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except:
        return False


@app.route('/api/summarize-news', methods=['POST'])
@login_required
def summarize_news():
    """Summarize news articles per stock using local Ollama"""
    try:
        # Check if Ollama is available (only works locally, not on Vercel)
        if not is_ollama_available():
            return jsonify({
                'error': 'AI summaries require Ollama running locally. This feature is not available on the deployed version.',
                'summaries': {}
            })

        data = request.get_json()
        news_by_ticker = data.get('news_by_ticker', {})

        if not news_by_ticker:
            return jsonify({'error': 'No news data provided'}), 400

        summaries = {}
        ollama_url = "http://localhost:11434/api/generate"

        for ticker, articles in news_by_ticker.items():
            if not articles:
                continue

            # Build news text for this ticker
            news_text = f"News articles for {ticker}:\n\n"
            for i, article in enumerate(articles, 1):
                news_text += f"{i}. {article.get('title', 'No title')}\n"
                if article.get('description'):
                    news_text += f"   {article.get('description')[:200]}...\n"
                news_text += f"   Date: {article.get('date', 'Unknown')}\n\n"

            # Create prompt for Ollama - strict format enforcement
            prompt = f"""Analyze these news articles for {ticker} and respond with EXACTLY this format (4 lines only, no intro, no conclusion, no extra text):

Price Movements & Financial Performance: <your analysis here>
Important Company Announcements/Events: <your analysis here>
Market Sentiment & Analyst Views: <your analysis here>
Risks & Opportunities: <your analysis here>

RULES:
- Output ONLY the 4 lines above with your analysis
- Each line must start with the exact label followed by colon
- Keep each point to 1-2 sentences
- Do NOT add any introduction like "Here's" or "Based on"
- Do NOT add "Overall" or conclusion
- If no relevant info for a category, write "No significant updates"

NEWS ARTICLES:
{news_text}"""

            try:
                # Call Ollama API
                ollama_request = urllib.request.Request(
                    ollama_url,
                    data=json.dumps({
                        "model": "llama3.2:3b",
                        "prompt": prompt,
                        "stream": False
                    }).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )

                with urllib.request.urlopen(ollama_request, timeout=60) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    raw_summary = result.get('response', 'Unable to generate summary').strip()

                    # Use second LLM call to normalize format
                    summary = normalize_summary_format(raw_summary, ollama_url)
                    summaries[ticker] = summary
                    print(f"[OLLAMA] Generated summary for {ticker}")

            except Exception as ollama_error:
                print(f"[OLLAMA] Error summarizing {ticker}: {ollama_error}")
                summaries[ticker] = f"Unable to generate summary: Ollama may not be running"

        return jsonify({'summaries': summaries})

    except Exception as e:
        print(f"Error in summarize_news: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """Chat with AI about portfolio using local Ollama"""
    try:
        # Check if Ollama is available (only works locally, not on Vercel)
        if not is_ollama_available():
            return jsonify({
                'error': 'Chatbot requires Ollama running locally. This feature is not available on the deployed version.',
                'response': 'Sorry, the AI chatbot requires Ollama to be running locally. This feature is not available on the deployed version of the app.'
            })

        data = request.get_json()
        user_message = data.get('message', '')

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Get current portfolio data for context
        portfolio_context = ""

        try:
            # Fetch all transactions (using UserID column and current_user.id)
            transactions_response = supabase.table("Transactions").select("*").eq("UserID", current_user.id).execute()
            transactions = transactions_response.data if transactions_response.data else []

            if transactions:
                # Build comprehensive portfolio context
                portfolio_context = "=== PORTFOLIO DATA ===\n\n"

                # All transactions details
                portfolio_context += "TRANSACTION HISTORY:\n"
                for tx in sorted(transactions, key=lambda x: x.get('DATE', ''), reverse=True):
                    ticker = tx.get('TICKER', 'N/A')
                    date = tx.get('DATE', 'N/A')
                    qty = float(tx.get('QUANTITY', 0))
                    price = tx.get('PRICE', 0)
                    action = tx.get('ACTION', '').upper()
                    currency = tx.get('CURRENCY TO', 'EUR') or 'EUR'
                    total = qty * float(price) if qty and price else 0

                    # Determine transaction type from ACTION field
                    if action in ['SELL', 'SALE', 'SOLD']:
                        tx_type = "SELL"
                    else:
                        tx_type = "BUY"

                    portfolio_context += f"- {date}: {tx_type} {qty} shares of {ticker} at {currency} {price} (Total: {currency} {total:.2f})\n"

                # Aggregate current holdings using ACTION field
                holdings = {}
                holdings_cost = {}
                for tx in transactions:
                    ticker = tx.get('TICKER')
                    qty = float(tx.get('QUANTITY', 0))
                    price = float(tx.get('PRICE', 0)) if tx.get('PRICE') else 0
                    action = tx.get('ACTION', '').upper()

                    if ticker not in holdings:
                        holdings[ticker] = 0
                        holdings_cost[ticker] = 0

                    if action in ['BUY', 'PURCHASE']:
                        holdings[ticker] += qty
                        holdings_cost[ticker] += qty * price
                    elif action in ['SELL', 'SALE', 'SOLD']:
                        holdings[ticker] -= qty

                # Current holdings summary - filter out invalid tickers
                active_holdings = {k: v for k, v in holdings.items() if v > 0 and k and k.upper() not in ['NOT AVAILABLE', 'N/A', 'UNKNOWN', '']}
                if active_holdings:
                    portfolio_context += "\nCURRENT HOLDINGS:\n"
                    for ticker, qty in active_holdings.items():
                        avg_cost = holdings_cost.get(ticker, 0) / qty if qty > 0 else 0
                        # Try to get current price
                        try:
                            current_price = fetch_live_price(ticker)
                            if current_price is None:
                                portfolio_context += f"- {ticker}: {qty} shares, Avg cost: €{avg_cost:.2f} (price unavailable)\n"
                                continue
                            current_value = qty * current_price
                            cost_basis = holdings_cost.get(ticker, 0)
                            gain_loss = current_value - cost_basis
                            gain_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0
                            portfolio_context += f"- {ticker}: {qty} shares, Avg cost: €{avg_cost:.2f}, Current price: €{current_price:.2f}, Value: €{current_value:.2f}, P/L: €{gain_loss:.2f} ({gain_pct:+.1f}%)\n"
                        except:
                            portfolio_context += f"- {ticker}: {qty} shares, Avg cost: €{avg_cost:.2f}\n"

                # Sold positions (completely exited)
                sold_tickers = set()
                for ticker, qty in holdings.items():
                    if qty <= 0 and ticker and ticker.upper() not in ['NOT AVAILABLE', 'N/A', 'UNKNOWN', '']:
                        sold_tickers.add(ticker)

                if sold_tickers:
                    portfolio_context += "\nSOLD POSITIONS (Fully Exited):\n"
                    for ticker in sold_tickers:
                        ticker_txs = [tx for tx in transactions if tx.get('TICKER') == ticker]
                        # Calculate using ACTION field
                        total_cost = 0
                        total_proceeds = 0
                        shares_bought = 0
                        shares_sold = 0
                        for tx in ticker_txs:
                            action = tx.get('ACTION', '').upper()
                            qty = float(tx.get('QUANTITY', 0))
                            price = float(tx.get('PRICE', 0)) if tx.get('PRICE') else 0
                            if action in ['BUY', 'PURCHASE']:
                                total_cost += qty * price
                                shares_bought += qty
                            elif action in ['SELL', 'SALE', 'SOLD']:
                                total_proceeds += qty * price
                                shares_sold += qty
                        realized_pl = total_proceeds - total_cost
                        portfolio_context += f"- {ticker}: Bought {shares_bought} shares for €{total_cost:.2f}, Sold {shares_sold} shares for €{total_proceeds:.2f}, Realized P/L: €{realized_pl:.2f}\n"

            # Fetch dividends
            try:
                dividends_response = supabase.table("Dividend").select("*").eq("UserID", current_user.id).execute()
                dividends = dividends_response.data if dividends_response.data else []

                if dividends:
                    portfolio_context += "\nDIVIDEND HISTORY:\n"
                    for div in sorted(dividends, key=lambda x: x.get('DATE', ''), reverse=True)[:10]:  # Last 10
                        ticker = div.get('TICKER', 'N/A')
                        amount = float(div.get('TOTAL_DIVIDEND', 0))
                        date = div.get('DATE', 'N/A')
                        portfolio_context += f"- {date}: {ticker} dividend: €{amount:.2f}\n"

                    total_all_divs = sum(float(d.get('TOTAL_DIVIDEND', 0)) for d in dividends)
                    portfolio_context += f"\nTotal dividends received: €{total_all_divs:.2f}\n"
            except Exception as e:
                print(f"Error fetching dividends for chat: {e}")

            # Calculate portfolio totals
            if active_holdings:
                try:
                    total_value = 0
                    total_cost = 0
                    for ticker, qty in active_holdings.items():
                        current_price = fetch_live_price(ticker)
                        if current_price is not None:
                            total_value += qty * current_price
                        total_cost += holdings_cost.get(ticker, 0)

                    total_gain = total_value - total_cost
                    total_gain_pct = (total_gain / total_cost * 100) if total_cost > 0 else 0

                    portfolio_context += f"\nPORTFOLIO SUMMARY:\n"
                    portfolio_context += f"- Total invested: €{total_cost:.2f}\n"
                    portfolio_context += f"- Current value: €{total_value:.2f}\n"
                    portfolio_context += f"- Total P/L: €{total_gain:.2f} ({total_gain_pct:+.1f}%)\n"
                except Exception as e:
                    print(f"Error calculating portfolio totals: {e}")

        except Exception as e:
            print(f"Error fetching portfolio for chat: {e}")
            import traceback
            traceback.print_exc()

        # Create prompt for Ollama
        prompt = f"""You are a helpful portfolio assistant with access to the user's complete investment data. Use the data below to answer their question accurately.

{portfolio_context}

User question: {user_message}

Instructions:
- Answer based on the actual data provided above
- Be specific with numbers, dates, and ticker symbols
- If asked about a specific stock, find it in the data
- Keep response concise (3-5 sentences)
- If the data doesn't contain the answer, say so"""

        ollama_url = "http://localhost:11434/api/generate"

        ollama_request = urllib.request.Request(
            ollama_url,
            data=json.dumps({
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False
            }).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(ollama_request, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            bot_response = result.get('response', 'Sorry, I could not generate a response.')
            return jsonify({'response': bot_response.strip()})

    except urllib.error.URLError as e:
        print(f"Ollama connection error: {e}")
        return jsonify({'error': 'Could not connect to Ollama. Make sure it is running.'}), 500
    except Exception as e:
        print(f"Error in chat: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

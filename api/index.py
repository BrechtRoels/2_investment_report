from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import os
import re
import yfinance as yf
from supabase_client import supabase

app = Flask(__name__, template_folder='../templates', static_folder='../static')

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

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/holdings')
def holdings():
    return render_template('holdings.html')

@app.route('/transactions')
def transactions():
    return render_template('transactions.html')

def get_exchange_rate(from_currency, to_currency='EUR'):
    """Get exchange rate from one currency to another using yfinance"""
    if from_currency == to_currency:
        return 1.0

    try:
        # Use yfinance to get exchange rate via forex pairs
        pair = f"{from_currency}{to_currency}=X"
        forex = yf.Ticker(pair)
        hist = forex.history(period='1d')

        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception as e:
        print(f"Error fetching exchange rate for {from_currency} to {to_currency}: {e}")

    # Fallback rates if API fails (updated Jan 2026)
    fallback_rates = {
        'USD': 0.86,  # 1 USD = 0.86 EUR
        'GBP': 1.20,  # 1 GBP = 1.20 EUR
        'JPY': 0.0057, # 1 JPY = 0.0057 EUR
        'CHF': 0.98,  # 1 CHF = 0.98 EUR
        'CAD': 0.61,  # 1 CAD = 0.61 EUR
        'AUD': 0.55,  # 1 AUD = 0.55 EUR
    }

    return fallback_rates.get(from_currency, 1.0)

def fetch_live_price(ticker):
    """Fetch live stock price using yfinance with currency conversion to EUR"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='1d')

        if hist.empty:
            return None

        price_in_original_currency = float(hist['Close'].iloc[-1])

        # Get the currency of the stock
        try:
            info = stock.info
            currency = info.get('currency', 'USD')
        except:
            currency = 'USD'  # Default to USD if we can't get currency info

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

@app.route('/api/portfolio')
def get_portfolio():
    """Get portfolio summary from Transactions table with live prices"""
    try:
        response = supabase.table("Transactions").select("*").execute()

        transactions = response.data

        holdings = {}

        for txn in transactions:
            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)
            price = parse_price(txn.get('PRICE'))
            total_purchase_price = parse_price(txn.get('TOTAL PURCHASE PRICE', 0))

            if not ticker:
                continue

            if ticker not in holdings:
                holdings[ticker] = {
                    'name': txn.get('NAME', ticker),
                    'ticker': ticker,
                    'total_shares': 0,
                    'total_cost': 0,
                    'transactions': []
                }

            if action in ['BUY', 'PURCHASE']:
                holdings[ticker]['total_shares'] += quantity
                # Use actual TOTAL PURCHASE PRICE from database (includes fees)
                holdings[ticker]['total_cost'] += total_purchase_price if total_purchase_price > 0 else (quantity * price)
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

            investments.append({
                'id': ticker,
                'name': holding['name'],
                'symbol': ticker,
                'shares': holding['total_shares'],
                'purchase_price': round(avg_purchase_price, 2),
                'current_price': round(current_price, 2),
                'change': round(change_percent, 2),
                'value': round(current_value, 2)
            })

            total_value += current_value
            total_cost += cost

        total_gain = total_value - total_cost
        gain_percentage = (total_gain / total_cost * 100) if total_cost > 0 else 0

        return jsonify({
            'investments': investments,
            'total_value': round(total_value, 2),
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

@app.route('/api/chart-data')
def get_chart_data():
    """Generate portfolio value history from transactions"""
    try:
        response = supabase.table("Transactions").select("*").order("DATE").execute()

        transactions = response.data

        holdings_by_date = {}
        current_holdings = {}

        for txn in transactions:
            date = txn.get('DATE', datetime.now().strftime('%Y-%m-%d'))
            ticker = txn.get('TICKER')
            action = txn.get('ACTION', '').upper()
            quantity = txn.get('QUANTITY', 0)
            price = parse_price(txn.get('PRICE'))

            if not ticker:
                continue

            if ticker not in current_holdings:
                current_holdings[ticker] = {'shares': 0, 'last_price': 0}

            if action in ['BUY', 'PURCHASE']:
                current_holdings[ticker]['shares'] += quantity
            elif action in ['SELL', 'SALE', 'SOLD']:
                current_holdings[ticker]['shares'] -= quantity

            if price > 0:
                current_holdings[ticker]['last_price'] = price

            total_value = sum(h['shares'] * h['last_price'] for h in current_holdings.values())

            holdings_by_date[date] = round(total_value, 2)

        if not holdings_by_date:
            current_date = datetime.now() - timedelta(days=30)
            data = []
            for i in range(31):
                data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'value': 0
                })
                current_date += timedelta(days=1)
            return jsonify(data)

        data = [{'date': date, 'value': value} for date, value in sorted(holdings_by_date.items())]

        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/realized-holdings')
def get_realized_holdings():
    """Get realized holdings (sold stocks) with their gains/losses"""
    try:
        response = supabase.table("Transactions").select("*").order("DATE").execute()
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

@app.route('/api/transactions')
def get_transactions():
    """Get all transactions"""
    try:
        response = supabase.table("Transactions").select("*").order("DATE", desc=True).execute()

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

@app.route('/api/transactions/<int:transaction_id>', methods=['PUT'])
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

@app.route('/api/stock-price/<string:ticker>', methods=['GET'])
def get_stock_price(ticker):
    """Fetch current and historical stock price using yfinance with EUR conversion"""
    try:
        # Get optional date parameter for historical prices
        date_str = request.args.get('date')

        stock = yf.Ticker(ticker)

        # Get stock info for company name and currency
        try:
            info = stock.info
            company_name = info.get('longName', info.get('shortName', ticker))
            original_currency = info.get('currency', 'USD')
        except:
            company_name = ticker
            original_currency = 'USD'

        if date_str:
            # Fetch historical price for specific date
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d')
                # Get data for a range around the target date to ensure we get the price
                start_date = target_date - timedelta(days=7)
                end_date = target_date + timedelta(days=1)

                hist = stock.history(start=start_date, end=end_date)

                if hist.empty:
                    return jsonify({
                        'success': False,
                        'message': f'No price data available for {ticker} on {date_str}'
                    }), 404

                # Find the closest date to the target date
                closest_date = min(hist.index, key=lambda x: abs(x.date() - target_date.date()))
                price_original = float(hist.loc[closest_date]['Close'])

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
                    'date': closest_date.strftime('%Y-%m-%d')
                })

            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid date format. Use YYYY-MM-DD'
                }), 400
        else:
            # Fetch current price
            hist = stock.history(period='1d')

            if hist.empty:
                return jsonify({
                    'success': False,
                    'message': f'No price data available for ticker {ticker}'
                }), 404

            price_original = float(hist['Close'].iloc[-1])

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
                'date': hist.index[-1].strftime('%Y-%m-%d')
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching price for {ticker}: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)

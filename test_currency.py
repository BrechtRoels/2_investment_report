#!/usr/bin/env python3

# Test currency detection logic
def get_currency(ticker):
    # Simulating the fixed logic
    try:
        # In real code, this would call yfinance
        # For testing, simulate that yfinance returns None for some stocks
        ticker_to_currency = {
            'NVDA': 'USD',  # yfinance should return this
            'INGA.AS': 'EUR',  # yfinance should return this
            'TEST.AS': None,  # simulate yfinance failure
            'TEST': None  # simulate yfinance failure
        }
        
        currency = ticker_to_currency.get(ticker, None)
        
        # If currency not found, try to infer from ticker suffix
        if not currency:
            if ticker.endswith('.AS') or ticker.endswith('.PA') or ticker.endswith('.BR') or ticker.endswith('.MI') or ticker.endswith('.DE'):
                currency = 'EUR'
            elif ticker.endswith('.L'):
                currency = 'GBP'
            else:
                currency = 'USD'
                
        return currency
    except:
        # Try to infer from ticker suffix
        if ticker.endswith('.AS') or ticker.endswith('.PA') or ticker.endswith('.BR') or ticker.endswith('.MI') or ticker.endswith('.DE'):
            return 'EUR'
        elif ticker.endswith('.L'):
            return 'GBP'
        else:
            return 'USD'

tickers = ['NVDA', 'INGA.AS', 'TEST.AS', 'TEST', 'AAPL']
for ticker in tickers:
    print(f"{ticker}: {get_currency(ticker)}")

import yfinance as yf

# Test with a well-known stock
ticker = "AAPL"
stock = yf.Ticker(ticker)
info = stock.info

print(f"Testing available metrics for {ticker}:\n")

metrics = {
    # Growth & Earnings
    'EPS (ttm)': info.get('trailingEps'),
    'EPS (forward)': info.get('forwardEps'),
    'Earnings Growth': info.get('earningsGrowth'),
    'Revenue Growth': info.get('revenueGrowth'),
    
    # Margins
    'Profit Margin': info.get('profitMargins'),
    'Operating Margin': info.get('operatingMargins'),
    'Gross Margin': info.get('grossMargins'),
    
    # Liquidity
    'Current Ratio': info.get('currentRatio'),
    'Quick Ratio': info.get('quickRatio'),
    
    # Dividends
    'Dividend Yield': info.get('dividendYield'),
    'Payout Ratio': info.get('payoutRatio'),
    
    # Valuation
    'EV/EBITDA': info.get('enterpriseToEbitda'),
    'Price to Sales': info.get('priceToSalesTrailing12Months'),
    
    # Additional
    'Beta': info.get('beta'),
    '52 Week High': info.get('fiftyTwoWeekHigh'),
    '52 Week Low': info.get('fiftyTwoWeekLow'),
}

for name, value in metrics.items():
    if value is not None:
        print(f"✓ {name}: {value}")
    else:
        print(f"✗ {name}: Not available")

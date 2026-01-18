import yfinance as yf
import pandas as pd
import numpy as np

# Test with a well-known stock
ticker = "AAPL"
stock = yf.Ticker(ticker)

# Get historical data for technical analysis
hist = stock.history(period="1y")

if not hist.empty:
    print(f"Testing technical indicators for {ticker}:\n")
    print(f"Historical data points: {len(hist)}")
    print(f"Latest close: ${hist['Close'].iloc[-1]:.2f}")
    
    # Calculate RSI (14-day)
    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    print(f"\n✓ RSI (14-day): {rsi.iloc[-1]:.2f}")
    
    # Calculate 200-day MA
    ma_200 = hist['Close'].rolling(window=200).mean()
    if not pd.isna(ma_200.iloc[-1]):
        current_price = hist['Close'].iloc[-1]
        distance_from_ma = ((current_price - ma_200.iloc[-1]) / ma_200.iloc[-1]) * 100
        print(f"✓ 200-Day MA: ${ma_200.iloc[-1]:.2f}")
        print(f"✓ Distance from 200-Day MA: {distance_from_ma:.2f}%")
    else:
        print(f"✗ 200-Day MA: Not enough data")
    
    # Calculate MACD
    exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
    exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    print(f"✓ MACD Histogram: {histogram.iloc[-1]:.4f}")
    
    # Calculate Bollinger Bands
    ma_20 = hist['Close'].rolling(window=20).mean()
    std_20 = hist['Close'].rolling(window=20).std()
    upper_band = ma_20 + (std_20 * 2)
    lower_band = ma_20 - (std_20 * 2)
    bb_width = upper_band - lower_band
    bb_percent = (hist['Close'] - lower_band) / bb_width
    print(f"✓ Bollinger Band %B: {bb_percent.iloc[-1]:.4f}")
    
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
    adx = dx.rolling(window=14).mean()
    
    print(f"✓ ADX (Trend Strength): {adx.iloc[-1]:.2f}")
    
else:
    print("No historical data available")

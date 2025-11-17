# Zerodha Kite API Configuration
# Get your API credentials from https://developers.kite.trade/

API_KEY = 'your_api_key_here'
API_SECRET = 'your_api_secret_here'

# Access token will be generated after login
# This needs to be updated daily as it expires
ACCESS_TOKEN = 'your_access_token_here'

# Trading Parameters
# Instrument type: "NIFTY" or "BANKNIFTY"
INSTRUMENT = "NIFTY"

# Exchange: NSE for cash, NFO for F&O
EXCHANGE = "NFO"

# Product type: MIS (intraday), NRML (overnight), CNC (delivery - only for equity)
PRODUCT_TYPE = "MIS"

# Order type for F&O: MARKET or LIMIT
ORDER_TYPE = "MARKET"

# Lot size (Nifty 50 = 25, Bank Nifty = 15 as of 2024)
LOT_SIZE = {
    "NIFTY": 25,
    "BANKNIFTY": 15
}

# Number of lots to trade
NUM_LOTS = 1

# Trading Symbol Format Examples:
# Futures: NIFTY24NOVFUT, BANKNIFTY24NOVFUT
# Options: NIFTY2411428000CE, BANKNIFTY2411451000PE
# The bot will auto-generate based on current month

# Risk Management (optional)
STOP_LOSS_PERCENT = 1.0  # 1% stop loss
TARGET_PERCENT = 2.0     # 2% target

# Candle Interval for strategy (minute, 3minute, 5minute, 15minute, 30minute, 60minute, day)
INTERVAL = "5minute"

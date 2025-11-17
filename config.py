"""
Configuration management for Zerodha Trading Bot
Uses environment variables for security
"""
import os

# Try to load dotenv if available (optional dependency)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, will use system environment variables only
    pass

# Zerodha API Configuration
KITE_API_KEY = os.getenv('KITE_API_KEY', '')
KITE_API_SECRET = os.getenv('KITE_API_SECRET', '')
KITE_ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN', '')  # Generated daily via login

# Risk Management Settings
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))  # 2% risk per trade
MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '0.5'))  # Max 50% of capital
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '0.01'))  # 1% stop loss for F&O
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '0.02'))  # 2% take profit
MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '0.05'))  # 5% max daily loss
MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', '0.10'))  # 10% max drawdown

# Trading Settings
PAPER_TRADING = os.getenv('PAPER_TRADING', 'true').lower() == 'true'
INITIAL_PAPER_BALANCE = float(os.getenv('INITIAL_PAPER_BALANCE', '100000'))  # 1 Lakh for F&O

# F&O Contract Settings
DEFAULT_EXPIRY = os.getenv('DEFAULT_EXPIRY', 'current')  # 'current' or 'next' or 'YYYYMMDD'
MAX_LOTS = int(os.getenv('MAX_LOTS', '10'))  # Maximum lots to trade

# Nifty50 Settings
NIFTY_LOT_SIZE = int(os.getenv('NIFTY_LOT_SIZE', '25'))  # Current lot size (changes periodically)
NIFTY_TICK_SIZE = float(os.getenv('NIFTY_TICK_SIZE', '0.05'))

# BankNifty Settings
BANKNIFTY_LOT_SIZE = int(os.getenv('BANKNIFTY_LOT_SIZE', '15'))  # Current lot size
BANKNIFTY_TICK_SIZE = float(os.getenv('BANKNIFTY_TICK_SIZE', '0.05'))

# Strategy Parameters
WWT_EMA_PERIOD = int(os.getenv('WWT_EMA_PERIOD', '10'))
WWT_CI_EMA_PERIOD = int(os.getenv('WWT_CI_EMA_PERIOD', '21'))
WWT_WT2_SMA_PERIOD = int(os.getenv('WWT_WT2_SMA_PERIOD', '4'))
ORB_PERIOD = int(os.getenv('ORB_PERIOD', '3'))
ORB_BREAKOUT_BUFFER = float(os.getenv('ORB_BREAKOUT_BUFFER', '0.001'))  # 0.1% buffer

# Logging Settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'zerodha_bot.log')
TRADE_JOURNAL_FILE = os.getenv('TRADE_JOURNAL_FILE', 'trade_journal.csv')

# WebSocket Settings
WS_RECONNECT_ATTEMPTS = int(os.getenv('WS_RECONNECT_ATTEMPTS', '5'))
WS_RECONNECT_DELAY = int(os.getenv('WS_RECONNECT_DELAY', '5'))  # seconds

# Market Hours (IST)
MARKET_OPEN_HOUR = int(os.getenv('MARKET_OPEN_HOUR', '9'))
MARKET_OPEN_MINUTE = int(os.getenv('MARKET_OPEN_MINUTE', '15'))
MARKET_CLOSE_HOUR = int(os.getenv('MARKET_CLOSE_HOUR', '15'))
MARKET_CLOSE_MINUTE = int(os.getenv('MARKET_CLOSE_MINUTE', '30'))


# Validation
def validate_config():
    """Validate configuration settings"""
    errors = []

    if not KITE_API_KEY:
        errors.append("KITE_API_KEY is not set")
    if not KITE_API_SECRET:
        errors.append("KITE_API_SECRET is not set")
    if not KITE_ACCESS_TOKEN:
        errors.append("KITE_ACCESS_TOKEN is not set (required for trading)")

    if RISK_PER_TRADE <= 0 or RISK_PER_TRADE > 1:
        errors.append("RISK_PER_TRADE must be between 0 and 1")
    if MAX_POSITION_SIZE <= 0 or MAX_POSITION_SIZE > 1:
        errors.append("MAX_POSITION_SIZE must be between 0 and 1")
    if STOP_LOSS_PERCENT <= 0 or STOP_LOSS_PERCENT > 1:
        errors.append("STOP_LOSS_PERCENT must be between 0 and 1")
    if TAKE_PROFIT_PERCENT <= 0 or TAKE_PROFIT_PERCENT > 1:
        errors.append("TAKE_PROFIT_PERCENT must be between 0 and 1")
    if MAX_LOTS <= 0:
        errors.append("MAX_LOTS must be positive")

    return errors

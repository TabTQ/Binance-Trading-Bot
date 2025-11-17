"""
Configuration management for Binance Trading Bot
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

# API Configuration
KEY = os.getenv('BINANCE_API_KEY', '')
SECRET = os.getenv('BINANCE_API_SECRET', '')

# Risk Management Settings
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))  # 2% risk per trade
MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '0.5'))  # Max 50% of balance
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '0.02'))  # 2% stop loss
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '0.04'))  # 4% take profit
MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '0.05'))  # 5% max daily loss
MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', '0.10'))  # 10% max drawdown

# Trading Settings
PAPER_TRADING = os.getenv('PAPER_TRADING', 'true').lower() == 'true'
INITIAL_PAPER_BALANCE = float(os.getenv('INITIAL_PAPER_BALANCE', '10000'))

# Strategy Parameters
WWT_EMA_PERIOD = int(os.getenv('WWT_EMA_PERIOD', '10'))
WWT_CI_EMA_PERIOD = int(os.getenv('WWT_CI_EMA_PERIOD', '21'))
WWT_WT2_SMA_PERIOD = int(os.getenv('WWT_WT2_SMA_PERIOD', '4'))
ORB_PERIOD = int(os.getenv('ORB_PERIOD', '3'))
ORB_BREAKOUT_BUFFER = float(os.getenv('ORB_BREAKOUT_BUFFER', '0.001'))  # 0.1% buffer

# Logging Settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'trading_bot.log')
TRADE_JOURNAL_FILE = os.getenv('TRADE_JOURNAL_FILE', 'trade_journal.csv')

# WebSocket Settings
WS_RECONNECT_ATTEMPTS = int(os.getenv('WS_RECONNECT_ATTEMPTS', '5'))
WS_RECONNECT_DELAY = int(os.getenv('WS_RECONNECT_DELAY', '5'))  # seconds

# Validation
def validate_config():
    """Validate configuration settings"""
    errors = []

    if not KEY:
        errors.append("BINANCE_API_KEY is not set")
    if not SECRET:
        errors.append("BINANCE_API_SECRET is not set")

    if RISK_PER_TRADE <= 0 or RISK_PER_TRADE > 1:
        errors.append("RISK_PER_TRADE must be between 0 and 1")
    if MAX_POSITION_SIZE <= 0 or MAX_POSITION_SIZE > 1:
        errors.append("MAX_POSITION_SIZE must be between 0 and 1")
    if STOP_LOSS_PERCENT <= 0 or STOP_LOSS_PERCENT > 1:
        errors.append("STOP_LOSS_PERCENT must be between 0 and 1")
    if TAKE_PROFIT_PERCENT <= 0 or TAKE_PROFIT_PERCENT > 1:
        errors.append("TAKE_PROFIT_PERCENT must be between 0 and 1")

    return errors

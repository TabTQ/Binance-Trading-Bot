# Algorithmic Trading Bot

A Python-based algorithmic trading bot that implements the WTMFI (Williams Trend Multi-Frame Indicator) strategy. Originally designed for Binance cryptocurrency trading, now extended to support Zerodha Kite API for trading Nifty 50 and Bank Nifty futures in Indian markets.

## Features

- **WTMFI Strategy**: Uses Williams Trend Multi-Frame Indicator for buy/sell signals
- **Real-time Trading**: WebSocket and polling modes for live market data
- **Multiple Markets**: Support for both Binance (crypto) and Zerodha (Indian indices)
- **Risk Management**: Configurable lot sizes and margin monitoring
- **Logging**: Comprehensive logging for trade analysis

## Available Bots

### 1. Binance Trading Bot (Original)
- File: `BOT_2.0.py`
- Config: `config.py`
- Trades cryptocurrency pairs (BTC/USDT, ETH/USDT, etc.)

### 2. Zerodha Trading Bot (New)
- File: `zerodha_bot.py`
- Config: `zerodha_config.py`
- Auth: `zerodha_auth.py`
- Trades Nifty 50 and Bank Nifty futures

---

## Zerodha Bot Setup (Nifty 50 / Bank Nifty)

### Prerequisites

1. **Zerodha Account** with F&O (Futures & Options) enabled
2. **Kite Connect API** subscription (₹2000/month) - [Apply here](https://developers.kite.trade/)
3. **Python 3.8+** installed
4. **TA-Lib** installed (see installation instructions below)

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/your-repo/trading-bot.git
cd trading-bot
```

2. **Install TA-Lib (Required for technical indicators):**

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get update
   sudo apt-get install -y build-essential wget
   wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
   tar -xzf ta-lib-0.4.0-src.tar.gz
   cd ta-lib/
   ./configure --prefix=/usr
   make
   sudo make install
   cd ..
   ```

   **macOS:**
   ```bash
   brew install ta-lib
   ```

   **Windows:**
   - Download from [TA-Lib Windows](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib)
   - Install the appropriate .whl file for your Python version

3. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

### Configuration

1. **Get your Kite Connect API credentials:**
   - Go to [Kite Connect Developer Portal](https://developers.kite.trade/)
   - Create a new app
   - Note down your `API Key` and `API Secret`
   - Set redirect URL to: `http://127.0.0.1:5000/callback`

2. **Update `zerodha_config.py`:**
```python
API_KEY = 'your_api_key_here'
API_SECRET = 'your_api_secret_here'
ACCESS_TOKEN = 'your_access_token_here'  # Will be generated after login

# Trading Configuration
INSTRUMENT = "NIFTY"  # or "BANKNIFTY"
EXCHANGE = "NFO"
PRODUCT_TYPE = "MIS"  # MIS for intraday, NRML for overnight
NUM_LOTS = 1
INTERVAL = "5minute"
```

3. **Generate Access Token:**
```bash
python zerodha_auth.py
```
   - This opens a browser for Kite login
   - After login, copy the access token displayed
   - Paste it in `zerodha_config.py`
   - **Note:** Access token expires daily at 7:30 AM IST

### Running the Bot

```bash
python zerodha_bot.py
```

You'll be prompted to choose:
1. **Polling Mode** (Recommended) - Fetches candles at regular intervals
2. **WebSocket Mode** - Real-time tick data

### Important Notes

- **Market Hours**: NSE/NFO operates 9:15 AM - 3:30 PM IST (Mon-Fri)
- **Token Expiry**: Access token expires daily at 7:30 AM IST
- **Lot Sizes**: Nifty 50 = 25 units, Bank Nifty = 15 units (as of 2024)
- **Margins**: Ensure adequate margin (recommended ₹50,000+ for 1 lot)
- **Paper Trading**: Orders are live! Test with small lots first
- **Risk Warning**: F&O trading involves substantial risk of loss

### Strategy Explanation (WTMFI)

The bot uses Williams Trend Multi-Frame Indicator:

1. **Average Price (AP)** = (High + Low + Close) / 3
2. **ESA** = EMA(AP, 10)
3. **Deviation** = |AP - ESA|
4. **CI** = Deviation / (0.015 × EMA(Deviation, 10))
5. **WT1** = EMA(CI, 21)
6. **WT2** = SMA(WT1, 4)

**Buy Signal**: WT1 crosses above WT2
**Sell Signal**: WT1 crosses below WT2

---

## Binance Bot Setup (Original)

### Prerequisites
- Binance account with API access
- Python 3.7+
- TA-Lib installed

### Configuration

Update `config.py`:
```python
KEY = 'your_binance_api_key'
SECRET = 'your_binance_api_secret'
```

### Running

```bash
python BOT_2.0.py
```

Enter:
- Crypto symbol (e.g., BTC, ETH)
- Kline interval (1m, 5m, 15m, 1h, etc.)

---

## Technologies Used

- **kiteconnect** - Zerodha Kite API wrapper
- **python-binance** - Binance API wrapper (original bot)
- **websocket-client** - WebSocket connections
- **pandas** - Data manipulation
- **numpy** - Numerical computations
- **TA-Lib** - Technical analysis indicators
- **Flask** - OAuth callback server (Zerodha auth)

---

## File Structure

```
├── BOT_2.0.py              # Original Binance trading bot
├── config.py               # Binance API credentials
├── zerodha_bot.py          # Zerodha trading bot (Nifty/Bank Nifty)
├── zerodha_config.py       # Zerodha API credentials & settings
├── zerodha_auth.py         # Zerodha OAuth authentication helper
├── requirements.txt        # Python dependencies
├── zerodha_bot.log         # Trading logs (generated)
└── README.md               # This file
```

---

## Disclaimer

**IMPORTANT**: This software is for educational purposes only.

- Trading involves substantial risk of financial loss
- Past performance does not guarantee future results
- The authors are not responsible for any financial losses
- Always test with paper trading or small amounts first
- Ensure you understand the risks before using real money
- This is NOT financial advice

---

## License

MIT License - Use at your own risk.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

For issues or feature requests, please open a GitHub issue.

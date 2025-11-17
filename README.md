# Zerodha F&O Trading Bot v2.0

A professional-grade trading bot for **Nifty50 and BankNifty Futures & Options** using Zerodha's Kite Connect API. Features comprehensive risk management, multiple strategies, and detailed trade journaling.

## Features

### Core Features
- **F&O Trading**: Nifty50 and BankNifty futures
- **Multiple Strategies**: WWT (Weis Wave Volume) and ORB (Opening Range Breakout)
- **Paper Trading Mode**: Test strategies without real money
- **Automatic Contract Selection**: Handles expiry dates and contract symbols
- **Lot-based Position Sizing**: Proper F&O lot size calculations

### Risk Management
- Configurable risk per trade (default: 2%)
- Maximum lots limit
- Automatic stop-loss and take-profit
- Margin-based position sizing
- Daily loss limit protection (5%)
- Maximum drawdown circuit breaker (10%)

### Indian Market Features
- Market hours awareness (9:15 AM - 3:30 PM IST)
- Auto expiry calculation (last Thursday of month)
- Intraday (MIS) product support
- NSE F&O segment integration

## Technologies

- **Kite Connect API** - Zerodha's trading API
- **KiteTicker** - Real-time WebSocket data
- **Pandas** - Data manipulation
- **NumPy** - Numerical computations
- **TA-Lib** - Technical analysis indicators

## Prerequisites

1. **Zerodha Account** with F&O trading enabled
2. **Kite Connect Subscription** (₹2000/month)
3. **Python 3.7+**
4. **TA-Lib** (system-level installation required)

## Installation

### 1. Install System Dependencies (TA-Lib)

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install build-essential wget
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
```

**macOS:**
```bash
brew install ta-lib
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Kite Connect

1. **Create Kite Connect App:**
   - Go to https://kite.trade/
   - Create new app
   - Get API Key and Secret

2. **Copy environment template:**
```bash
cp .env.example .env
```

3. **Edit `.env` with your credentials:**
```bash
nano .env
```

4. **Generate Access Token:**
   The access token must be generated daily through Kite Connect's login flow.
   See Kite Connect documentation for token generation.

## Configuration

### Zerodha API Credentials
```
KITE_API_KEY=your_key
KITE_API_SECRET=your_secret
KITE_ACCESS_TOKEN=daily_generated_token
```

### F&O Settings
```
NIFTY_LOT_SIZE=25            # Check NSE for current lot size
BANKNIFTY_LOT_SIZE=15        # Check NSE for current lot size
MAX_LOTS=10                  # Maximum lots to trade
```

### Risk Management
```
RISK_PER_TRADE=0.02          # 2% risk per trade
MAX_POSITION_SIZE=0.5        # Max 50% of capital
STOP_LOSS_PERCENT=0.01       # 1% stop loss (tighter for F&O)
TAKE_PROFIT_PERCENT=0.02     # 2% take profit
MAX_DAILY_LOSS=0.05          # 5% daily loss limit
MAX_DRAWDOWN=0.10            # 10% max drawdown
```

### Trading Mode
```
PAPER_TRADING=true           # Paper trading (default)
INITIAL_PAPER_BALANCE=100000 # 1 Lakh INR starting capital
```

### Market Hours (IST)
```
MARKET_OPEN_HOUR=9
MARKET_OPEN_MINUTE=15
MARKET_CLOSE_HOUR=15
MARKET_CLOSE_MINUTE=30
```

## Usage

Run the bot:
```bash
python BOT_2.0.py
```

### Interactive Setup

1. **Select Instrument:**
   - NIFTY 50 Futures
   - BANKNIFTY Futures

2. **Select Strategy:**
   - Weis Wave Volume (WWT) - Trend following
   - Opening Range Breakout (ORB) - Perfect for Nifty/BankNifty intraday

3. **Select Timeframe:**
   - minute, 3minute, 5minute (recommended), 15minute (recommended), 30minute, 60minute, day

4. **Review Configuration**

5. **Confirm to Start**

## Strategies

### Weis Wave Volume (WWT)
- Uses WT1/WT2 indicator crossovers
- BUY when WT1 crosses above WT2
- SELL when WT1 crosses below WT2
- Good for trending markets

### Opening Range Breakout (ORB)
- **Perfect for Nifty/BankNifty intraday trading**
- Establishes price range from first N candles after market open
- BUY on breakout above range high
- SELL on breakdown below range low
- Most effective with 15-minute or 5-minute candles

## F&O Contract Handling

The bot automatically:
- Calculates current month expiry (last Thursday)
- Generates trading symbol (e.g., `NIFTY24NOV28FUT`)
- Fetches instrument token from NFO segment
- Handles lot-based quantity calculations

## Trade Journal

All trades are logged to `trade_journal.csv`:

| Column | Description |
|--------|-------------|
| timestamp | Trade execution time (IST) |
| instrument | NIFTY or BANKNIFTY |
| trading_symbol | Full contract symbol |
| side | BUY or SELL |
| price | Execution price |
| quantity | Total shares (lots × lot_size) |
| lots | Number of lots |
| value | Total trade value (INR) |
| strategy | Strategy name |
| pnl | Profit/Loss in INR |
| pnl_percent | P&L percentage |

## Paper Trading Simulation

In paper trading mode, the bot:
- Simulates realistic Nifty/BankNifty price movements
- Calculates proper margin requirements (~12% for futures)
- Tracks P&L accurately
- Enforces all risk management rules

This allows strategy testing without real capital.

## Important Considerations

### Lot Sizes
- **NIFTY**: 25 shares per lot (check NSE for updates)
- **BANKNIFTY**: 15 shares per lot (check NSE for updates)
- Lot sizes change periodically - update in `.env`

### Margin Requirements
- F&O trading requires margin (typically 10-15% of contract value)
- Bot calculates margin for paper trading
- Live trading uses actual margin from Zerodha

### Market Hours
- NSE F&O: 9:15 AM - 3:30 PM IST
- Pre-market: 9:00 AM - 9:15 AM (not traded)
- Bot checks market hours before trading

### Access Token
- Kite Connect access token expires daily
- Must regenerate before each trading session
- Consider automation for token generation

## Safety Features

1. **Paper Trading** - Default mode for safe testing
2. **Stop Loss** - Automatic loss limiting (1% default for F&O)
3. **Take Profit** - Lock in gains
4. **Daily Loss Limit** - Stop trading after 5% daily loss
5. **Max Drawdown** - Circuit breaker at 10% drawdown
6. **Max Lots Limit** - Cap on position size
7. **Market Hours Check** - Only trades during NSE hours
8. **Input Validation** - Prevents invalid configurations

## Architecture

```
BOT_2.0.py
├── ZerodhaTradingBot (Main orchestrator)
├── Strategy (Abstract base class)
│   ├── WWTStrategy
│   └── ORBStrategy
├── RiskManager (Lot sizing, risk limits)
├── TradeJournal (Trade history, P&L metrics)
├── PaperTrader (Simulated F&O trading)
└── Data Classes
    ├── Trade
    ├── Position
    └── FNOContract
```

## Troubleshooting

### Common Issues

1. **kiteconnect not found**
   ```bash
   pip install kiteconnect
   ```

2. **TA-Lib not found**: Install system TA-Lib first

3. **Access token expired**: Regenerate via Kite Connect login

4. **Invalid trading symbol**: Check NSE for correct expiry format

5. **Insufficient margin**: Reduce MAX_LOTS or increase capital

6. **Module not found**: Run `pip install -r requirements.txt`

### Logs

Check `zerodha_bot.log` for detailed error messages.

## Future Improvements

- [ ] Auto token generation script
- [ ] Options (CE/PE) trading support
- [ ] Backtesting with historical NSE data
- [ ] Multiple index support (Nifty Bank, Nifty IT, etc.)
- [ ] Telegram/Discord notifications
- [ ] Web dashboard with live P&L
- [ ] Options Greeks calculations
- [ ] Advanced strategies (Iron Condor, Straddle, etc.)

## Regulatory Compliance

⚠️ **IMPORTANT:**
- F&O trading is regulated by SEBI
- Ensure compliance with all NSE/BSE regulations
- Maintain proper records for tax purposes
- Consult a financial advisor before live trading
- Losses in F&O can exceed invested capital

## License

MIT License

## Disclaimer

**This software is for educational purposes only.**

Trading in Futures & Options involves substantial risk and is not suitable for all investors. Past performance is not indicative of future results. The risk of loss in trading F&O can be substantial. You should carefully consider whether trading is suitable for you in light of your financial condition.

Never trade with money you cannot afford to lose. The developers are not responsible for any financial losses incurred using this software.

**Always test with paper trading first!**

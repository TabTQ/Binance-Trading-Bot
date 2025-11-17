# Binance Trading Bot v2.0

A professional-grade cryptocurrency trading bot with risk management, multiple strategies, and comprehensive logging.

## Features

### Core Features
- **Multiple Trading Strategies**: WWT (Weis Wave Volume) and ORB (Opening Range Breakout)
- **Paper Trading Mode**: Test strategies without risking real money
- **Risk Management**: Stop-loss, take-profit, position sizing, daily loss limits
- **Trade Journal**: Automatic CSV logging of all trades with P&L tracking
- **Performance Metrics**: Win rate, drawdown tracking, and statistics

### Risk Management
- Configurable risk per trade (default: 2%)
- Maximum position size limits
- Automatic stop-loss and take-profit
- Daily loss limit protection
- Maximum drawdown circuit breaker

### Security
- Environment variable-based configuration
- No hardcoded API keys
- `.gitignore` for sensitive files
- Configuration validation

### Reliability
- WebSocket auto-reconnection
- Comprehensive error handling
- Detailed logging (file and console)
- Graceful shutdown with statistics

## Technologies

- **Binance API** - Market data and order execution
- **WebSocket** - Real-time price streaming
- **Pandas** - Data manipulation
- **NumPy** - Numerical computations
- **TA-Lib** - Technical analysis indicators
- **python-dotenv** - Environment configuration

## Installation

### 1. Install System Dependencies

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

### 3. Configure Environment

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your settings:
```bash
nano .env
```

3. Add your Binance API credentials:
```
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

## Configuration

All configuration is done via environment variables in `.env`:

### API Configuration
```
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
```

### Risk Management
```
RISK_PER_TRADE=0.02          # 2% risk per trade
MAX_POSITION_SIZE=0.5        # Max 50% of balance
STOP_LOSS_PERCENT=0.02       # 2% stop loss
TAKE_PROFIT_PERCENT=0.04     # 4% take profit
MAX_DAILY_LOSS=0.05          # 5% daily loss limit
MAX_DRAWDOWN=0.10            # 10% max drawdown
```

### Trading Mode
```
PAPER_TRADING=true           # Paper trading (no real money)
INITIAL_PAPER_BALANCE=10000  # Starting paper balance
```

### Strategy Parameters
```
# WWT Strategy
WWT_EMA_PERIOD=10
WWT_CI_EMA_PERIOD=21
WWT_WT2_SMA_PERIOD=4

# ORB Strategy
ORB_PERIOD=3                 # Candles for opening range
ORB_BREAKOUT_BUFFER=0.001    # 0.1% breakout buffer
```

## Usage

Run the bot:
```bash
python BOT_2.0.py
```

### Interactive Setup

1. **Select Instrument:**
   - NIFTY50 (BTC proxy)
   - BANKNIFTY (ETH proxy)
   - Custom symbol

2. **Select Strategy:**
   - Weis Wave Volume (WWT) - Trend following
   - Opening Range Breakout (ORB) - Momentum trading

3. **Select Timeframe:**
   - 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 12h, 1d, 3d, 1w, 1M

4. **Review Configuration**

5. **Confirm to Start**

## Strategies

### Weis Wave Volume (WWT)
- Uses WT1/WT2 indicator crossovers
- BUY when WT1 crosses above WT2
- SELL when WT1 crosses below WT2
- Good for trending markets

### Opening Range Breakout (ORB)
- Establishes price range from first N candles
- BUY on breakout above range high
- SELL on breakdown below range low
- Good for momentum and volatility

## Output Files

- **`trading_bot.log`** - Detailed execution logs
- **`trade_journal.csv`** - Complete trade history with P&L

## Trade Journal Columns

| Column | Description |
|--------|-------------|
| timestamp | Trade execution time |
| symbol | Trading pair |
| side | BUY or SELL |
| price | Execution price |
| quantity | Trade size |
| value | Total trade value |
| strategy | Strategy name |
| pnl | Profit/Loss amount |
| pnl_percent | P&L percentage |
| stop_loss | Stop loss price |
| take_profit | Take profit price |

## Safety Features

1. **Paper Trading** - Default mode for testing
2. **Stop Loss** - Automatic loss limiting
3. **Take Profit** - Lock in gains
4. **Daily Loss Limit** - Stop trading after 5% loss
5. **Max Drawdown** - Circuit breaker at 10% drawdown
6. **Position Sizing** - Risk-based quantity calculation
7. **Input Validation** - Prevents invalid configurations

## Architecture

```
BOT_2.0.py
├── TradingBot (Main orchestrator)
├── Strategy (Abstract base class)
│   ├── WWTStrategy
│   └── ORBStrategy
├── RiskManager (Position sizing, limits)
├── TradeJournal (Trade history, metrics)
├── PaperTrader (Simulated trading)
└── Data Classes (Trade, Position)
```

## Important Notes

⚠️ **WARNINGS:**
- Live trading is disabled by default (PAPER_TRADING=true)
- Never commit `.env` file with real API keys
- Start with paper trading to test strategies
- Past performance doesn't guarantee future results
- Cryptocurrency trading involves significant risk

## Troubleshooting

### Common Issues

1. **TA-Lib not found**: Install system TA-Lib first
2. **API errors**: Check credentials in `.env`
3. **WebSocket disconnects**: Automatic reconnection enabled
4. **Module not found**: Run `pip install -r requirements.txt`
5. **python-dotenv not installed**: Optional - bot will use system environment variables
6. **No API keys configured**: Bot will use mock data for strategy testing in paper mode

### Mock Data Mode

If API keys are not configured and paper trading is enabled, the bot will:
- Generate mock historical data for strategy initialization
- Allow testing of strategy logic without real market connection
- Display warning about offline/mock mode

This is useful for:
- Testing strategy implementation
- Validating risk management logic
- Learning the bot interface

### Logs

Check `trading_bot.log` for detailed error messages.

## Future Improvements

- [ ] Backtesting engine
- [ ] More strategy options (RSI, MACD, Bollinger Bands)
- [ ] Web dashboard
- [ ] Telegram notifications
- [ ] Multi-pair trading
- [ ] Database storage
- [ ] Unit tests

## License

MIT License

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies involves substantial risk of loss. Always do your own research and never trade with money you cannot afford to lose.

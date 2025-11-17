# CLAUDE.md - Binance Trading Bot

## Quick Reference

- **Language:** Python 3
- **Main Entry:** `BOT_2.0.py` (195 lines)
- **Config:** `config.py` (API credentials)
- **Status:** Proof-of-concept with trading disabled
- **Run:** `python BOT_2.0.py`

## Project Overview

This is a cryptocurrency trading bot that:
- Connects to Binance via WebSocket for real-time price data
- Implements Wavetrend technical indicator for trade signals
- Executes BUY/SELL orders on indicator crossovers
- **Note:** Order execution is currently commented out (dry-run mode)

## Codebase Structure

```
Binance-Trading-Bot/
├── BOT_2.0.py       # Main bot - all trading logic
├── config.py        # API credentials (KEY, SECRET)
└── README.md        # Basic project info
```

## Dependencies

```bash
pip install python-binance websocket-client TA-Lib pandas numpy
```

**Important:** TA-Lib requires system-level libta-lib installation.

## Core Architecture

### Global State (Lines 15-21)
```python
position = False           # Current trading position
ap, ds, cis, wt1s = []    # Indicator calculation lists
wt2_last, wt1_last = 1.0  # Previous indicator values
```

### Key Functions

| Function | Purpose | Lines |
|----------|---------|-------|
| `initialize_calc()` | Load historical data, pre-calculate indicators | 24-71 |
| `on_message(ws, message)` | Process WebSocket data, execute trades | 110-166 |
| `order(side, c)` | Execute buy/sell (currently disabled) | 85-102 |
| `buy_amount(c)` | Calculate buy quantity from USDT balance | 79-83 |
| `sell_amount()` | Get available crypto balance | 73-77 |

### Trading Logic (Wavetrend Crossover)

1. **Calculate indicators:**
   - AP = (High + Low + Close) / 3
   - D = EMA(|AP - EMA(AP, 10)|, 10)
   - CI = D / (0.015 * D)
   - WT1 = EMA(CI, 21)
   - WT2 = SMA(WT1, 4)

2. **Trade signals:**
   - **BUY:** WT1 crosses above WT2 (not in position)
   - **SELL:** WT1 crosses below WT2 (in position)

## Development Commands

```bash
# Run bot (interactive - prompts for symbol and timeframe)
python BOT_2.0.py

# Example inputs:
# Symbol: BTC
# Kline: 5m
```

## Critical Issues to Know

### Security
- API credentials in plain text (`config.py`)
- No input validation on user inputs
- Should be in `.gitignore` in production

### Code Quality
- **No error handling** - API failures crash the bot
- **Memory leak** - Lists grow indefinitely without cleanup
- **Global state** - All functions share mutable globals
- **No tests** - No test suite present
- **No logging** - Only `print()` statements

### Incomplete Code
- Lines 176-194: Duplicate/commented code (unreachable)
- Line 122: Hardcoded `is_candle_closed = True` (should use WebSocket data)
- Lines 93, 98: Order execution commented out

## When Modifying This Code

### Do:
- Add try/except blocks around API calls
- Implement proper logging (replace print statements)
- Add input validation for symbol and kline
- Consider memory management for indicator lists
- Keep API credentials out of version control
- Add type hints and docstrings

### Don't:
- Enable order execution without thorough testing
- Commit real API credentials
- Change indicator constants (0.015, 10, 21, 4) without understanding impact
- Assume WebSocket connection is stable

### Refactoring Priorities
1. Extract indicator calculation to separate module
2. Implement error handling for all API calls
3. Add configuration for indicator parameters
4. Implement proper state management (consider class-based)
5. Add reconnection logic for WebSocket
6. Implement list size limits to prevent memory issues

## API Reference

### Binance Client (python-binance)
```python
client = Client(KEY, SECRET, tld='com')
client.get_klines(symbol, interval, limit)      # Historical candles
client.get_asset_balance(asset)                 # Account balance
client.create_order(symbol, side, type, quantity)  # Place order
```

### WebSocket Stream
```python
ws = websocket.WebSocketApp(url, on_open, on_close, on_message)
ws.run_forever()  # Blocking call
```

### Technical Analysis (TA-Lib)
```python
talib.EMA(array, timeperiod)  # Exponential Moving Average
talib.SMA(array, timeperiod)  # Simple Moving Average
```

## Testing This Bot

Since there are no tests, manual testing approach:
1. Use test/paper trading API credentials
2. Keep order execution commented out
3. Monitor console output for trading signals
4. Verify indicator calculations match expected values
5. Test with various symbols and timeframes

## Common Workflows

### Adding New Indicator
1. Extend `initialize_calc()` to pre-calculate
2. Add global list to store values
3. Update `on_message()` to calculate on new candles
4. Modify trade logic to incorporate new indicator

### Enabling Live Trading
1. Uncomment lines 93, 98 in `order()` function
2. Add error handling around order creation
3. Implement order quantity rounding (exchange requirements)
4. Add balance verification before orders
5. Test extensively with small amounts first

### Adding Error Handling
```python
def order(side, c):
    try:
        # existing logic
        order = client.create_order(...)
    except BinanceAPIException as e:
        print(f"Order failed: {e}")
        # Handle specific error codes
    except Exception as e:
        print(f"Unexpected error: {e}")
```

import websocket, json, pprint, numpy, talib
from binance.client import Client
from binance.enums import *
import pandas as pd
import config
from datetime import datetime, time

# Initialize Binance client
client = Client(config.KEY, config.SECRET, tld='com')

# Global variables for trading state
position = False
SYMBOL = ''
TRADE_SYMBOL = ''
kline = ''
SOCKET = ''
selected_strategy = ''

# WWT Strategy variables
ap = []
ds = []
cis = []
wt1s = []
wt2_last = 1.0000
wt1_last = 1.0000

# Opening Range Breakout Strategy variables
orb_high = None
orb_low = None
orb_range_set = False
orb_candle_count = 0
ORB_PERIOD = 3  # Number of candles to determine opening range

def display_instrument_menu():
    """Display instrument selection menu and get user choice"""
    print("\n" + "="*50)
    print("        INSTRUMENT SELECTION")
    print("="*50)
    print("1. NIFTY50 (BTC as proxy)")
    print("2. BANKNIFTY (ETH as proxy)")
    print("3. Custom Symbol")
    print("="*50)

    while True:
        choice = input("Select instrument (1-3): ").strip()
        if choice == '1':
            return 'BTC', 'NIFTY50'
        elif choice == '2':
            return 'ETH', 'BANKNIFTY'
        elif choice == '3':
            custom = input("Enter custom symbol (e.g., BTC, ETH, BNB): ").strip().upper()
            return custom, custom
        else:
            print("Invalid choice. Please select 1, 2, or 3.")

def display_strategy_menu():
    """Display strategy selection menu and get user choice"""
    print("\n" + "="*50)
    print("        STRATEGY SELECTION")
    print("="*50)
    print("1. Weis Wave Volume (WWT) Strategy")
    print("   - Uses WT1/WT2 crossover signals")
    print("   - Good for trend following")
    print("")
    print("2. Opening Range Breakout (ORB) Strategy")
    print("   - Trades breakouts from initial range")
    print("   - Good for momentum trading")
    print("="*50)

    while True:
        choice = input("Select strategy (1-2): ").strip()
        if choice == '1':
            return 'WWT'
        elif choice == '2':
            return 'ORB'
        else:
            print("Invalid choice. Please select 1 or 2.")

def get_timeframe():
    """Get timeframe selection from user"""
    print("\n" + "="*50)
    print("        TIMEFRAME SELECTION")
    print("="*50)
    print("Available: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 12h, 1d, 3d, 1w, 1M")
    print("="*50)
    kline = input("Enter kline/timeframe: ").strip()
    return kline

def initialize_wwt():
    """Initialize WWT strategy with historical data"""
    global TRADE_SYMBOL, kline, ap, ds, cis, wt1s, wt2_last, wt1_last

    print("\nInitializing WWT Strategy...")
    hist_data = client.get_klines(symbol=TRADE_SYMBOL, interval=kline, limit=43)
    D = pd.DataFrame(hist_data)
    D.columns = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'is_best_match']

    i = 42
    j = 0
    while j < i:
        h = float(D['high'][j])
        l = float(D['low'][j])
        c = float(D['close'][j])
        ap_calc = (h + l + c) / 3
        ap.append(ap_calc)

        if len(ap) > 9:
            np_ap = numpy.array(ap)
            esa = talib.EMA(np_ap, 10)
            last_esa = float(esa[-1])
            d_abs = abs(ap_calc - last_esa)
            ds.append(float(d_abs))

            if len(ds) > 9:
                np_d = numpy.array(ds)
                d = talib.EMA(np_d, 10)
                last_d = float(d[-1])
                ci = d_abs / (0.015 * last_d)
                cis.append(float(ci))

                if len(cis) > 20:
                    np_ci = numpy.array(cis)
                    tci = talib.EMA(np_ci, 21)
                    wt1 = float(tci[-1])
                    wt1_last = wt1
                    wt1s.append(wt1)

                    if len(wt1s) > 3:
                        np_wt1 = numpy.array(wt1s)
                        wt2 = talib.SMA(np_wt1, 4)
                        wt2_last = float(wt2[-1])
        j = j + 1
    print("WWT Strategy initialized successfully!")

def initialize_orb():
    """Initialize Opening Range Breakout strategy"""
    global orb_high, orb_low, orb_range_set, orb_candle_count

    print("\nInitializing Opening Range Breakout Strategy...")
    print(f"Waiting for first {ORB_PERIOD} candles to establish opening range...")

    # Reset ORB variables
    orb_high = None
    orb_low = None
    orb_range_set = False
    orb_candle_count = 0

    print("ORB Strategy initialized - will establish range from first candles!")

def sell_amount():
    """Get available amount of asset to sell"""
    global SYMBOL
    bit = client.get_asset_balance(asset=SYMBOL)
    amount = float(bit['free'])
    return amount

def buy_amount(c):
    """Calculate amount to buy based on available USDT"""
    USDT_balance = client.get_asset_balance(asset='USDT')
    USDT_free = USDT_balance['free']
    amount = (1 / float(c)) * float(USDT_free)
    return amount

def order(side, c):
    """Execute buy or sell order"""
    global TRADE_SYMBOL, position

    order_type = ORDER_TYPE_MARKET

    if side == SIDE_BUY:
        quantity = buy_amount(c)
        # order = client.create_order(symbol=TRADE_SYMBOL, side=side, type=order_type, quantity=quantity)
        print(f"\n{'='*50}")
        print(f"  BUY SIGNAL - {TRADE_SYMBOL}")
        print(f"  Price: {c}")
        print(f"  Quantity: {quantity:.6f}")
        print(f"{'='*50}\n")
        position = True
    elif side == SIDE_SELL:
        quantity = sell_amount()
        # order = client.create_order(symbol=TRADE_SYMBOL, side=side, type=order_type, quantity=quantity)
        print(f"\n{'='*50}")
        print(f"  SELL SIGNAL - {TRADE_SYMBOL}")
        print(f"  Price: {c}")
        print(f"  Quantity: {quantity:.6f}")
        print(f"{'='*50}\n")
        position = False
        USDT_balance = client.get_asset_balance(asset='USDT')
        print(f"Balance: {USDT_balance['free']} USDT")

def process_wwt_strategy(h, l, c):
    """Process WWT (Weis Wave Volume) strategy"""
    global ap, ds, cis, wt1s, wt2_last, wt1_last, position

    ap_calc = (float(h) + float(l) + float(c)) / 3
    ap.append(float(ap_calc))
    np_ap = numpy.array(ap)
    esa = talib.EMA(np_ap, 10)
    last_esa = float(esa[-1])
    d_abs = abs(ap_calc - last_esa)
    ds.append(float(d_abs))
    np_d = numpy.array(ds)
    d = talib.EMA(np_d, 10)
    last_d = float(d[-1])
    ci = d_abs / (0.015 * last_d)
    cis.append(float(ci))
    np_ci = numpy.array(cis)
    wt1 = talib.EMA(np_ci, 21)
    wt1_current = float(wt1[-1])
    wt1s.append(wt1_current)
    np_wt1 = numpy.array(wt1s)
    wt2 = talib.SMA(np_wt1, 4)
    wt2_current = float(wt2[-1])

    print(f"WWT Indicators - WT1: {wt1_current:.4f}, WT2: {wt2_current:.4f}")

    # Trading logic based on WT1/WT2 crossover
    if wt1_last < wt2_last:
        if (wt1_current == wt2_current or wt1_current > wt2_current):
            if not position:
                order(SIDE_BUY, c)
    elif wt1_last > wt2_last:
        if (wt1_current == wt2_current or wt1_current < wt2_current):
            if position:
                order(SIDE_SELL, c)
    else:
        if wt1_current > wt2_current:
            if not position:
                order(SIDE_BUY, c)
        elif wt1_current < wt2_current:
            if position:
                order(SIDE_SELL, c)

    wt1_last = wt1_current
    wt2_last = wt2_current

def process_orb_strategy(o, h, l, c):
    """Process Opening Range Breakout strategy"""
    global orb_high, orb_low, orb_range_set, orb_candle_count, position

    current_high = float(h)
    current_low = float(l)
    current_close = float(c)
    current_open = float(o)

    # Phase 1: Establish opening range
    if not orb_range_set:
        orb_candle_count += 1

        if orb_high is None:
            orb_high = current_high
            orb_low = current_low
        else:
            orb_high = max(orb_high, current_high)
            orb_low = min(orb_low, current_low)

        print(f"Building ORB range ({orb_candle_count}/{ORB_PERIOD})")
        print(f"  Current Range - High: {orb_high:.2f}, Low: {orb_low:.2f}")

        if orb_candle_count >= ORB_PERIOD:
            orb_range_set = True
            range_size = orb_high - orb_low
            print(f"\n{'='*50}")
            print(f"  OPENING RANGE ESTABLISHED!")
            print(f"  Range High: {orb_high:.2f}")
            print(f"  Range Low: {orb_low:.2f}")
            print(f"  Range Size: {range_size:.2f}")
            print(f"{'='*50}\n")
        return

    # Phase 2: Trade breakouts
    print(f"ORB Status - High: {orb_high:.2f}, Low: {orb_low:.2f}, Current: {current_close:.2f}")

    # Breakout above range high - BUY signal
    if current_close > orb_high and not position:
        print(f"BREAKOUT ABOVE! Price {current_close:.2f} > Range High {orb_high:.2f}")
        order(SIDE_BUY, c)
        # Update range after breakout
        orb_high = current_high

    # Breakdown below range low - SELL signal (if in position)
    elif current_close < orb_low and position:
        print(f"BREAKDOWN BELOW! Price {current_close:.2f} < Range Low {orb_low:.2f}")
        order(SIDE_SELL, c)
        # Update range after breakdown
        orb_low = current_low

    # Stop loss: If price moves significantly against position
    elif position and current_close < orb_low:
        print(f"STOP LOSS TRIGGERED! Price {current_close:.2f} < Range Low {orb_low:.2f}")
        order(SIDE_SELL, c)

def on_open(ws):
    """WebSocket connection opened"""
    print('\nWebSocket connection opened')
    print(f'Trading {TRADE_SYMBOL} with {selected_strategy} strategy')
    print('Waiting for candle data...\n')

def on_close(ws, close_status_code, close_msg):
    """WebSocket connection closed"""
    print('WebSocket connection closed')

def on_message(ws, message):
    """Process incoming WebSocket message"""
    global selected_strategy

    json_message = json.loads(message)
    candle = json_message['k']
    is_candle_closed = candle['x']  # True when candle is closed

    o = candle['o']  # Open
    h = candle['h']  # High
    l = candle['l']  # Low
    c = candle['c']  # Close

    if is_candle_closed:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Candle closed at {c}")

        if selected_strategy == 'WWT':
            process_wwt_strategy(h, l, c)
        elif selected_strategy == 'ORB':
            process_orb_strategy(o, h, l, c)

def main():
    """Main function to run the trading bot"""
    global SYMBOL, TRADE_SYMBOL, kline, SOCKET, selected_strategy

    print("\n" + "="*50)
    print("    BINANCE TRADING BOT v2.0")
    print("    Enhanced with Strategy Selection")
    print("="*50)

    # Step 1: Select instrument
    SYMBOL, instrument_name = display_instrument_menu()
    print(f"\nSelected Instrument: {instrument_name} (Trading as {SYMBOL}USDT)")

    # Step 2: Select strategy
    selected_strategy = display_strategy_menu()
    print(f"\nSelected Strategy: {selected_strategy}")

    # Step 3: Select timeframe
    kline = get_timeframe()
    print(f"\nSelected Timeframe: {kline}")

    # Setup trading parameters
    SYM = SYMBOL.lower()
    Socket = "wss://stream.binance.com:9443/ws/"
    SOCKET = Socket + SYM + "usdt@kline_" + kline
    USDT = 'USDT'
    TRADE_SYMBOL = SYMBOL + USDT

    print(f"\n{'='*50}")
    print(f"  CONFIGURATION SUMMARY")
    print(f"{'='*50}")
    print(f"  Instrument: {instrument_name}")
    print(f"  Trading Pair: {TRADE_SYMBOL}")
    print(f"  Strategy: {selected_strategy}")
    print(f"  Timeframe: {kline}")
    print(f"  WebSocket: {SOCKET}")
    print(f"{'='*50}")

    # Initialize selected strategy
    if selected_strategy == 'WWT':
        initialize_wwt()
    elif selected_strategy == 'ORB':
        initialize_orb()

    # Confirm before starting
    confirm = input("\nStart trading bot? (yes/no): ").strip().lower()
    if confirm != 'yes' and confirm != 'y':
        print("Trading bot cancelled.")
        return

    # Start WebSocket connection
    print("\nStarting WebSocket connection...")
    ws = websocket.WebSocketApp(
        SOCKET,
        on_open=on_open,
        on_close=on_close,
        on_message=on_message
    )
    ws.run_forever()

if __name__ == "__main__":
    main()

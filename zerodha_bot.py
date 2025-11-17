#!/usr/bin/env python3
"""
Zerodha Trading Bot for Nifty 50 / Bank Nifty
Converted from Binance Trading Bot
Uses WTMFI (Williams Trend Multi-Frame Indicator) Strategy
"""

import json
import numpy
import talib
import pandas as pd
from datetime import datetime, timedelta
from kiteconnect import KiteConnect, KiteTicker
import zerodha_config as config
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('zerodha_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global variables
kite = None
kws = None
instrument_token = None
trading_symbol = None
position = False
ap = []
ds = []
cis = []
wt1s = []
wt2_last = 1.0000
wt1_last = 1.0000
current_candle = {}
last_candle_time = None

# Interval mapping for Kite
INTERVAL_MAP = {
    "1minute": "minute",
    "minute": "minute",
    "3minute": "3minute",
    "5minute": "5minute",
    "15minute": "15minute",
    "30minute": "30minute",
    "60minute": "60minute",
    "hour": "60minute",
    "day": "day"
}


def initialize_kite():
    """Initialize Kite Connect API connection"""
    global kite

    kite = KiteConnect(api_key=config.API_KEY)
    kite.set_access_token(config.ACCESS_TOKEN)

    # Verify connection
    try:
        profile = kite.profile()
        logger.info(f"Connected as: {profile['user_name']}")
        logger.info(f"Email: {profile['email']}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Kite API: {e}")
        logger.error("Please ensure your access token is valid and not expired")
        return False


def get_trading_symbol():
    """Get the trading symbol for Nifty/Bank Nifty futures"""
    global instrument_token, trading_symbol

    # Get current month's futures contract
    now = datetime.now()
    year = now.strftime("%y")
    month = now.strftime("%b").upper()

    # Construct futures symbol
    if config.INSTRUMENT == "NIFTY":
        base_symbol = "NIFTY"
    elif config.INSTRUMENT == "BANKNIFTY":
        base_symbol = "BANKNIFTY"
    else:
        logger.error(f"Invalid instrument: {config.INSTRUMENT}")
        sys.exit(1)

    # For futures: NIFTY24NOVFUT, BANKNIFTY24NOVFUT
    trading_symbol = f"{base_symbol}{year}{month}FUT"

    logger.info(f"Looking for instrument: {trading_symbol} on {config.EXCHANGE}")

    # Fetch instruments and find token
    try:
        instruments = kite.instruments(config.EXCHANGE)

        for instrument in instruments:
            if instrument['tradingsymbol'] == trading_symbol:
                instrument_token = instrument['instrument_token']
                logger.info(f"Found instrument token: {instrument_token}")
                logger.info(f"Lot size: {instrument['lot_size']}")
                logger.info(f"Tick size: {instrument['tick_size']}")
                return True

        # If current month futures not found, try next month
        next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
        next_year = next_month.strftime("%y")
        next_month_str = next_month.strftime("%b").upper()
        trading_symbol = f"{base_symbol}{next_year}{next_month_str}FUT"

        logger.info(f"Current month not found, trying: {trading_symbol}")

        for instrument in instruments:
            if instrument['tradingsymbol'] == trading_symbol:
                instrument_token = instrument['instrument_token']
                logger.info(f"Found instrument token: {instrument_token}")
                return True

        logger.error(f"Could not find instrument for {base_symbol}")
        return False

    except Exception as e:
        logger.error(f"Error fetching instruments: {e}")
        return False


def get_historical_data(days=10):
    """Fetch historical candle data for indicator initialization"""
    global kite, instrument_token

    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)

    interval = INTERVAL_MAP.get(config.INTERVAL, "5minute")

    logger.info(f"Fetching historical data from {from_date} to {to_date}")

    try:
        data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=interval
        )

        df = pd.DataFrame(data)
        logger.info(f"Fetched {len(df)} candles")
        return df
    except Exception as e:
        logger.error(f"Error fetching historical data: {e}")
        return None


def initialize_calc():
    """Initialize indicator calculations with historical data"""
    global ap, ds, cis, wt1s, wt2_last, wt1_last

    df = get_historical_data()
    if df is None or len(df) < 43:
        logger.error("Not enough historical data for indicator calculation")
        sys.exit(1)

    # Use last 43 candles for initialization
    df = df.tail(43).reset_index(drop=True)

    logger.info("Initializing indicators with historical data...")

    for j in range(len(df) - 1):  # Leave last candle for live update
        h = float(df.iloc[j]['high'])
        l = float(df.iloc[j]['low'])
        c = float(df.iloc[j]['close'])

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

    logger.info(f"Indicators initialized - WT1: {wt1_last:.4f}, WT2: {wt2_last:.4f}")


def get_margins():
    """Get available margins for trading"""
    try:
        margins = kite.margins()
        equity_margin = margins.get('equity', {}).get('available', {}).get('live_balance', 0)
        logger.info(f"Available margin: {equity_margin:.2f} INR")
        return float(equity_margin)
    except Exception as e:
        logger.error(f"Error fetching margins: {e}")
        return 0


def get_positions():
    """Get current positions"""
    try:
        positions = kite.positions()
        net_positions = positions.get('net', [])

        for pos in net_positions:
            if pos['tradingsymbol'] == trading_symbol:
                return pos
        return None
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return None


def calculate_quantity():
    """Calculate quantity based on lot size"""
    lot_size = config.LOT_SIZE.get(config.INSTRUMENT, 25)
    quantity = lot_size * config.NUM_LOTS
    logger.info(f"Order quantity: {quantity} (Lots: {config.NUM_LOTS}, Lot size: {lot_size})")
    return quantity


def place_order(transaction_type, price=0):
    """Place order on Zerodha"""
    global position, trading_symbol

    quantity = calculate_quantity()

    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=config.EXCHANGE,
            tradingsymbol=trading_symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            product=config.PRODUCT_TYPE,
            order_type=kite.ORDER_TYPE_MARKET if config.ORDER_TYPE == "MARKET" else kite.ORDER_TYPE_LIMIT,
            price=price if config.ORDER_TYPE == "LIMIT" else None,
            validity=kite.VALIDITY_DAY
        )

        if transaction_type == kite.TRANSACTION_TYPE_BUY:
            logger.info(f"BUY order placed! Order ID: {order_id}")
            position = True
        else:
            logger.info(f"SELL order placed! Order ID: {order_id}")
            position = False
            # Log P&L
            margins = get_margins()
            logger.info(f"Current available margin: {margins:.2f} INR")

        return order_id

    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return None


def process_candle(h, l, c):
    """Process completed candle and generate trading signals"""
    global ap, ds, cis, wt1s, wt2_last, wt1_last, position

    logger.info(f"Candle closed - High: {h:.2f}, Low: {l:.2f}, Close: {c:.2f}")

    # Calculate indicators
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

    logger.info(f"WT1: {wt1_current:.4f}, WT2: {wt2_current:.4f}")
    logger.info(f"Previous - WT1: {wt1_last:.4f}, WT2: {wt2_last:.4f}")

    # Trading logic - WTMFI Crossover Strategy
    if wt1_last < wt2_last:
        if wt1_current >= wt2_current:
            if not position:
                logger.info("BUY SIGNAL: WT1 crossed above WT2")
                place_order(kite.TRANSACTION_TYPE_BUY, c)
    elif wt1_last > wt2_last:
        if wt1_current <= wt2_current:
            if position:
                logger.info("SELL SIGNAL: WT1 crossed below WT2")
                place_order(kite.TRANSACTION_TYPE_SELL, c)
    else:
        if wt1_current > wt2_current:
            if not position:
                logger.info("BUY SIGNAL: WT1 > WT2")
                place_order(kite.TRANSACTION_TYPE_BUY, c)
        elif wt1_current < wt2_current:
            if position:
                logger.info("SELL SIGNAL: WT1 < WT2")
                place_order(kite.TRANSACTION_TYPE_SELL, c)

    # Update last values
    wt1_last = wt1_current
    wt2_last = wt2_current


def on_ticks(ws, ticks):
    """Handle incoming tick data from WebSocket"""
    global current_candle, last_candle_time

    for tick in ticks:
        if tick['instrument_token'] == instrument_token:
            # Get OHLC data
            ohlc = tick.get('ohlc', {})
            if ohlc:
                logger.debug(f"Tick - LTP: {tick['last_price']}, Open: {ohlc['open']}, High: {ohlc['high']}, Low: {ohlc['low']}, Close: {ohlc['close']}")


def on_connect(ws, response):
    """Called when WebSocket connection is established"""
    logger.info("WebSocket connected!")
    logger.info(f"Subscribing to {trading_symbol} (Token: {instrument_token})")

    # Subscribe to instrument
    ws.subscribe([instrument_token])

    # Set mode to full (includes OHLC data)
    ws.set_mode(ws.MODE_FULL, [instrument_token])


def on_close(ws, code, reason):
    """Called when WebSocket connection is closed"""
    logger.warning(f"WebSocket closed - Code: {code}, Reason: {reason}")


def on_error(ws, code, reason):
    """Called when WebSocket error occurs"""
    logger.error(f"WebSocket error - Code: {code}, Reason: {reason}")


def on_reconnect(ws, attempts_count):
    """Called when WebSocket tries to reconnect"""
    logger.info(f"WebSocket reconnecting... Attempt {attempts_count}")


def on_noreconnect(ws):
    """Called when WebSocket has exhausted all reconnection attempts"""
    logger.error("WebSocket reconnection failed!")


def start_ticker():
    """Start WebSocket ticker for real-time data"""
    global kws

    kws = KiteTicker(config.API_KEY, config.ACCESS_TOKEN)

    # Assign callbacks
    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.on_close = on_close
    kws.on_error = on_error
    kws.on_reconnect = on_reconnect
    kws.on_noreconnect = on_noreconnect

    logger.info("Starting WebSocket ticker...")

    # Connect to WebSocket (blocking call)
    kws.connect(threaded=False)


def run_polling_mode():
    """
    Alternative to WebSocket - Poll for candle data
    This is more reliable for candle-based strategies
    """
    global last_candle_time

    import time

    interval_seconds = {
        "minute": 60,
        "3minute": 180,
        "5minute": 300,
        "15minute": 900,
        "30minute": 1800,
        "60minute": 3600,
        "day": 86400
    }

    poll_interval = interval_seconds.get(INTERVAL_MAP.get(config.INTERVAL, "5minute"), 300)

    logger.info(f"Starting polling mode with {poll_interval}s interval...")
    logger.info(f"Trading {trading_symbol} on {config.EXCHANGE}")
    logger.info(f"Product type: {config.PRODUCT_TYPE}")

    # Get initial candle time
    df = get_historical_data(days=1)
    if df is not None and len(df) > 0:
        last_candle_time = df.iloc[-1]['date']
        logger.info(f"Last candle time: {last_candle_time}")

    while True:
        try:
            # Wait for next candle
            time.sleep(poll_interval)

            # Fetch latest candle
            df = get_historical_data(days=1)
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]

                # Check if it's a new candle
                if last_candle_time is None or latest['date'] > last_candle_time:
                    last_candle_time = latest['date']

                    # Process the completed candle
                    process_candle(
                        latest['high'],
                        latest['low'],
                        latest['close']
                    )
                else:
                    logger.debug("No new candle yet...")

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in polling loop: {e}")
            time.sleep(60)  # Wait a minute before retrying


def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("Zerodha Trading Bot - Nifty 50 / Bank Nifty")
    logger.info("Strategy: WTMFI (Williams Trend Multi-Frame Indicator)")
    logger.info("=" * 50)

    # Initialize Kite connection
    if not initialize_kite():
        sys.exit(1)

    # Get trading symbol
    if not get_trading_symbol():
        sys.exit(1)

    # Display configuration
    logger.info(f"Instrument: {config.INSTRUMENT}")
    logger.info(f"Trading Symbol: {trading_symbol}")
    logger.info(f"Exchange: {config.EXCHANGE}")
    logger.info(f"Product Type: {config.PRODUCT_TYPE}")
    logger.info(f"Candle Interval: {config.INTERVAL}")
    logger.info(f"Number of Lots: {config.NUM_LOTS}")

    # Check margins
    margins = get_margins()
    if margins < 50000:  # Minimum recommended margin for index F&O
        logger.warning(f"Low margin balance: {margins:.2f} INR")
        logger.warning("Recommended minimum margin for index F&O is 50,000 INR")

    # Check existing positions
    existing_pos = get_positions()
    if existing_pos:
        global position
        position = existing_pos['quantity'] > 0
        logger.info(f"Existing position found: {existing_pos['quantity']} units")

    # Initialize indicators
    initialize_calc()

    # Choose mode
    print("\nSelect trading mode:")
    print("1. Polling Mode (Recommended - fetches candles at interval)")
    print("2. WebSocket Mode (Real-time ticks)")

    mode = input("\nEnter choice (1 or 2): ").strip()

    if mode == "2":
        logger.info("Starting WebSocket mode...")
        start_ticker()
    else:
        logger.info("Starting Polling mode...")
        run_polling_mode()


if __name__ == "__main__":
    main()

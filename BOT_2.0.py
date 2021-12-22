import websocket, json, pprint, numpy, talib
from binance.client import Client
from binance.enums import *
import pandas as pd
import config

SYMBOL = input("Enter Crypto symbol (BTC for Bitcoin) : ")
kline = input("Enter kline value (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 12h, 1D, 3D, 1W, 1M) : ")
SYM = SYMBOL.lower()
Socket = "wss://stream.binance.com:9443/ws/"
SOCKET = Socket + SYM + "usdt@kline_" + kline
client = Client(config.KEY, config.SECRET, tld='com')
USDT = 'USDT'
TRADE_SYMBOL = SYMBOL + USDT
position = False
ap = []
ds = []
cis = []
wt1s = []
wt2_last = 1.0000
wt1_last = 1.0000


def initialize_calc():
    global TRADE_SYMBOL
    global kline
    global ap
    global ds
    global cis
    global wt1s
    global wt2_last
    global wt1_last

    hist_data = client.get_klines(symbol=TRADE_SYMBOL, interval=kline, limit=43)
    D=pd.DataFrame(hist_data)
    D.columns=['open_time','open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol','is_best_match']
    i=42
    j=0
    while j<i:
        h=float(D['high'][j])
        l=float(D['low'][j])
        c=float(D['close'][j])
        ap_calc=(h+l+c)/3
        ap.append(ap_calc)

        if len(ap) > 9:
            np_ap = numpy.array(ap)
            esa = talib.EMA(np_ap,10)
            last_esa = float(esa[-1])
            d_abs = abs(ap_calc-last_esa)
            ds.append(float(d_abs))

            if len(ds)>9:
                np_d = numpy.array(ds)
                d = talib.EMA(np_d, 10)
                last_d = float(d[-1])
                ci = d_abs/(0.015*last_d)
                cis.append(float(ci))

                if len(cis)>20:
                    np_ci = numpy.array(cis)
                    tci = talib.EMA(np_ci, 21)
                    wt1 = float(tci[-1])
                    wt1_last = wt1
                    wt1s.append(wt1)

                    if len(wt1s)>3:
                        np_wt1 = numpy.array(wt1s)
                        wt2 = talib.SMA(np_wt1, 4)
                        wt2_last = float(wt2[-1])
        j=j+1

def sell_amount():
    global SYMBOL
    bit = client.get_asset_balance(asset=SYMBOL)
    amount = float( bit['free'])
    return amount

def buy_amount(c):
    USDT = client.get_asset_balance(asset='USDT')
    USDT1 = USDT['free']
    amount = (1/float(c))*float(USDT1)
    return amount

def order(side,c):
    global TRADE_SYMBOL
    global position

    order_type=ORDER_TYPE_MARKET
    
    if side == SIDE_BUY:
        quantity = buy_amount(c)
        #order = client.create_order(symbol=TRADE_SYMBOL, side=side, type=order_type, quantity=quantity)
        print("BOUGHT!")
        position = True
    elif side == SIDE_SELL:
        quantity = sell_amount()
        #order = client.create_order(symbol=TRADE_SYMBOL, side=side, type=order_type, quantity=quantity)
        print("SOLD!")
        position = False
        USDT = client.get_asset_balance(asset='USDT')
        print("balance : {} USDT".format(USDT['free']))

def on_open(ws):
    print('opened connection')

def on_close(ws): 
    print('closed connection')

def on_message(ws, message):
    global ap
    global ds
    global cis
    global wt1s
    global wt2_last
    global wt1_last
    global TRADE_SYMBOL

    json_message = json.loads(message)
    candle = json_message['k']
    #is_candle_closed = candle['x']
    is_candle_closed = True
    o = candle['o']
    h = candle['h']
    l = candle['l']
    c = candle['c']

    if is_candle_closed:
        print("candle closed at {}".format(c))
        ap_calc = (float(h)+float(l)+float(c))/3
        ap.append(float(ap_calc))
        np_ap = numpy.array(ap)
        esa = talib.EMA(np_ap, 10)
        last_esa = float(esa[-1])
        d_abs = abs(ap_calc-last_esa)
        ds.append(float(d_abs))
        np_d = numpy.array(ds)
        d = talib.EMA(np_d, 10)
        last_d = float(d[-1])
        ci = d_abs/(0.015*last_d)
        cis.append(float(ci))
        np_ci = numpy.array(cis)
        wt1 = talib.EMA(np_ci, 21)
        wt1_current = float(wt1[-1])
        wt1s.append(wt1_current)
        np_wt1 = numpy.array(wt1s)
        wt2 = talib.SMA(np_wt1, 4)
        wt2_current = float(wt2[-1])

        if wt1_last < wt2_last:
            if (wt1_current == wt2_current or wt1_current > wt2_current):
                if not position:
                    order(SIDE_BUY,c)
        elif wt1_last > wt2_last:
            if (wt1_current == wt2_current or wt1_current < wt2_current):
                if position:
                    order(SIDE_SELL,c)
        else:
            if wt1_current > wt2_current:
                if not position:
                    order(SIDE_BUY,c)
            elif wt1_current < wt2_current:
                if position:
                    order(SIDE_SELL,c)
        wt1_last = wt1_current
        wt2_last = wt2_current

initialize_calc()
ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()





//live socket
def on_open(ws):
    print('opened connection')

def on_close(ws): 
    print('closed connection')

def on_message(ws, message):
    json_message = json.loads(message)
    candle = json_message['k']
    is_candle_closed = candle['x']
    #is_candle_closed = True
    o = candle['o']
    h = candle['h']
    l = candle['l']
    c = candle['c']

ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()

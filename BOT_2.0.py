#!/usr/bin/env python3
"""
Binance Trading Bot v2.0
Enhanced with risk management, logging, and multiple strategies
"""

import websocket
import json
import numpy as np
import talib
import pandas as pd
import logging
import csv
import time
import sys
from datetime import datetime, date
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceRequestException
import config


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Trade:
    """Represents a single trade"""
    timestamp: str
    symbol: str
    side: str
    price: float
    quantity: float
    value: float
    strategy: str
    pnl: float = 0.0
    pnl_percent: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0


@dataclass
class Position:
    """Represents current position"""
    symbol: str
    entry_price: float
    quantity: float
    side: str  # 'LONG' or 'FLAT'
    stop_loss: float
    take_profit: float
    entry_time: str


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure logging with both file and console handlers"""
    logger = logging.getLogger('TradingBot')
    logger.setLevel(getattr(logging, config.LOG_LEVEL))

    # File handler
    file_handler = logging.FileHandler(config.LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_format)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# ============================================================================
# TRADE JOURNAL
# ============================================================================

class TradeJournal:
    """Manages trade history and performance metrics"""

    def __init__(self, filename: str):
        self.filename = filename
        self.trades: List[Trade] = []
        self.daily_pnl = 0.0
        self.peak_balance = 0.0
        self.current_balance = 0.0
        self._initialize_journal()

    def _initialize_journal(self):
        """Create journal file with headers if it doesn't exist"""
        try:
            with open(self.filename, 'x', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'side', 'price', 'quantity',
                    'value', 'strategy', 'pnl', 'pnl_percent',
                    'stop_loss', 'take_profit'
                ])
        except FileExistsError:
            pass

    def record_trade(self, trade: Trade):
        """Record a trade to journal"""
        self.trades.append(trade)
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                trade.timestamp, trade.symbol, trade.side, trade.price,
                trade.quantity, trade.value, trade.strategy, trade.pnl,
                trade.pnl_percent, trade.stop_loss, trade.take_profit
            ])

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L tracking"""
        self.daily_pnl += pnl

    def reset_daily_pnl(self):
        """Reset daily P&L (call at start of each day)"""
        self.daily_pnl = 0.0

    def update_balance(self, balance: float):
        """Update balance and peak tracking"""
        self.current_balance = balance
        if balance > self.peak_balance:
            self.peak_balance = balance

    def get_drawdown(self) -> float:
        """Calculate current drawdown from peak"""
        if self.peak_balance == 0:
            return 0.0
        return (self.peak_balance - self.current_balance) / self.peak_balance

    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics"""
        if not self.trades:
            return {}

        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.trades) if self.trades else 0,
            'total_pnl': sum(t.pnl for t in self.trades),
            'avg_pnl': sum(t.pnl for t in self.trades) / len(self.trades),
            'daily_pnl': self.daily_pnl,
            'current_drawdown': self.get_drawdown(),
        }


# ============================================================================
# RISK MANAGER
# ============================================================================

class RiskManager:
    """Manages risk and position sizing"""

    def __init__(self, journal: TradeJournal, logger: logging.Logger):
        self.journal = journal
        self.logger = logger

    def calculate_position_size(self, balance: float, price: float) -> float:
        """Calculate position size based on risk parameters"""
        # Risk-based position sizing
        risk_amount = balance * config.RISK_PER_TRADE
        max_position_value = balance * config.MAX_POSITION_SIZE

        # Use the smaller of risk-based or max position
        position_value = min(risk_amount / config.STOP_LOSS_PERCENT, max_position_value)
        quantity = position_value / price

        self.logger.debug(f"Position size calculated: {quantity:.6f} (value: {position_value:.2f})")
        return quantity

    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """Calculate stop loss price"""
        if side == 'BUY':
            return entry_price * (1 - config.STOP_LOSS_PERCENT)
        else:
            return entry_price * (1 + config.STOP_LOSS_PERCENT)

    def calculate_take_profit(self, entry_price: float, side: str) -> float:
        """Calculate take profit price"""
        if side == 'BUY':
            return entry_price * (1 + config.TAKE_PROFIT_PERCENT)
        else:
            return entry_price * (1 - config.TAKE_PROFIT_PERCENT)

    def check_daily_loss_limit(self, initial_balance: float) -> bool:
        """Check if daily loss limit has been reached"""
        if initial_balance == 0:
            return False
        daily_loss_percent = abs(self.journal.daily_pnl) / initial_balance
        if self.journal.daily_pnl < 0 and daily_loss_percent >= config.MAX_DAILY_LOSS:
            self.logger.warning(f"Daily loss limit reached: {daily_loss_percent:.2%}")
            return True
        return False

    def check_max_drawdown(self) -> bool:
        """Check if maximum drawdown has been reached"""
        drawdown = self.journal.get_drawdown()
        if drawdown >= config.MAX_DRAWDOWN:
            self.logger.warning(f"Maximum drawdown reached: {drawdown:.2%}")
            return True
        return False

    def should_stop_trading(self, initial_balance: float) -> bool:
        """Check if trading should be stopped due to risk limits"""
        return self.check_daily_loss_limit(initial_balance) or self.check_max_drawdown()


# ============================================================================
# PAPER TRADING
# ============================================================================

class PaperTrader:
    """Simulates trading without real money"""

    def __init__(self, initial_balance: float, logger: logging.Logger):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.holdings: Dict[str, float] = {}
        self.logger = logger

    def get_balance(self, asset: str = 'USDT') -> float:
        """Get balance of an asset"""
        if asset == 'USDT':
            return self.balance
        return self.holdings.get(asset, 0.0)

    def execute_buy(self, symbol: str, quantity: float, price: float) -> bool:
        """Execute a paper buy order"""
        cost = quantity * price
        if cost > self.balance:
            self.logger.warning(f"Insufficient balance for buy: {cost:.2f} > {self.balance:.2f}")
            return False

        self.balance -= cost
        asset = symbol.replace('USDT', '')
        self.holdings[asset] = self.holdings.get(asset, 0) + quantity

        self.logger.info(f"PAPER BUY: {quantity:.6f} {asset} @ {price:.2f} (Cost: {cost:.2f})")
        return True

    def execute_sell(self, symbol: str, quantity: float, price: float) -> bool:
        """Execute a paper sell order"""
        asset = symbol.replace('USDT', '')
        if self.holdings.get(asset, 0) < quantity:
            self.logger.warning(f"Insufficient holdings for sell")
            return False

        revenue = quantity * price
        self.holdings[asset] -= quantity
        self.balance += revenue

        self.logger.info(f"PAPER SELL: {quantity:.6f} {asset} @ {price:.2f} (Revenue: {revenue:.2f})")
        return True


# ============================================================================
# STRATEGIES (Abstract Base Class)
# ============================================================================

class Strategy(ABC):
    """Abstract base class for trading strategies"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.name = "BaseStrategy"

    @abstractmethod
    def initialize(self, historical_data: pd.DataFrame):
        """Initialize strategy with historical data"""
        pass

    @abstractmethod
    def process_candle(self, o: float, h: float, l: float, c: float) -> Optional[str]:
        """Process a candle and return signal: 'BUY', 'SELL', or None"""
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        pass


class WWTStrategy(Strategy):
    """Weis Wave Volume Trading Strategy"""

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)
        self.name = "WWT"
        self.ap = []
        self.ds = []
        self.cis = []
        self.wt1s = []
        self.wt2_last = 1.0
        self.wt1_last = 1.0

    def initialize(self, historical_data: pd.DataFrame):
        """Initialize with historical candle data"""
        self.logger.info("Initializing WWT Strategy...")

        for i in range(len(historical_data) - 1):
            h = float(historical_data['high'].iloc[i])
            l = float(historical_data['low'].iloc[i])
            c = float(historical_data['close'].iloc[i])

            ap_calc = (h + l + c) / 3
            self.ap.append(ap_calc)

            if len(self.ap) > config.WWT_EMA_PERIOD - 1:
                np_ap = np.array(self.ap)
                esa = talib.EMA(np_ap, config.WWT_EMA_PERIOD)
                last_esa = float(esa[-1])
                d_abs = abs(ap_calc - last_esa)
                self.ds.append(float(d_abs))

                if len(self.ds) > config.WWT_EMA_PERIOD - 1:
                    np_d = np.array(self.ds)
                    d = talib.EMA(np_d, config.WWT_EMA_PERIOD)
                    last_d = float(d[-1])
                    ci = d_abs / (0.015 * last_d) if last_d != 0 else 0
                    self.cis.append(float(ci))

                    if len(self.cis) > config.WWT_CI_EMA_PERIOD - 1:
                        np_ci = np.array(self.cis)
                        tci = talib.EMA(np_ci, config.WWT_CI_EMA_PERIOD)
                        wt1 = float(tci[-1])
                        self.wt1_last = wt1
                        self.wt1s.append(wt1)

                        if len(self.wt1s) > config.WWT_WT2_SMA_PERIOD - 1:
                            np_wt1 = np.array(self.wt1s)
                            wt2 = talib.SMA(np_wt1, config.WWT_WT2_SMA_PERIOD)
                            self.wt2_last = float(wt2[-1])

        self.logger.info("WWT Strategy initialized successfully!")

    def process_candle(self, o: float, h: float, l: float, c: float) -> Optional[str]:
        """Process candle and return trading signal"""
        ap_calc = (h + l + c) / 3
        self.ap.append(float(ap_calc))

        np_ap = np.array(self.ap)
        esa = talib.EMA(np_ap, config.WWT_EMA_PERIOD)
        last_esa = float(esa[-1])
        d_abs = abs(ap_calc - last_esa)
        self.ds.append(float(d_abs))

        np_d = np.array(self.ds)
        d = talib.EMA(np_d, config.WWT_EMA_PERIOD)
        last_d = float(d[-1])
        ci = d_abs / (0.015 * last_d) if last_d != 0 else 0
        self.cis.append(float(ci))

        np_ci = np.array(self.cis)
        wt1 = talib.EMA(np_ci, config.WWT_CI_EMA_PERIOD)
        wt1_current = float(wt1[-1])
        self.wt1s.append(wt1_current)

        np_wt1 = np.array(self.wt1s)
        wt2 = talib.SMA(np_wt1, config.WWT_WT2_SMA_PERIOD)
        wt2_current = float(wt2[-1])

        self.logger.debug(f"WWT: WT1={wt1_current:.4f}, WT2={wt2_current:.4f}")

        signal = None

        # Crossover detection
        if self.wt1_last < self.wt2_last:
            if wt1_current >= wt2_current:
                signal = 'BUY'
        elif self.wt1_last > self.wt2_last:
            if wt1_current <= wt2_current:
                signal = 'SELL'

        self.wt1_last = wt1_current
        self.wt2_last = wt2_current

        return signal

    def get_parameters(self) -> Dict[str, Any]:
        return {
            'ema_period': config.WWT_EMA_PERIOD,
            'ci_ema_period': config.WWT_CI_EMA_PERIOD,
            'wt2_sma_period': config.WWT_WT2_SMA_PERIOD
        }


class ORBStrategy(Strategy):
    """Opening Range Breakout Strategy"""

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)
        self.name = "ORB"
        self.orb_high = None
        self.orb_low = None
        self.orb_range_set = False
        self.candle_count = 0

    def initialize(self, historical_data: pd.DataFrame):
        """Initialize ORB strategy"""
        self.logger.info("Initializing ORB Strategy...")
        self.logger.info(f"Will establish range from first {config.ORB_PERIOD} candles")

        # Reset state
        self.orb_high = None
        self.orb_low = None
        self.orb_range_set = False
        self.candle_count = 0

        self.logger.info("ORB Strategy initialized!")

    def process_candle(self, o: float, h: float, l: float, c: float) -> Optional[str]:
        """Process candle and return trading signal"""
        # Phase 1: Build opening range
        if not self.orb_range_set:
            self.candle_count += 1

            if self.orb_high is None:
                self.orb_high = h
                self.orb_low = l
            else:
                self.orb_high = max(self.orb_high, h)
                self.orb_low = min(self.orb_low, l)

            self.logger.info(f"Building ORB range ({self.candle_count}/{config.ORB_PERIOD})")
            self.logger.info(f"  Range: High={self.orb_high:.2f}, Low={self.orb_low:.2f}")

            if self.candle_count >= config.ORB_PERIOD:
                self.orb_range_set = True
                range_size = self.orb_high - self.orb_low
                self.logger.info(f"OPENING RANGE ESTABLISHED!")
                self.logger.info(f"  High: {self.orb_high:.2f}")
                self.logger.info(f"  Low: {self.orb_low:.2f}")
                self.logger.info(f"  Size: {range_size:.2f}")

            return None

        # Phase 2: Trade breakouts
        buffer = self.orb_high * config.ORB_BREAKOUT_BUFFER

        self.logger.debug(f"ORB: High={self.orb_high:.2f}, Low={self.orb_low:.2f}, Close={c:.2f}")

        # Breakout above range
        if c > self.orb_high + buffer:
            self.logger.info(f"BREAKOUT ABOVE! {c:.2f} > {self.orb_high:.2f}")
            self.orb_high = h  # Update range
            return 'BUY'

        # Breakdown below range
        if c < self.orb_low - buffer:
            self.logger.info(f"BREAKDOWN BELOW! {c:.2f} < {self.orb_low:.2f}")
            self.orb_low = l  # Update range
            return 'SELL'

        return None

    def get_parameters(self) -> Dict[str, Any]:
        return {
            'orb_period': config.ORB_PERIOD,
            'breakout_buffer': config.ORB_BREAKOUT_BUFFER
        }


# ============================================================================
# MAIN TRADING BOT
# ============================================================================

class TradingBot:
    """Main trading bot orchestrator"""

    def __init__(self):
        self.logger = setup_logging()
        self.journal = TradeJournal(config.TRADE_JOURNAL_FILE)
        self.risk_manager = RiskManager(self.journal, self.logger)
        self.strategy: Optional[Strategy] = None
        self.position: Optional[Position] = None
        self.symbol = ''
        self.trade_symbol = ''
        self.kline = ''
        self.socket_url = ''
        self.ws = None
        self.reconnect_count = 0
        self.running = False

        # Paper or live trading
        if config.PAPER_TRADING:
            self.paper_trader = PaperTrader(config.INITIAL_PAPER_BALANCE, self.logger)
            self.initial_balance = config.INITIAL_PAPER_BALANCE
            self.client = None
            self.logger.info("Running in PAPER TRADING mode")
        else:
            self.paper_trader = None
            self.client = Client(config.KEY, config.SECRET, tld='com')
            self.initial_balance = self._get_usdt_balance()
            self.logger.info("Running in LIVE TRADING mode")

        self.journal.update_balance(self.initial_balance)
        self.journal.peak_balance = self.initial_balance

    def _get_usdt_balance(self) -> float:
        """Get USDT balance from Binance"""
        try:
            if self.paper_trader:
                return self.paper_trader.get_balance('USDT')
            balance = self.client.get_asset_balance(asset='USDT')
            return float(balance['free'])
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return 0.0

    def _get_asset_balance(self, asset: str) -> float:
        """Get asset balance"""
        try:
            if self.paper_trader:
                return self.paper_trader.get_balance(asset)
            balance = self.client.get_asset_balance(asset=asset)
            return float(balance['free'])
        except Exception as e:
            self.logger.error(f"Error getting {asset} balance: {e}")
            return 0.0

    def _validate_input(self, prompt: str, valid_options: List[str]) -> str:
        """Validate user input against valid options"""
        while True:
            user_input = input(prompt).strip()
            if user_input in valid_options:
                return user_input
            print(f"Invalid input. Valid options: {', '.join(valid_options)}")

    def select_instrument(self):
        """Interactive instrument selection"""
        print("\n" + "=" * 50)
        print("        INSTRUMENT SELECTION")
        print("=" * 50)
        print("1. NIFTY50 (BTC as proxy)")
        print("2. BANKNIFTY (ETH as proxy)")
        print("3. Custom Symbol")
        print("=" * 50)

        choice = self._validate_input("Select instrument (1-3): ", ['1', '2', '3'])

        if choice == '1':
            return 'BTC', 'NIFTY50'
        elif choice == '2':
            return 'ETH', 'BANKNIFTY'
        else:
            custom = input("Enter symbol (e.g., BTC, ETH, BNB): ").strip().upper()
            if not custom:
                print("Invalid symbol. Using BTC.")
                custom = 'BTC'
            return custom, custom

    def select_strategy(self):
        """Interactive strategy selection"""
        print("\n" + "=" * 50)
        print("        STRATEGY SELECTION")
        print("=" * 50)
        print("1. Weis Wave Volume (WWT) Strategy")
        print("   - Crossover-based trend following")
        print("")
        print("2. Opening Range Breakout (ORB) Strategy")
        print("   - Momentum-based breakout trading")
        print("=" * 50)

        choice = self._validate_input("Select strategy (1-2): ", ['1', '2'])

        if choice == '1':
            return WWTStrategy(self.logger)
        else:
            return ORBStrategy(self.logger)

    def select_timeframe(self) -> str:
        """Interactive timeframe selection"""
        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '12h', '1d', '3d', '1w', '1M']

        print("\n" + "=" * 50)
        print("        TIMEFRAME SELECTION")
        print("=" * 50)
        print(f"Available: {', '.join(valid_timeframes)}")
        print("=" * 50)

        return self._validate_input("Enter timeframe: ", valid_timeframes)

    def fetch_historical_data(self) -> pd.DataFrame:
        """Fetch historical candle data for strategy initialization"""
        self.logger.info(f"Fetching historical data for {self.trade_symbol}...")

        try:
            if self.paper_trader:
                # For paper trading, we still need real market data
                temp_client = Client(config.KEY, config.SECRET, tld='com')
                hist_data = temp_client.get_klines(
                    symbol=self.trade_symbol,
                    interval=self.kline,
                    limit=50
                )
            else:
                hist_data = self.client.get_klines(
                    symbol=self.trade_symbol,
                    interval=self.kline,
                    limit=50
                )

            df = pd.DataFrame(hist_data)
            df.columns = [
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'qav', 'num_trades', 'taker_base_vol',
                'taker_quote_vol', 'is_best_match'
            ]

            # Convert to float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            self.logger.info(f"Fetched {len(df)} historical candles")
            return df

        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}")
            raise

    def execute_order(self, side: str, price: float, signal_type: str = 'STRATEGY'):
        """Execute a buy or sell order with risk management"""
        if self.risk_manager.should_stop_trading(self.initial_balance):
            self.logger.warning("Trading halted due to risk limits!")
            return

        timestamp = datetime.now().isoformat()

        if side == 'BUY' and self.position is None:
            # Calculate position size
            balance = self._get_usdt_balance()
            quantity = self.risk_manager.calculate_position_size(balance, price)

            # Calculate stop loss and take profit
            stop_loss = self.risk_manager.calculate_stop_loss(price, 'BUY')
            take_profit = self.risk_manager.calculate_take_profit(price, 'BUY')

            # Execute order
            if self.paper_trader:
                success = self.paper_trader.execute_buy(self.trade_symbol, quantity, price)
            else:
                try:
                    # Live order (commented for safety)
                    # order = self.client.create_order(
                    #     symbol=self.trade_symbol,
                    #     side=SIDE_BUY,
                    #     type=ORDER_TYPE_MARKET,
                    #     quantity=quantity
                    # )
                    success = True
                    self.logger.info(f"LIVE BUY ORDER: {quantity:.6f} @ {price:.2f}")
                except Exception as e:
                    self.logger.error(f"Order execution failed: {e}")
                    success = False

            if success:
                self.position = Position(
                    symbol=self.trade_symbol,
                    entry_price=price,
                    quantity=quantity,
                    side='LONG',
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    entry_time=timestamp
                )

                trade = Trade(
                    timestamp=timestamp,
                    symbol=self.trade_symbol,
                    side='BUY',
                    price=price,
                    quantity=quantity,
                    value=quantity * price,
                    strategy=self.strategy.name,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                self.journal.record_trade(trade)

                self.logger.info(f"{'='*50}")
                self.logger.info(f"  BUY ORDER EXECUTED")
                self.logger.info(f"  Price: {price:.2f}")
                self.logger.info(f"  Quantity: {quantity:.6f}")
                self.logger.info(f"  Stop Loss: {stop_loss:.2f}")
                self.logger.info(f"  Take Profit: {take_profit:.2f}")
                self.logger.info(f"{'='*50}")

        elif side == 'SELL' and self.position is not None:
            quantity = self.position.quantity
            entry_price = self.position.entry_price

            # Execute order
            if self.paper_trader:
                success = self.paper_trader.execute_sell(self.trade_symbol, quantity, price)
            else:
                try:
                    # Live order (commented for safety)
                    # order = self.client.create_order(
                    #     symbol=self.trade_symbol,
                    #     side=SIDE_SELL,
                    #     type=ORDER_TYPE_MARKET,
                    #     quantity=quantity
                    # )
                    success = True
                    self.logger.info(f"LIVE SELL ORDER: {quantity:.6f} @ {price:.2f}")
                except Exception as e:
                    self.logger.error(f"Order execution failed: {e}")
                    success = False

            if success:
                # Calculate P&L
                pnl = (price - entry_price) * quantity
                pnl_percent = (price - entry_price) / entry_price

                trade = Trade(
                    timestamp=timestamp,
                    symbol=self.trade_symbol,
                    side='SELL',
                    price=price,
                    quantity=quantity,
                    value=quantity * price,
                    strategy=self.strategy.name,
                    pnl=pnl,
                    pnl_percent=pnl_percent
                )
                self.journal.record_trade(trade)
                self.journal.update_daily_pnl(pnl)

                # Update balance
                new_balance = self._get_usdt_balance()
                self.journal.update_balance(new_balance)

                self.logger.info(f"{'='*50}")
                self.logger.info(f"  SELL ORDER EXECUTED")
                self.logger.info(f"  Price: {price:.2f}")
                self.logger.info(f"  Quantity: {quantity:.6f}")
                self.logger.info(f"  P&L: {pnl:.2f} ({pnl_percent:.2%})")
                self.logger.info(f"  Balance: {new_balance:.2f} USDT")
                self.logger.info(f"{'='*50}")

                self.position = None

    def check_stop_loss_take_profit(self, current_price: float):
        """Check if stop loss or take profit has been hit"""
        if self.position is None:
            return

        if current_price <= self.position.stop_loss:
            self.logger.warning(f"STOP LOSS TRIGGERED @ {current_price:.2f}")
            self.execute_order('SELL', current_price, 'STOP_LOSS')

        elif current_price >= self.position.take_profit:
            self.logger.info(f"TAKE PROFIT TRIGGERED @ {current_price:.2f}")
            self.execute_order('SELL', current_price, 'TAKE_PROFIT')

    def on_open(self, ws):
        """WebSocket connection opened"""
        self.logger.info("WebSocket connection opened")
        self.logger.info(f"Trading {self.trade_symbol} with {self.strategy.name} strategy")
        self.reconnect_count = 0

    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        self.logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")

        if self.running and self.reconnect_count < config.WS_RECONNECT_ATTEMPTS:
            self.reconnect_count += 1
            delay = config.WS_RECONNECT_DELAY * self.reconnect_count
            self.logger.info(f"Reconnecting in {delay} seconds (attempt {self.reconnect_count})")
            time.sleep(delay)
            self._connect_websocket()

    def on_error(self, ws, error):
        """WebSocket error handler"""
        self.logger.error(f"WebSocket error: {error}")

    def on_message(self, ws, message):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            candle = data['k']
            is_closed = candle['x']

            o = float(candle['o'])
            h = float(candle['h'])
            l = float(candle['l'])
            c = float(candle['c'])

            # Check stop loss / take profit on every tick
            if self.position:
                self.check_stop_loss_take_profit(c)

            # Process strategy only on candle close
            if is_closed:
                self.logger.info(f"Candle closed @ {c:.2f}")

                # Get strategy signal
                signal = self.strategy.process_candle(o, h, l, c)

                if signal == 'BUY' and self.position is None:
                    self.execute_order('BUY', c)
                elif signal == 'SELL' and self.position is not None:
                    self.execute_order('SELL', c)

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
        except KeyError as e:
            self.logger.error(f"Missing key in message: {e}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _connect_websocket(self):
        """Establish WebSocket connection"""
        self.ws = websocket.WebSocketApp(
            self.socket_url,
            on_open=self.on_open,
            on_close=self.on_close,
            on_message=self.on_message,
            on_error=self.on_error
        )
        self.ws.run_forever()

    def display_config_summary(self, instrument_name: str):
        """Display configuration summary"""
        print(f"\n{'='*50}")
        print(f"  CONFIGURATION SUMMARY")
        print(f"{'='*50}")
        print(f"  Mode: {'PAPER' if config.PAPER_TRADING else 'LIVE'} TRADING")
        print(f"  Instrument: {instrument_name}")
        print(f"  Trading Pair: {self.trade_symbol}")
        print(f"  Strategy: {self.strategy.name}")
        print(f"  Timeframe: {self.kline}")
        print(f"  Initial Balance: {self.initial_balance:.2f} USDT")
        print(f"{'='*50}")
        print(f"  RISK MANAGEMENT")
        print(f"{'='*50}")
        print(f"  Risk per Trade: {config.RISK_PER_TRADE:.1%}")
        print(f"  Max Position Size: {config.MAX_POSITION_SIZE:.1%}")
        print(f"  Stop Loss: {config.STOP_LOSS_PERCENT:.1%}")
        print(f"  Take Profit: {config.TAKE_PROFIT_PERCENT:.1%}")
        print(f"  Max Daily Loss: {config.MAX_DAILY_LOSS:.1%}")
        print(f"  Max Drawdown: {config.MAX_DRAWDOWN:.1%}")
        print(f"{'='*50}")

    def run(self):
        """Main bot execution"""
        print("\n" + "=" * 50)
        print("    BINANCE TRADING BOT v2.0")
        print("    Enhanced with Risk Management")
        print("=" * 50)

        # Validate configuration
        errors = config.validate_config()
        if errors and not config.PAPER_TRADING:
            for error in errors:
                self.logger.error(error)
            print("Configuration errors found. Please check .env file.")
            return

        # Step 1: Select instrument
        self.symbol, instrument_name = self.select_instrument()
        self.trade_symbol = self.symbol + 'USDT'
        self.logger.info(f"Selected instrument: {instrument_name} ({self.trade_symbol})")

        # Step 2: Select strategy
        self.strategy = self.select_strategy()
        self.logger.info(f"Selected strategy: {self.strategy.name}")

        # Step 3: Select timeframe
        self.kline = self.select_timeframe()
        self.logger.info(f"Selected timeframe: {self.kline}")

        # Setup WebSocket URL
        sym_lower = self.symbol.lower()
        self.socket_url = f"wss://stream.binance.com:9443/ws/{sym_lower}usdt@kline_{self.kline}"

        # Display summary
        self.display_config_summary(instrument_name)

        # Initialize strategy
        try:
            historical_data = self.fetch_historical_data()
            self.strategy.initialize(historical_data)
        except Exception as e:
            self.logger.error(f"Failed to initialize strategy: {e}")
            print(f"Error: {e}")
            return

        # Confirm start
        confirm = input("\nStart trading bot? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Trading bot cancelled.")
            return

        # Start trading
        self.running = True
        self.logger.info("Starting WebSocket connection...")

        try:
            self._connect_websocket()
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        finally:
            self.running = False
            stats = self.journal.get_statistics()
            if stats:
                self.logger.info("Trading Statistics:")
                for key, value in stats.items():
                    self.logger.info(f"  {key}: {value}")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()

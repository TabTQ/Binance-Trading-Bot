#!/usr/bin/env python3
"""
Zerodha F&O Trading Bot v2.0
For Nifty50 and BankNifty Futures & Options Trading
Enhanced with risk management, logging, and multiple strategies
"""

import json
import numpy as np
import talib
import pandas as pd
import logging
import csv
import time
import sys
from datetime import datetime, date, timedelta
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Kite Connect imports
try:
    from kiteconnect import KiteConnect, KiteTicker
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    print("WARNING: kiteconnect not installed. Install with: pip install kiteconnect")

import config


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Trade:
    """Represents a single trade"""
    timestamp: str
    instrument: str
    trading_symbol: str
    side: str  # BUY or SELL
    price: float
    quantity: int  # Number of shares (lots * lot_size)
    lots: int
    value: float
    strategy: str
    pnl: float = 0.0
    pnl_percent: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0


@dataclass
class Position:
    """Represents current position"""
    instrument: str
    trading_symbol: str
    instrument_token: int
    entry_price: float
    quantity: int
    lots: int
    side: str  # 'LONG' or 'SHORT'
    stop_loss: float
    take_profit: float
    entry_time: str


@dataclass
class FNOContract:
    """Represents an F&O contract"""
    instrument: str  # NIFTY or BANKNIFTY
    trading_symbol: str
    instrument_token: int
    lot_size: int
    tick_size: float
    expiry: str


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure logging with both file and console handlers"""
    logger = logging.getLogger('ZerodhaTradingBot')
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
                    'timestamp', 'instrument', 'trading_symbol', 'side', 'price',
                    'quantity', 'lots', 'value', 'strategy', 'pnl', 'pnl_percent',
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
                trade.timestamp, trade.instrument, trade.trading_symbol, trade.side,
                trade.price, trade.quantity, trade.lots, trade.value, trade.strategy,
                trade.pnl, trade.pnl_percent, trade.stop_loss, trade.take_profit
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
    """Manages risk and position sizing for F&O trading"""

    def __init__(self, journal: TradeJournal, logger: logging.Logger):
        self.journal = journal
        self.logger = logger

    def calculate_lots(self, capital: float, price: float, lot_size: int) -> int:
        """Calculate number of lots based on risk parameters"""
        # Risk-based position sizing
        risk_amount = capital * config.RISK_PER_TRADE
        max_position_value = capital * config.MAX_POSITION_SIZE

        # Value per lot
        lot_value = price * lot_size

        # Calculate max lots based on risk
        risk_based_lots = int(risk_amount / (config.STOP_LOSS_PERCENT * lot_value))

        # Calculate max lots based on position size limit
        position_based_lots = int(max_position_value / lot_value)

        # Use minimum of risk-based or position-based or max lots
        calculated_lots = min(risk_based_lots, position_based_lots, config.MAX_LOTS)

        # Ensure at least 1 lot
        lots = max(1, calculated_lots)

        self.logger.debug(f"Lots calculated: {lots} (value: {lots * lot_value:.2f} INR)")
        return lots

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
    """Simulates F&O trading without real money"""

    def __init__(self, initial_balance: float, logger: logging.Logger):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions: Dict[str, Dict] = {}
        self.logger = logger

    def get_balance(self) -> float:
        """Get current balance"""
        return self.balance

    def execute_buy(self, symbol: str, quantity: int, price: float, lots: int) -> bool:
        """Execute a paper buy order (go long)"""
        # For futures, margin is typically around 10-15% of contract value
        margin_required = quantity * price * 0.12  # ~12% margin

        if margin_required > self.balance:
            self.logger.warning(f"Insufficient margin: {margin_required:.2f} > {self.balance:.2f}")
            return False

        self.balance -= margin_required  # Block margin
        self.positions[symbol] = {
            'quantity': quantity,
            'lots': lots,
            'price': price,
            'margin': margin_required
        }

        self.logger.info(f"PAPER BUY: {lots} lots ({quantity} qty) @ {price:.2f}")
        self.logger.info(f"Margin blocked: {margin_required:.2f} INR")
        return True

    def execute_sell(self, symbol: str, quantity: int, price: float, entry_price: float) -> float:
        """Execute a paper sell order (square off long position)"""
        if symbol not in self.positions:
            self.logger.warning(f"No position found for {symbol}")
            return 0.0

        position = self.positions[symbol]
        # Calculate P&L
        pnl = (price - entry_price) * quantity

        # Release margin and add P&L
        self.balance += position['margin'] + pnl

        self.logger.info(f"PAPER SELL: {position['lots']} lots ({quantity} qty) @ {price:.2f}")
        self.logger.info(f"P&L: {pnl:.2f} INR")

        del self.positions[symbol]
        return pnl


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
    def process_candle(self, o: float, h: float, l: float, c: float, v: float) -> Optional[str]:
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

    def process_candle(self, o: float, h: float, l: float, c: float, v: float) -> Optional[str]:
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
    """Opening Range Breakout Strategy - Perfect for Nifty/BankNifty"""

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
        self.logger.info(f"Will establish range from first {config.ORB_PERIOD} candles after market open")

        # Reset state
        self.orb_high = None
        self.orb_low = None
        self.orb_range_set = False
        self.candle_count = 0

        self.logger.info("ORB Strategy initialized!")

    def process_candle(self, o: float, h: float, l: float, c: float, v: float) -> Optional[str]:
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
                self.logger.info(f"  Size: {range_size:.2f} points")

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

class ZerodhaTradingBot:
    """Main trading bot orchestrator for Zerodha F&O"""

    def __init__(self):
        self.logger = setup_logging()
        self.journal = TradeJournal(config.TRADE_JOURNAL_FILE)
        self.risk_manager = RiskManager(self.journal, self.logger)
        self.strategy: Optional[Strategy] = None
        self.position: Optional[Position] = None
        self.contract: Optional[FNOContract] = None
        self.kite = None
        self.kws = None
        self.running = False
        self.last_tick = {}

        # Paper or live trading
        if config.PAPER_TRADING:
            self.paper_trader = PaperTrader(config.INITIAL_PAPER_BALANCE, self.logger)
            self.initial_balance = config.INITIAL_PAPER_BALANCE
            self.logger.info("Running in PAPER TRADING mode")
        else:
            self.paper_trader = None
            self.logger.info("Running in LIVE TRADING mode")

            if KITE_AVAILABLE and config.KITE_API_KEY and config.KITE_ACCESS_TOKEN:
                self.kite = KiteConnect(api_key=config.KITE_API_KEY)
                self.kite.set_access_token(config.KITE_ACCESS_TOKEN)
                self.initial_balance = self._get_available_margin()
            else:
                self.initial_balance = 0.0

        self.journal.update_balance(self.initial_balance)
        self.journal.peak_balance = self.initial_balance

    def _get_available_margin(self) -> float:
        """Get available margin from Zerodha"""
        try:
            if self.kite:
                margins = self.kite.margins()
                return float(margins['equity']['available']['live_balance'])
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting margin: {e}")
            return 0.0

    def _validate_input(self, prompt: str, valid_options: List[str]) -> str:
        """Validate user input against valid options"""
        while True:
            user_input = input(prompt).strip()
            if user_input in valid_options:
                return user_input
            print(f"Invalid input. Valid options: {', '.join(valid_options)}")

    def select_instrument(self) -> FNOContract:
        """Select F&O instrument to trade"""
        print("\n" + "=" * 50)
        print("        INSTRUMENT SELECTION")
        print("=" * 50)
        print("1. NIFTY 50 Futures")
        print("2. BANKNIFTY Futures")
        print("=" * 50)

        choice = self._validate_input("Select instrument (1-2): ", ['1', '2'])

        if choice == '1':
            instrument = 'NIFTY'
            lot_size = config.NIFTY_LOT_SIZE
            tick_size = config.NIFTY_TICK_SIZE
        else:
            instrument = 'BANKNIFTY'
            lot_size = config.BANKNIFTY_LOT_SIZE
            tick_size = config.BANKNIFTY_TICK_SIZE

        # Get current month expiry (last Thursday of the month)
        expiry = self._get_current_expiry()
        trading_symbol = f"{instrument}{expiry}FUT"

        # Get instrument token (in live mode)
        instrument_token = self._get_instrument_token(trading_symbol)

        contract = FNOContract(
            instrument=instrument,
            trading_symbol=trading_symbol,
            instrument_token=instrument_token,
            lot_size=lot_size,
            tick_size=tick_size,
            expiry=expiry
        )

        self.logger.info(f"Selected: {trading_symbol} (Lot size: {lot_size})")
        return contract

    def _get_current_expiry(self) -> str:
        """Get current month expiry date string"""
        today = date.today()

        # Find last Thursday of current month
        year = today.year
        month = today.month

        # Get last day of month
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        last_day = next_month - timedelta(days=1)

        # Find last Thursday
        days_since_thursday = (last_day.weekday() - 3) % 7
        last_thursday = last_day - timedelta(days=days_since_thursday)

        # If expiry has passed, use next month
        if today > last_thursday:
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1

            if month == 12:
                next_month = date(year + 1, 1, 1)
            else:
                next_month = date(year, month + 1, 1)
            last_day = next_month - timedelta(days=1)
            days_since_thursday = (last_day.weekday() - 3) % 7
            last_thursday = last_day - timedelta(days=days_since_thursday)

        # Format: YYMMMDD (e.g., 24NOV28)
        month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                       'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
        expiry_str = f"{last_thursday.year % 100}{month_names[last_thursday.month - 1]}{last_thursday.day:02d}"

        return expiry_str

    def _get_instrument_token(self, trading_symbol: str) -> int:
        """Get instrument token for the trading symbol"""
        if self.kite and not config.PAPER_TRADING:
            try:
                instruments = self.kite.instruments("NFO")
                for inst in instruments:
                    if inst['tradingsymbol'] == trading_symbol:
                        return inst['instrument_token']
            except Exception as e:
                self.logger.error(f"Error fetching instrument token: {e}")

        # Return mock token for paper trading
        return 12345678

    def select_strategy(self) -> Strategy:
        """Interactive strategy selection"""
        print("\n" + "=" * 50)
        print("        STRATEGY SELECTION")
        print("=" * 50)
        print("1. Weis Wave Volume (WWT) Strategy")
        print("   - Crossover-based trend following")
        print("")
        print("2. Opening Range Breakout (ORB) Strategy")
        print("   - Perfect for Nifty/BankNifty intraday")
        print("=" * 50)

        choice = self._validate_input("Select strategy (1-2): ", ['1', '2'])

        if choice == '1':
            return WWTStrategy(self.logger)
        else:
            return ORBStrategy(self.logger)

    def select_timeframe(self) -> str:
        """Interactive timeframe selection"""
        valid_timeframes = ['minute', '3minute', '5minute', '15minute', '30minute', '60minute', 'day']

        print("\n" + "=" * 50)
        print("        TIMEFRAME SELECTION")
        print("=" * 50)
        print(f"Available: {', '.join(valid_timeframes)}")
        print("Recommended for intraday: 5minute or 15minute")
        print("=" * 50)

        return self._validate_input("Enter timeframe: ", valid_timeframes)

    def fetch_historical_data(self, timeframe: str) -> pd.DataFrame:
        """Fetch historical candle data for strategy initialization"""
        self.logger.info(f"Fetching historical data for {self.contract.trading_symbol}...")

        try:
            # Check if API is available
            if not self.kite or not config.KITE_ACCESS_TOKEN:
                self.logger.warning("Kite API not configured. Using mock historical data.")
                return self._generate_mock_historical_data()

            # Fetch from Kite
            from_date = datetime.now() - timedelta(days=5)
            to_date = datetime.now()

            hist_data = self.kite.historical_data(
                self.contract.instrument_token,
                from_date,
                to_date,
                timeframe
            )

            df = pd.DataFrame(hist_data)
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']

            self.logger.info(f"Fetched {len(df)} historical candles")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}")
            self.logger.warning("Using mock data for testing")
            return self._generate_mock_historical_data()

    def _generate_mock_historical_data(self) -> pd.DataFrame:
        """Generate mock historical data for testing"""
        self.logger.info("Generating mock historical data...")

        # Base price for Nifty/BankNifty
        if self.contract.instrument == 'NIFTY':
            base_price = 19500.0
        else:
            base_price = 44500.0

        data = []
        for i in range(50):
            change = np.random.randn() * 50
            open_price = base_price + change
            high_price = open_price + abs(np.random.randn() * 30)
            low_price = open_price - abs(np.random.randn() * 30)
            close_price = open_price + np.random.randn() * 20
            volume = np.random.randint(10000, 100000)

            data.append({
                'date': datetime.now() - timedelta(minutes=(50-i)*5),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })

            base_price = close_price

        df = pd.DataFrame(data)
        self.logger.info(f"Generated {len(df)} mock candles")
        return df

    def execute_order(self, side: str, price: float, signal_type: str = 'STRATEGY'):
        """Execute a buy or sell order with risk management"""
        if self.risk_manager.should_stop_trading(self.initial_balance):
            self.logger.warning("Trading halted due to risk limits!")
            return

        timestamp = datetime.now().isoformat()

        if side == 'BUY' and self.position is None:
            # Calculate lots
            balance = self.paper_trader.get_balance() if self.paper_trader else self._get_available_margin()
            lots = self.risk_manager.calculate_lots(balance, price, self.contract.lot_size)
            quantity = lots * self.contract.lot_size

            # Calculate stop loss and take profit
            stop_loss = self.risk_manager.calculate_stop_loss(price, 'BUY')
            take_profit = self.risk_manager.calculate_take_profit(price, 'BUY')

            # Execute order
            if self.paper_trader:
                success = self.paper_trader.execute_buy(
                    self.contract.trading_symbol, quantity, price, lots
                )
            else:
                try:
                    # Live order
                    order_id = self.kite.place_order(
                        variety=self.kite.VARIETY_REGULAR,
                        exchange=self.kite.EXCHANGE_NFO,
                        tradingsymbol=self.contract.trading_symbol,
                        transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                        quantity=quantity,
                        product=self.kite.PRODUCT_MIS,  # Intraday
                        order_type=self.kite.ORDER_TYPE_MARKET
                    )
                    success = True
                    self.logger.info(f"Order placed: {order_id}")
                except Exception as e:
                    self.logger.error(f"Order execution failed: {e}")
                    success = False

            if success:
                self.position = Position(
                    instrument=self.contract.instrument,
                    trading_symbol=self.contract.trading_symbol,
                    instrument_token=self.contract.instrument_token,
                    entry_price=price,
                    quantity=quantity,
                    lots=lots,
                    side='LONG',
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    entry_time=timestamp
                )

                trade = Trade(
                    timestamp=timestamp,
                    instrument=self.contract.instrument,
                    trading_symbol=self.contract.trading_symbol,
                    side='BUY',
                    price=price,
                    quantity=quantity,
                    lots=lots,
                    value=quantity * price,
                    strategy=self.strategy.name,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                self.journal.record_trade(trade)

                self.logger.info(f"{'='*50}")
                self.logger.info(f"  BUY ORDER EXECUTED - {self.contract.instrument}")
                self.logger.info(f"  Price: {price:.2f}")
                self.logger.info(f"  Lots: {lots} (Qty: {quantity})")
                self.logger.info(f"  Value: {quantity * price:.2f} INR")
                self.logger.info(f"  Stop Loss: {stop_loss:.2f}")
                self.logger.info(f"  Take Profit: {take_profit:.2f}")
                self.logger.info(f"{'='*50}")

        elif side == 'SELL' and self.position is not None:
            quantity = self.position.quantity
            entry_price = self.position.entry_price
            lots = self.position.lots

            # Execute order
            if self.paper_trader:
                pnl = self.paper_trader.execute_sell(
                    self.contract.trading_symbol, quantity, price, entry_price
                )
                success = True
            else:
                try:
                    # Live order
                    order_id = self.kite.place_order(
                        variety=self.kite.VARIETY_REGULAR,
                        exchange=self.kite.EXCHANGE_NFO,
                        tradingsymbol=self.contract.trading_symbol,
                        transaction_type=self.kite.TRANSACTION_TYPE_SELL,
                        quantity=quantity,
                        product=self.kite.PRODUCT_MIS,
                        order_type=self.kite.ORDER_TYPE_MARKET
                    )
                    success = True
                    self.logger.info(f"Order placed: {order_id}")
                    pnl = (price - entry_price) * quantity
                except Exception as e:
                    self.logger.error(f"Order execution failed: {e}")
                    success = False
                    pnl = 0.0

            if success:
                pnl_percent = (price - entry_price) / entry_price

                trade = Trade(
                    timestamp=timestamp,
                    instrument=self.contract.instrument,
                    trading_symbol=self.contract.trading_symbol,
                    side='SELL',
                    price=price,
                    quantity=quantity,
                    lots=lots,
                    value=quantity * price,
                    strategy=self.strategy.name,
                    pnl=pnl,
                    pnl_percent=pnl_percent
                )
                self.journal.record_trade(trade)
                self.journal.update_daily_pnl(pnl)

                # Update balance
                new_balance = self.paper_trader.get_balance() if self.paper_trader else self._get_available_margin()
                self.journal.update_balance(new_balance)

                self.logger.info(f"{'='*50}")
                self.logger.info(f"  SELL ORDER EXECUTED - {self.contract.instrument}")
                self.logger.info(f"  Price: {price:.2f}")
                self.logger.info(f"  Lots: {lots} (Qty: {quantity})")
                self.logger.info(f"  P&L: {pnl:.2f} INR ({pnl_percent:.2%})")
                self.logger.info(f"  Balance: {new_balance:.2f} INR")
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

    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now()
        market_open = now.replace(
            hour=config.MARKET_OPEN_HOUR,
            minute=config.MARKET_OPEN_MINUTE,
            second=0
        )
        market_close = now.replace(
            hour=config.MARKET_CLOSE_HOUR,
            minute=config.MARKET_CLOSE_MINUTE,
            second=0
        )

        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday or Sunday
            return False

        return market_open <= now <= market_close

    def on_ticks(self, ws, ticks):
        """Handle incoming tick data from Kite WebSocket"""
        for tick in ticks:
            if tick['instrument_token'] == self.contract.instrument_token:
                self.last_tick = tick

                ltp = tick['last_price']
                self.logger.debug(f"Tick: {ltp:.2f}")

                # Check stop loss / take profit
                if self.position:
                    self.check_stop_loss_take_profit(ltp)

    def on_connect(self, ws, response):
        """Handle WebSocket connection"""
        self.logger.info("WebSocket connected")
        # Subscribe to instrument
        ws.subscribe([self.contract.instrument_token])
        ws.set_mode(ws.MODE_FULL, [self.contract.instrument_token])

    def on_close(self, ws, code, reason):
        """Handle WebSocket disconnection"""
        self.logger.warning(f"WebSocket closed: {code} - {reason}")

    def on_error(self, ws, code, reason):
        """Handle WebSocket errors"""
        self.logger.error(f"WebSocket error: {code} - {reason}")

    def display_config_summary(self):
        """Display configuration summary"""
        print(f"\n{'='*50}")
        print(f"  CONFIGURATION SUMMARY")
        print(f"{'='*50}")
        print(f"  Mode: {'PAPER' if config.PAPER_TRADING else 'LIVE'} TRADING")
        print(f"  Instrument: {self.contract.instrument}")
        print(f"  Contract: {self.contract.trading_symbol}")
        print(f"  Lot Size: {self.contract.lot_size}")
        print(f"  Strategy: {self.strategy.name}")
        print(f"  Initial Capital: {self.initial_balance:.2f} INR")
        print(f"{'='*50}")
        print(f"  RISK MANAGEMENT")
        print(f"{'='*50}")
        print(f"  Risk per Trade: {config.RISK_PER_TRADE:.1%}")
        print(f"  Max Position Size: {config.MAX_POSITION_SIZE:.1%}")
        print(f"  Stop Loss: {config.STOP_LOSS_PERCENT:.1%}")
        print(f"  Take Profit: {config.TAKE_PROFIT_PERCENT:.1%}")
        print(f"  Max Daily Loss: {config.MAX_DAILY_LOSS:.1%}")
        print(f"  Max Drawdown: {config.MAX_DRAWDOWN:.1%}")
        print(f"  Max Lots: {config.MAX_LOTS}")
        print(f"{'='*50}")
        print(f"  MARKET HOURS (IST)")
        print(f"{'='*50}")
        print(f"  Open: {config.MARKET_OPEN_HOUR:02d}:{config.MARKET_OPEN_MINUTE:02d}")
        print(f"  Close: {config.MARKET_CLOSE_HOUR:02d}:{config.MARKET_CLOSE_MINUTE:02d}")
        print(f"{'='*50}")

    def run_paper_simulation(self, timeframe: str):
        """Run paper trading simulation with historical data"""
        self.logger.info("Starting paper trading simulation...")

        # Generate simulated candles
        candle_count = 0
        base_price = 19500.0 if self.contract.instrument == 'NIFTY' else 44500.0

        print("\nSimulating market data... Press Ctrl+C to stop\n")

        try:
            while self.running:
                # Generate a candle
                change = np.random.randn() * 30
                o = base_price + change
                h = o + abs(np.random.randn() * 20)
                l = o - abs(np.random.randn() * 20)
                c = o + np.random.randn() * 15
                v = np.random.randint(10000, 50000)

                candle_count += 1
                self.logger.info(f"Candle #{candle_count} closed @ {c:.2f}")

                # Process strategy
                signal = self.strategy.process_candle(o, h, l, c, v)

                if signal == 'BUY' and self.position is None:
                    self.execute_order('BUY', c)
                elif signal == 'SELL' and self.position is not None:
                    self.execute_order('SELL', c)

                # Check stop loss / take profit
                if self.position:
                    self.check_stop_loss_take_profit(c)

                base_price = c

                # Wait between candles (simulated)
                time.sleep(2)

        except KeyboardInterrupt:
            self.logger.info("Simulation stopped by user")

    def run(self):
        """Main bot execution"""
        print("\n" + "=" * 50)
        print("    ZERODHA F&O TRADING BOT v2.0")
        print("    For Nifty50 & BankNifty")
        print("=" * 50)

        # Validate configuration
        errors = config.validate_config()
        if errors:
            if not config.PAPER_TRADING:
                for error in errors:
                    self.logger.error(error)
                print("Configuration errors found. Please check .env file.")
                return
            else:
                self.logger.warning("API credentials not configured. Running in simulation mode.")
                print("\nWARNING: Kite API credentials not configured.")
                print("Bot will run in paper trading simulation mode.\n")

        # Step 1: Select instrument
        self.contract = self.select_instrument()
        self.logger.info(f"Selected contract: {self.contract.trading_symbol}")

        # Step 2: Select strategy
        self.strategy = self.select_strategy()
        self.logger.info(f"Selected strategy: {self.strategy.name}")

        # Step 3: Select timeframe
        timeframe = self.select_timeframe()
        self.logger.info(f"Selected timeframe: {timeframe}")

        # Display summary
        self.display_config_summary()

        # Initialize strategy
        try:
            historical_data = self.fetch_historical_data(timeframe)
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
        self.logger.info("Starting trading bot...")

        try:
            if config.PAPER_TRADING or not KITE_AVAILABLE:
                # Paper trading simulation
                self.run_paper_simulation(timeframe)
            else:
                # Live WebSocket connection
                self.kws = KiteTicker(config.KITE_API_KEY, config.KITE_ACCESS_TOKEN)
                self.kws.on_ticks = self.on_ticks
                self.kws.on_connect = self.on_connect
                self.kws.on_close = self.on_close
                self.kws.on_error = self.on_error
                self.kws.connect()

        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        finally:
            self.running = False
            stats = self.journal.get_statistics()
            if stats:
                self.logger.info("Trading Statistics:")
                for key, value in stats.items():
                    if isinstance(value, float):
                        self.logger.info(f"  {key}: {value:.4f}")
                    else:
                        self.logger.info(f"  {key}: {value}")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    bot = ZerodhaTradingBot()
    bot.run()

import csv
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from src.logger_factory import get_logger

# All order creation and exit logic is handled in this strategy class.
# signal_manager.py and exit_manager.py are deprecated.

@dataclass
class Trade:
    symbol: str
    name: str
    side: str
    entry_time: datetime
    entry_price: float
    entry_open: float
    entry_close: float
    entry_vwap: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_type: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None

class IncrementalVWAP:
    def __init__(self):
        self.cum_tp_vol = 0.0
        self.cum_vol = 0.0
        self.vwap = None

    def update(self, high: float, low: float, close: float, volume: float) -> float:
        typical_price = (high + low + close) / 3
        tp_vol = typical_price * volume

        self.cum_tp_vol += tp_vol
        self.cum_vol += volume

        if self.cum_vol > 0:
            self.vwap = round(self.cum_tp_vol / self.cum_vol, 2)
        return self.vwap

    def update_from_quote(self, ltp: float, volume: float) -> float:
        tp_vol = ltp * volume
        self.cum_tp_vol += tp_vol
        self.cum_vol += volume

        if self.cum_vol > 0:
            self.vwap = round(self.cum_tp_vol / self.cum_vol, 2)
        return self.vwap

class VwapStrategy:
    """VWAP cross strategy with integrated position and risk management."""
    
    def __init__(self, 
                 exit_steps: List[Tuple[float, float]] = None, 
                 exit_max_pct: float = 0.01,
                 market_close_time: str = '13:39',
                 output_file: str = 'trades.csv'):
        """
        Initialize the VWAP strategy.
        
        Args:
            exit_steps: List of tuples (profit_pct, position_portion) for scaling out
            exit_max_pct: Maximum retracement before trailing stop triggers
            market_close_time: Time to close all positions (format: 'HH:MM')
            output_file: CSV file to save trade records
        """
        self._logger = get_logger("VWAPStrategy")
        self.vwaps = defaultdict(IncrementalVWAP)
        self.exit_steps = exit_steps or [
            (0.02, 0.3), (0.04, 0.3), (0.05, 0.3), (0.07, 0.3),
            (0.10, 0.3), (0.15, 0.3), (0.20, 0.3), (0.30, 0.3)
        ]
        self.market_close = datetime.strptime(market_close_time, "%H:%M").time()
        self.exit_max_pct = exit_max_pct
        self.output_file = output_file
        
        # Active trades
        self.positions: Dict[str, dict] = {}
        self.completed_trades: List[Trade] = []
        
        # Initialize output file
        self._init_output_file()
    
    def _init_output_file(self):
        """Initialize the output CSV file with headers."""
        with open(self.output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'symbol', 'name', 'side', 'entry_time', 'entry_price',
                'entry_open', 'entry_close', 'entry_vwap',
                'exit_time', 'exit_price', 'exit_type',
                'pnl', 'pnl_pct'
            ])
    
    def _record_trade(self, trade: Trade):
        """Save a completed trade to the output file."""
        self.completed_trades.append(trade)
        with open(self.output_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=vars(trade).keys())
            writer.writerow(asdict(trade))
    
    def on_candle(self, symbol: str, candle: dict):
        """Process a new candle."""
        vwap = self.vwaps[symbol].update(
            candle['high'], candle['low'], candle['close'], candle['volume']
        )
        
        now_time = candle['timestamp'].time()
        close_price = candle['close']
        open_price = candle['open']
        
        # Check for entry signals if no position exists
        if symbol not in self.positions:
            self._check_entry(symbol, candle, open_price, close_price, vwap)
        else:
            # Manage existing position
            self._manage_position(symbol, close_price, vwap, now_time, candle['timestamp'])
    
    def on_quote(self, symbol: str, ltp: float, volume: float, timestamp: datetime):
        """Process a new quote (tick data)."""
        vwap = self.vwaps[symbol].update_from_quote(ltp, volume)
        
        # Check for risk exits on tick data
        if symbol in self.positions:
            self._check_risk_exit(symbol, ltp, vwap, timestamp)
    
    def _check_entry(self, symbol: str, candle: dict, open_price: float, 
                    close_price: float, vwap: float):
        """Check for entry signals."""
        if open_price < vwap and close_price > vwap:
            self._enter_position(symbol, 'BUY', close_price, candle, vwap)
        elif open_price > vwap and close_price < vwap:
            self._enter_position(symbol, 'SELL', close_price, candle, vwap)
    
    def _enter_position(self, symbol: str, side: str, price: float, 
                       candle: dict, vwap: float):
        """Enter a new position."""
        self.positions[symbol] = {
            'side': side,
            'entry_price': price,
            'entry_time': candle['timestamp'],
            'steps': self.exit_steps.copy(),
            'filled_steps': set(),
            'max_profit_price': price,
            'min_profit_price': price,
            'position_size': 1.0,
            'name': candle.get('name', symbol),
            'entry_open': candle['open'],
            'entry_close': candle['close'],
            'entry_vwap': vwap
        }
        self._logger.info(f"ENTER {side} {symbol} @ {price}")
    
    def _manage_position(self, symbol: str, price: float, vwap: float, 
                        current_time: datetime, timestamp: datetime):
        """Manage an existing position, checking for exits."""
        position = self.positions[symbol]
        entry = position['entry_price']
        side = position['side']
        
        # Update price extremes
        if side == 'BUY':
            position['max_profit_price'] = max(position['max_profit_price'], price)
        else:
            position['min_profit_price'] = min(position['min_profit_price'], price)
        
        # Check for step exits
        self._check_step_exits(symbol, price, position)
        
        # Check for trailing stop
        if self._check_trailing_stop(symbol, price, position, timestamp):
            return
        
        # Check for market close
        if current_time >= self.market_close:
            self._exit_position(symbol, price, timestamp, 'TIME')
    
    def _check_step_exits(self, symbol: str, price: float, position: dict):
        """Check for partial profit taking at predefined levels."""
        entry = position['entry_price']
        side = position['side']
        
        profit_ratio = (price - entry) / entry if side == 'BUY' else (entry - price) / entry
        
        for pct, portion in position['steps']:
            if pct in position['filled_steps']:
                continue
                
            if profit_ratio >= pct:
                position['filled_steps'].add(pct)
                position['position_size'] -= portion
                self._logger.info(
                    f"STEP EXIT {symbol} @ {price} "
                    f"({portion*100:.0f}% @ {pct*100:.0f}%)"
                )
    
    def _check_trailing_stop(self, symbol: str, price: float, 
                           position: dict, timestamp: datetime) -> bool:
        """Check if trailing stop is triggered."""
        side = position['side']
        
        if side == 'BUY':
            peak = position['max_profit_price']
            retrace = (peak - price) / peak
        else:
            trough = position['min_profit_price']
            retrace = (price - trough) / trough
        
        if retrace >= self.exit_max_pct:
            self._exit_position(symbol, price, timestamp, 'TRAIL')
            return True
        return False
    
    def _check_risk_exit(self, symbol: str, price: float, 
                        vwap: float, timestamp: datetime, safety_pct: float = 0.03):
        """Check for risk-based exits on tick data."""
        position = self.positions.get(symbol)
        if not position:
            return
            
        side = position['side']
        entry = position['entry_price']
        
        # Safety stop loss
        if (side == 'BUY' and price <= entry * (1 - safety_pct)) or \
           (side == 'SELL' and price >= entry * (1 + safety_pct)):
            self._exit_position(symbol, price, timestamp, 'SAFETY')
            return
            
        # VWAP-based risk exit
        if (side == 'BUY' and price < vwap) or (side == 'SELL' and price > vwap):
            self._exit_position(symbol, price, timestamp, 'RISK')
    
    def _exit_position(self, symbol: str, price: float, 
                      timestamp: datetime, exit_type: str):
        """Exit a position and record the trade."""
        if symbol not in self.positions:
            return
            
        position = self.positions.pop(symbol)
        side = position['side']
        entry_price = position['entry_price']
        
        # Calculate P&L
        if side == 'BUY':
            pnl = price - entry_price
        else:
            pnl = entry_price - price
            
        pnl_pct = (pnl / entry_price) * 100
        
        # Create trade record
        trade = Trade(
            symbol=symbol,
            name=position['name'],
            side=side,
            entry_time=position['entry_time'],
            entry_price=entry_price,
            entry_open=position['entry_open'],
            entry_close=position['entry_close'],
            entry_vwap=position['entry_vwap'],
            exit_time=timestamp,
            exit_price=price,
            exit_type=exit_type,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2)
        )
        
        self._record_trade(trade)
        self._logger.info(
            f"EXIT {side} {symbol} @ {price} | "
            f"P&L: {pnl:.2f} ({pnl_pct:.2f}%) | "
            f"Reason: {exit_type}"
        )
    
    def get_active_positions(self) -> Dict[str, dict]:
        """Get all active positions."""
        return self.positions
    
    def get_completed_trades(self) -> List[Trade]:
        """Get all completed trades."""
        return self.completed_trades

from datetime import datetime
from typing import Dict
from src.logger_factory import get_logger
import csv
from dataclasses import asdict


class ExitManager:
    """ Takes input of OrderObject and provides exit signals on it"""
    def __init__(self, 
                 exit_steps=None,
                 reterival_exit: float = 0.05,
                 default_quantity: int = 75,
                 market_close=None):
        
        self.exit_steps = exit_steps
        self.reterival_exit = reterival_exit
        self.default_quantity = default_quantity
        self.market_close = market_close
        self._handlers = []

        self._logger = get_logger("ExitManager")


    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)
            
    def manage_position(self, symbol: str, price: float, vwap: float,
                        current_time: datetime, timestamp: datetime, 
                        positions: Dict[str, dict]):
        """Manage an existing position, checking for exits."""
        if symbol not in positions:
            return

        position = positions[symbol]
        side = position['side']

        # Update price extremes for trailing logic
        if side == 'BUY':
            position['max_profit_price'] = max(position['max_profit_price'], price)
        else:
            position['min_profit_price'] = min(position['min_profit_price'], price)

        # Check exit conditions
        self._check_step_exits(symbol, price, position, timestamp)
        if self._check_trailing_stop(symbol, price, position, timestamp):
            return

        if current_time >= self.market_close:
            self._exit_position(symbol, price, timestamp, 'TIME', position, position['remaining_qty'])

        if position['remaining_qty'] <= 0:
            positions.pop(symbol, None)

    def check_risk_exit(self, symbol: str, price: float, vwap: float,
                        timestamp: datetime, positions: Dict[str, dict],
                        safety_pct: float = 0.03):
        """Check for risk-based exits (hard stop loss + VWAP cross)."""
        position = positions.get(symbol)
        if not position or position['remaining_qty'] <= 0:
            return

        side = position['side']
        entry = position['entry_price']

        # Safety Exit
        if (side == 'BUY' and price <= entry * (1 - safety_pct)) or \
           (side == 'SELL' and price >= entry * (1 + safety_pct)):
            self._exit_position(symbol, price, timestamp, 'SAFETY', position, position['remaining_qty'])
            return

        # VWAP Risk Exit
        if (side == 'BUY' and price < vwap) or (side == 'SELL' and price > vwap):
            self._exit_position(symbol, price, timestamp, 'RISK', position, position['remaining_qty'])

    def _check_step_exits(self, symbol: str, price: float, position: dict, timestamp: datetime):
        """Partial profit taking at predefined levels."""
        entry = position['entry_price']
        side = position['side']
        total_qty = position['quantity']

        profit_ratio = (price - entry) / entry if side == 'BUY' else (entry - price) / entry

        for pct, portion in position['steps']:
            if pct in position['filled_steps']:
                continue

            if profit_ratio >= pct and position['remaining_qty'] > 0:
                qty_to_exit = int(total_qty * portion)
                qty_to_exit = max(self.default_quantity, (qty_to_exit // self.default_quantity) * self.default_quantity)
                qty_to_exit = min(qty_to_exit, position['remaining_qty'])
                if qty_to_exit <= 0:
                    continue

                position['filled_steps'].add(pct)
                position['remaining_qty'] -= qty_to_exit
                position['position_size'] = position['remaining_qty'] / total_qty
                self._exit_position(symbol, price, timestamp, f'STEP_{int(pct*100)}', position, qty_to_exit)

    def _check_trailing_stop(self, symbol: str, price: float, position: dict, timestamp: datetime) -> bool:
        """Trailing stop based on retracement percentage."""
        side = position['side']
        if position['remaining_qty'] <= 0:
            return False

        retrace = ((position['max_profit_price'] - price) / position['max_profit_price']) if side == 'BUY' \
            else ((price - position['min_profit_price']) / position['min_profit_price'])

        if retrace >= self.reterival_exit:
            self._exit_position(symbol, price, timestamp, 'TRAIL', position, position['remaining_qty'])
            return True
        return False

    def _exit_position(self, symbol: str, price: float, timestamp: datetime,
                      exit_type: str, position: dict, qty: int):
        side = position['side']
        entry_price = position['entry_price']

        pnl = (price - entry_price) * qty if side == 'BUY' else (entry_price - price) * qty
        pnl_pct = (pnl / (entry_price * qty)) * 100 if qty > 0 else 0

        self._logger.info(f"EXIT {side} {symbol} @ {price} | P&L: {pnl:.2f} ({pnl_pct:.2f}%) | Qty: {qty} | Reason: {exit_type}")
        for cb in self._handlers:
            # Pass all relevant info for order exit
            cb(
                signal="EXIT",
                instrument=symbol,
                exit_reason=exit_type,
                exit_price=price,
                timestamp=timestamp
            )


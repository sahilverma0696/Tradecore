from datetime import datetime
from typing import Dict, Optional
from src.logger_factory import get_logger
from src.core.event_bus import Publisher, ExitSignal


class ExitManager(Publisher):
    """Takes OrderObject and provides exit signals"""
    def __init__(self, 
                 exit_steps=None,
                 reterival_exit: float = 0.05,
                 default_quantity: int = 75,
                 market_close=None):
        super().__init__()
        self.exit_steps = exit_steps or []
        self.reterival_exit = reterival_exit
        self.default_quantity = default_quantity
        self.market_close = market_close
        self._logger = get_logger("ExitManager")

    def check_exit(self, order, ltp: float, timestamp: datetime) -> Optional[dict]:
        """Check if order should exit and return exit signal"""
        
        # Check step exits
        step_exit = self._check_step_exits(order, ltp)
        if step_exit:
            exit_event = ExitSignal(
                timestamp=timestamp,
                source=self.__class__.__name__,
                symbol=order.get_name(),
                exit_price=ltp,
                exit_reason=step_exit,
                quantity=self.default_quantity
            )
            self.publish_event(exit_event)
            return {
                'signal': 'EXIT',
                'symbol': order.get_name(),
                'exit_price': ltp,
                'exit_reason': step_exit,
                'quantity': self.default_quantity,
                'timestamp': timestamp
            }

        # Check trailing stop
        trail_exit = self._check_trailing_stop(order, ltp)
        if trail_exit:
            exit_event = ExitSignal(
                timestamp=timestamp,
                source=self.__class__.__name__,
                symbol=order.get_name(),
                exit_price=ltp,
                exit_reason='TRAIL',
                quantity=order.total_quantity
            )
            self.publish_event(exit_event)
            return {
                'signal': 'EXIT',
                'symbol': order.get_name(),
                'exit_price': ltp,
                'exit_reason': 'TRAIL',
                'quantity': order.total_quantity,
                'timestamp': timestamp
            }

        # Check time-based exit
        if self.market_close and timestamp.time() >= self.market_close:
            exit_event = ExitSignal(
                timestamp=timestamp,
                source=self.__class__.__name__,
                symbol=order.get_name(),
                exit_price=ltp,
                exit_reason='TIME',
                quantity=order.total_quantity
            )
            self.publish_event(exit_event)
            return {
                'signal': 'EXIT',
                'symbol': order.get_name(),
                'exit_price': ltp,
                'exit_reason': 'TIME',
                'quantity': order.total_quantity,
                'timestamp': timestamp
            }

        return None

    def _check_step_exits(self, order, ltp: float) -> Optional[str]:
        """Check for step exits"""
        entry_price = order.get_entry_price()
        if not entry_price:
            return None

        side = order.get_side()
        profit_ratio = (ltp - entry_price) / entry_price if side == 'BUY' else (entry_price - ltp) / entry_price

        current_step = order.get_current_step()
        if profit_ratio >= current_step and current_step not in order.filled_steps:
            order.filled_steps.add(current_step)
            return f'STEP_{int(current_step*100)}'

        return None

    ## TODO: check which of the two qualify
    def _check_trailing_stop(self, order, ltp: float) -> bool:
        """Check trailing stop based on retracement"""
        side = order.get_side()
        
        if side == 'BUY':
            retrace = ((order.get_max_price() - ltp) / order.get_max_price()) if order.get_max_price() > 0 else 0
        else:
            retrace = ((ltp - order.get_min_price()) / order.get_min_price()) if order.get_min_price() > 0 else 0

        return retrace >= self.reterival_exit

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


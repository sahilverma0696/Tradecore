from datetime import datetime, time
from typing import Dict, Optional
from src.logger_factory import get_logger
from src.core.event_bus import Publisher, ExitSignal
from src.core.event_bus import QuoteEvent


class ExitManager(Publisher):
    """Takes OrderObject and provides exit signals"""
    def __init__(self, 
                 exit_steps=None,
                 reterival_exit: float = 0.05,
                 default_quantity: int = 75,
                 market_close: str = None):
        super().__init__()
        self.exit_steps = exit_steps or []
        self.reterival_exit = reterival_exit
        self.default_quantity = default_quantity
        
        # Convert market_close string to time object
        self.market_close = self._parse_market_close_time(market_close)
        
        self._logger = get_logger("ExitManager")
        self._logger.info(f"ExitManager initialized with {len(self.exit_steps)} exit steps")
        self._logger.info(f"Market close time: {self.market_close}")

    def _parse_market_close_time(self, market_close_str: str) -> Optional[time]:
        """Convert market close time string to datetime.time object."""
        if not market_close_str:
            return None
        
        try:
            # Parse time string in format "HH:MM" 
            hour, minute = map(int, market_close_str.split(':'))
            return time(hour, minute)
        except (ValueError, AttributeError) as e:
            self._logger.error(f"Invalid market_close format '{market_close_str}': {e}")
            return None

    ## TODO: better to pass the event
    def check_exit(self, order, event: QuoteEvent) -> Optional[dict]:
        """Check if order should exit and return exit signal"""
        
        # Check step exits
        step_exit = self._check_step_exits(order, event.ltp)
        if step_exit:
            exit_event = ExitSignal(
                timestamp=event.timestamp,
                source=self.__class__.__name__,
                symbol=order.get_name(),
                exit_price=event.ltp,
                exit_reason=step_exit,
                quantity=self.default_quantity
            )
            self.publish_event(exit_event)
            return {
                'signal': 'EXIT',
                'symbol': order.get_name(),
                'exit_price': event.ltp,
                'exit_reason': step_exit,
                'quantity': self.default_quantity,
                'timestamp': event.timestamp
            }

        # Check trailing stop
        trail_exit = self._check_trailing_stop(order, event.ltp)
        if trail_exit:
            exit_event = ExitSignal(
                timestamp=event.timestamp,
                source=self.__class__.__name__,
                symbol=order.get_name(),
                price=event.ltp,
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
                price=ltp,
                exit_reason='TIME',
                quantity=order.total_quantity
            )
            self.publish_event(exit_event)
            return {
                'signal': 'EXIT',
                'symbol': order.get_name(),
                'price': ltp,
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

    ## keeping it here because yet to finalize exit manager
    # def _check_trailing_stop(self, symbol: str, price: float, position: dict, timestamp: datetime) -> bool:
    #     """Trailing stop based on retracement percentage."""
    #     side = position['side']
    #     if position['remaining_qty'] <= 0:
    #         return False

    #     retrace = ((position['max_profit_price'] - price) / position['max_profit_price']) if side == 'BUY' \
    #         else ((price - position['min_profit_price']) / position['min_profit_price'])

    #     if retrace >= self.reterival_exit:
    #         self._exit_position(symbol, price, timestamp, 'TRAIL', position, position['remaining_qty'])
    #         return True
    #     return False

    def _exit_position(self, symbol: str, price: float, timestamp: datetime,
                      exit_type: str, position: dict, qty: int):
        side = position['side']
        entry_price = position['entry_price']

        pnl = (price - entry_price) * qty if side == 'BUY' else (entry_price - price) * qty
        pnl_pct = (pnl / (entry_price * qty)) * 100 if qty > 0 else 0
        

        self._logger.info(f"EXIT {side} {symbol} @ {price} | P&L: {pnl:.2f} ({pnl_pct:.2f}%) | Qty: {qty} | Reason: {exit_type}")


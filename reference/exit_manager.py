import time
from datetime import datetime
from logger_factory import get_logger

class ExitManager:
    def __init__(self, order_manager):
        self.order_manager = order_manager
        self.logger = get_logger(self.__class__.__name__)
        self.logger.info("INIT exit manager")
        self.exit_handler = None  # Optional external callback on exit signal

    def register_exit_handler(self, handler_func):
        """
        Register an external function to be called on exit signal.
        This function should accept (order_obj, reason) as args.
        """
        if callable(handler_func):
            self.exit_handler = handler_func

    def handle_ltp(self, quote):
        """
        Main LTP quote handler to trigger exit logic.
        """
        name = quote['name']
        
        ltp = quote['ltp']

        order = self.order_manager.get_order(name)
        if not order:
            return

        order.set_ltp(ltp)
        candle = order.get_current_candle()
        side = order.get_side()
        

        # Skip if no candle yet
        if not candle or 'vwap' not in candle or candle['vwap'] is None:
            return

        # --- RISK EXIT ---
        vwap = candle['vwap']
        if (side == 'BUY' and ltp < vwap) or (side == 'SELL' and ltp > vwap):
            self.logger.info(f"[RISK EXIT] {name} - LTP {ltp} vs VWAP {vwap}")
            print(f"[RISK EXIT] {name} - LTP {ltp} vs VWAP {vwap}")
            self._trigger_exit(order, reason="RISK")
            return

        # --- RETRACE EXIT ---
        step = order.get_current_step()
        trail_pct = order.get_current_trail()

        if side == 'BUY':
            peak = order.get_max_price()
            if ltp > peak:
                order.set_max_price(ltp)  # new peak
            retrace = (peak - ltp) / peak if peak else 0
            step_price = order.get_entry_price() * (1 + step)
            trail_price = peak * (1 - trail_pct)
            exit_level = max(step_price, trail_price)

            if ltp <= exit_level:
                self.logger.info(f"[RETRACE EXIT] {name} BUY - LTP {ltp}, Peak {peak}, Exit @ {exit_level}")
                self._trigger_exit(order, reason="RETRACE")
        
        elif side == 'SELL':
            trough = order.get_min_price()
            if ltp < trough:
                order.set_min_price(ltp)  # new trough
            retrace = (ltp - trough) / trough if trough else 0
            step_price = order.get_entry_price() * (1 - step)
            trail_price = trough * (1 + trail_pct)
            exit_level = min(step_price, trail_price)

            if ltp >= exit_level:
                self.logger.info(f"[RETRACE EXIT] {name} SELL - LTP {ltp}, Trough {trough}, Exit @ {exit_level}")
                self._trigger_exit(order, reason="RETRACE")

    def _trigger_exit(self, order, reason):
        """
        Internal method to handle exit logic.
        
        Args:
            order: The OrderObject to exit
            reason (str): Reason for exit (e.g., 'RISK', 'TRAILING_STOP', 'TARGET_HIT')
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.logger.info(f"Exit signal for {order.name} at {timestamp}: {reason}")
        
        # Ensure we have the latest LTP before exit
        current_ltp = order.get_ltp()
        
        # For RETRACE exits, use the calculated exit level instead of LTP
        if reason == 'RETRACE':
            if order.get_side() == 'BUY':
                exit_price = order.get_max_price() * (1 - order.get_current_trail())
            else:  # SELL
                exit_price = order.get_min_price() * (1 + order.get_current_trail())
            self.logger.info(f"Using calculated exit price for {reason} exit: {exit_price}")
        else:
            exit_price = current_ltp
        
        # Log exit details
        exit_details = {
            'exit_price': exit_price,
            'exit_time': timestamp,
            'exit_reason': reason,
            'entry_price': order.get_entry_price(),
            'entry_time': order.get_entry_time(),
            'duration': (datetime.now() - order.get_entry_time()).total_seconds() if order.get_entry_time() else 0,
            'pnl_pct': ((exit_price - order.get_entry_price()) / order.get_entry_price() * 100) 
                       if order.get_entry_price() and order.get_entry_price() != 0 else 0
        }
        
        # Call external handler if registered
        if self.exit_handler:
            self.exit_handler(order, reason)
            
        # Remove the order from order manager with exit reason and price
        self.order_manager.remove_order(
            name=order.name, 
            timestamp=timestamp, 
            exit_reason=reason,
            exit_price=exit_price
        )
        
        return exit_details

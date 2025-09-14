from datetime import datetime
from typing import Optional, Dict, Any
from src.core.order_object import OrderObject
from src.logger_factory import get_logger


class ExitManager:
    """
    Exit management library for order objects.
    Works on trailing stops, retrieval exits, and market close exits.
    
    has just one function check_exit:
        - checks on profit exit
            - step exit
        - checks on trigger exit
            - retrieval trigger is triggered
            - zero stop is triggered
            - hard stop is triggered
        - checks on market close exit
    """
    
    def __init__(self, name: str = "ExitManager"):
        self.logger = get_logger(name)
        self.dust_value = 0.01
        
    # step based exits
    def _check_step_exit(self, order: OrderObject) -> Optional[Dict[str, Any]]:
        """
        Check if step change triggers partial profit exit.

        Args:
            order: OrderObject containing order state information

        """

        current_step_idx = order.get_current_step_idx()
        
        ltp = order.get_ltp()
        side = order.get_side()
        
        entry_price = order.get_entry_price()
        
        #this is a decimal value, like 0.02 for 2%
        step = order.get_current_step()
        
        #this is the value of this step trigger, based on side
        step_exit_value = entry_price *(step*100) if side == "BUY" else entry_price *(1 - step*100)
        
        if( (side == "BUY" and ltp >= step_exit_value) or
            (side == "SELL" and ltp <= step_exit_value) ):
            # Step exit triggered
            # values will be updated in order object
            current_quantity = order.get_current_quantity()
            order.total_quantity -= current_quantity
            return self._create_exit_info(order, f'STEP_EXIT_{current_step_idx}', current_quantity, 'PARTIAL')

        return None

    def _check_profit_exit(self, order: OrderObject) -> Optional[Dict[str, Any]]:
        """
        Check if profit exit is triggered.
        keeping this as a function in case future ways are added
        """
        # checks if step exit is triggered
        return self._check_step_exit(order)


    # trigger based exits
    def _check_retrieval_trigger_exit(self, order: OrderObject) -> Optional[Dict[str, Any]]:
        '''
        Check if retrieval trigger exit is triggered.
        '''
        trigger = order.get_current_trigger() *100 # convert to percentage
        side = order.get_side()
        ltp = order.get_ltp()
        max_price = order.get_max_price()
        min_price = order.get_min_price()
        difference = (max_price - ltp) if side == "BUY" else (ltp - min_price)
        difference_percentage = (difference / max_price)*100 if side == "BUY" else (difference / min_price)*100
        
        if( difference_percentage >= trigger and trigger > 0):
            remaining_quantity = order.get_remaining_quantity()
            order.total_quantity = 0  # Set total quantity to 0 to indicate full exit
            return self._create_exit_info(order, 'RETRIEVAL_TRIGGER', remaining_quantity, 'FULL')
        return None

    def _check_zero_stop_exit(self, order: OrderObject) -> Optional[Dict[str, Any]]:
        '''
        Check if zero stop exit is triggered.
        '''
        ltp = order.get_ltp()
        entry_price = order.get_entry_price()
        # this is around entry price, say within 0.1% of entry price
        threshold = self.dust_value * entry_price  # 0.01 of entry price
        if abs(ltp - entry_price) <= threshold:
            return self._create_exit_info(order, 'ZERO_STOP')
        return None

    def _check_hard_stop_exit(self, order: OrderObject) -> Optional[Dict[str, Any]]:
        '''
        Check if hard stop exit is triggered.
        '''
        ltp = order.get_ltp()
        entry_price = order.get_entry_price()
        # this is in case of ltp is below 2% of entry price in BUY and above 2% in SELL
        threshold = 0.02 * entry_price  # 2% of entry price
        side = order.get_side()
        if (side == "BUY" and ltp <= entry_price - threshold) or (side == "SELL" and ltp >= entry_price + threshold):
            return self._create_exit_info(order, 'HARD_STOP')
        return None

    def _check_on_trigger_exit(self, order: OrderObject) -> Optional[Dict[str, Any]]:
        # TODO: future, convert to enum based flags
        """
            Check if any trigger-based exit conditions are met.
            
            Returns:
                Exit reason string if any trigger condition is met, else empty string.
        """ 
        
        hard_stop = self._check_hard_stop_exit(order)
        if hard_stop is not None:
            return hard_stop
        zero_stop = self._check_zero_stop_exit(order)
        if zero_stop is not None:
            return zero_stop
        retrieval_trigger = self._check_retrieval_trigger_exit(order)
        if retrieval_trigger is not None:
            return retrieval_trigger
        return None

    # market close exit: to be implemented
    def _check_market_close_exit(self, order: OrderObject) -> bool:
        return False

    def check(self, order: OrderObject) -> dict:
        """
        Check all exit conditions based on order state.
        """
        
        # check trigger based exits
        trigger = self._check_on_trigger_exit(order)
        if trigger:
            return trigger

        # Check step-based exits
        step_profit = self._check_profit_exit(order)
        if step_profit:
            return step_profit

        # TODO: check market close exit

        return None

    def _create_exit_info(self, order: OrderObject, exit_reason: str, quantity: int, exit_type: str) -> Dict[str, Any]:
        """Create standardized exit information dictionary."""
        return {
            'symbol': order.get('name'),
            'exit_price': order.get('ltp'),
            'exit_reason': exit_reason,
            'exit_type': exit_type,
            'quantity': quantity,
        }
    
    # updates in order values should be calculated in OrderObject only, ExitManager just provides checks
    def calculate_performance_metrics(self, order_state: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate performance metrics for the order.
        
        Args:
            order_state: Dictionary containing order state information
            
        Returns:
            Dictionary with calculated performance metrics
        """
        entry_price = order_state.get('entry_price', 0)
        ltp = order_state.get('ltp', 0)
        side = order_state.get('side', '')
        min_price = order_state.get('min_price', 0)
        max_price = order_state.get('max_price', 0)
        
        if not entry_price:
            return {
                'current_profit': 0.0,
                'current_profit_percentage': 0.0,
                'max_move_percentage': 0.0,
                'min_move_percentage': 0.0,
                'retreat': 0.0
            }
        
        # Calculate metrics based on side
        if side == "BUY":
            current_profit = ltp - entry_price
            current_profit_percentage = (current_profit / entry_price) * 100
            max_move_percentage = ((max_price - entry_price) / entry_price) * 100
            min_move_percentage = ((min_price - entry_price) / entry_price) * 100
        else:  # SELL
            current_profit = entry_price - ltp
            current_profit_percentage = (current_profit / entry_price) * 100
            max_move_percentage = ((entry_price - min_price) / entry_price) * 100
            min_move_percentage = ((entry_price - max_price) / entry_price) * 100
        
        # Calculate retreat (pullback from maximum favorable movement)
        retreat = max_move_percentage - current_profit_percentage
        
        return {
            'current_profit': current_profit,
            'current_profit_percentage': current_profit_percentage,
            'max_move_percentage': max_move_percentage,
            'min_move_percentage': min_move_percentage,
            'retreat': retreat
        }

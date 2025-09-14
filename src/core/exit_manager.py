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
            return "STEP_EXIT"
        
        return None
        
    def _check_profit_exit(self, order: OrderObject) -> bool:
        # checks if step exit is triggered
        return self._check_step_exit(order)


    # trigger based exits
    def _check_retrieval_trigger_exit(self, order: OrderObject) -> bool:
        return False
    
    def _check_zero_stop_exit(self, order: OrderObject) -> bool:
        return False
    
    def _check_hard_stop_exit(self, order: OrderObject) -> bool:
        return False
    
    def _check_on_trigger_exit(self, order: OrderObject) -> str:
        # TODO: future, convert to enum based flags
        if( self._check_hard_stop_exit(order)):
            return "HARD_STOP"
        elif( self._check_zero_stop_exit(order)):
            return "ZERO_STOP"
        elif( self._check_retrieval_trigger_exit(order)):
            return "RETRIEVAL_TRIGGER"
        return ""
    
    
    # market close exit
    def _check_market_close_exit(self, order: OrderObject) -> bool:
        return False

    def check(self, order: OrderObject) -> dict:
        """
        Check all exit conditions based on order state.
        
        """
        
        # check trigger based exits
        trigger = self._check_on_trigger_exit(order)
        if trigger != "":
            return self._create_exit_info(
                order,
                trigger
            )

        # Check step-based exits
        step_profit = self._check_profit_exit(order)
        if step_profit:
            return step_profit

        #check profit exit
        
        #check market close exit
        
        
        # Trail exit check (retreat exceeds trail threshold)
        if self._check_trail_exit(order):
            return self._create_exit_info(
                order,
                f'TRAIL_EXIT_{order.get_current_trigger()}', 
                'TRAIL'
            )
        
        # Retrieval exit (stop loss)
        if self._check_stop_loss_exit(order_state):
            return self._create_exit_info(
                order_state, 'RETRIEVAL_EXIT', 'LOSS'
            )
        
        return None
    
    
    def _check_trail_exit(self, order_state: Dict[str, Any]) -> bool:
        """Check if retreat exceeds trail threshold."""
        retreat = order_state.get('retreat', 0)
        current_trail = order_state.get('current_trail', 0)
        return retreat >= current_trail
    
    def _check_stop_loss_exit(self, order_state: Dict[str, Any]) -> bool:
        """Check if current profit percentage triggers stop loss."""
        current_profit_percentage = order_state.get('current_profit_percentage', 0)
        return current_profit_percentage <= -self.retrieval_exit
    
    
    def _create_exit_info(self, order: OrderObject, exit_reason: str) -> Dict[str, Any]:
        """Create standardized exit information dictionary."""
        return {
            'symbol': order.get('name'),
            'exit_price': order.get('ltp'),
            'exit_reason': exit_reason,
            'quantity': order.get_current_quantity(),
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

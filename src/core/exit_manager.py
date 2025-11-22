from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from src.core.event_bus.events import OrderEvent
from src.core.event_bus.mixins import Publisher
from src.logger_factory import get_logger
from src.time_control import TimeChecker
import src.basic as basic
from src.global_enum import *
if TYPE_CHECKING:
    from src.core.order_object import OrderObject


class ExitManager(Publisher):
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
        super().__init__()
        self.logger = get_logger(name)
        self.dust_value = 0.01
        self.time = TimeChecker()
        self.count = 0
        
        
    # step based exits, to be updated
    def _check_step_exit(self, order: 'OrderObject') -> Optional[Dict[str, Any]]:
        """
        Check if step change triggers partial profit exit.
        THIS IS PROFIT EXIT
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
            order.filled_quantity += current_quantity
            order.remaining_quantity = order.total_quantity - order.filled_quantity
            # TODO: make this increment safe
            order.current_step_idx += 1
            return self._create_exit_info(order, f'STEP_EXIT_{current_step_idx}', current_quantity, 'PARTIAL')

        return None


    def _check_retrieval_trigger_exit(self, order: 'OrderObject') -> Optional[Dict[str, Any]]:
        '''
        Check if retrieval trigger exit is triggered.
        THIS IS SAVING PROFIT EXIT

        Steps: 1.5%, 3%, 4.5%, 6%, ...
        When price retreats, exit at the last step price crossed, not at the retrace price.
        '''
        step_size = 1.5  # percent
        max_steps = 10   # up to 15% (adjust as needed)
        step_thresholds = [step_size * (i + 1) for i in range(max_steps)]

        side = order.get_side()
        ltp = order.get_ltp()
        entry_price = order.get_entry_price()
        max_price = order.get_max_price()
        min_price = order.get_min_price()

        # Calculate max favorable move percentage and step index
        if side == "BUY":
            max_move_pct = ((max_price - entry_price) / entry_price) * 100
            current_move_pct = ((ltp - entry_price) / entry_price) * 100
        else:  # SELL
            max_move_pct = ((entry_price - min_price) / entry_price) * 100
            current_move_pct = ((entry_price - ltp) / entry_price) * 100

        # Find the highest step crossed
        last_step_pct = 0
        for step in step_thresholds:
            if max_move_pct >= step:
                last_step_pct = step
            else:
                break

        # Track last step crossed in order object
        if not hasattr(order, 'retrieval_last_step_pct'):
            order.retrieval_last_step_pct = 0
        if last_step_pct > order.retrieval_last_step_pct:
            order.retrieval_last_step_pct = last_step_pct

        # If price retreats below last step price, trigger exit at that step price
        if order.retrieval_last_step_pct > 0:
            if side == "BUY":
                step_price = entry_price * (1 + order.retrieval_last_step_pct / 100)
                if ltp <= step_price:
                    self.count += 1
                    print(f"Triggered retrieval exit #{self.count} ({side}) at step {order.retrieval_last_step_pct}% (price {step_price})")
                    self.logger.info(f"Retrieval trigger exit hit for {order.get_name()} at LTP {ltp} (step {order.retrieval_last_step_pct}%)")
                    order.state = ORDERSTATE.CLOSE
                    return self._create_exit_info(order, f'RETRIEVAL_TRIGGER_{order.retrieval_last_step_pct}', order.quantity, 'FULL')
            else:  # SELL
                step_price = entry_price * (1 - order.retrieval_last_step_pct / 100)
                if ltp >= step_price:
                    self.count += 1
                    print(f"Triggered retrieval exit #{self.count} ({side}) at step {order.retrieval_last_step_pct}% (price {step_price})")
                    self.logger.info(f"Retrieval trigger exit hit for {order.get_name()} at LTP {ltp} (step {order.retrieval_last_step_pct}%)")
                    order.state = ORDERSTATE.CLOSE
                    return self._create_exit_info(order, f'RETRIEVAL_TRIGGER_{order.retrieval_last_step_pct}', order.quantity, 'FULL')

        return None


    # Net ZERO STOP
    def _check_net_zero_stop_exit(self,order: 'OrderObject') -> Optional[Dict[str,Any]]:
        '''
        THIS IS A NET ZERO EXIT 
        this is step after sometime, this becomes a net 0 profit
        considers transaction and taxes charges taking trade to no loss
        '''
        
        # assuming 1% above 
        if abs(order.ltp - order.net_zero_stop) <= 1 and order.net_zero_state:
            order.state = ORDERSTATE.CLOSE
            self.logger.info(f"Net zero stop exit hit for {order.get_name()} at LTP {order.get_ltp()}")
            return self._create_exit_info(order, 'ZERO_STOP', order.quantity,'FULL')
        return None
    
    # ZERO STOP
    def _check_zero_stop_exit(self, order: 'OrderObject') -> Optional[Dict[str, Any]]:
        '''
        Check if zero stop exit is triggered.
        THIS IS LOSS STOP
        '''
        ltp = order.get_ltp()
        # this is around entry price, say within 0.1% of entry price
        threshold = self.dust_value * order.const_entry_price  # 0.01 of entry price
        if abs(ltp - order.const_entry_price) <= threshold and order.zero_stop_state:
            order.state = ORDERSTATE.CLOSE
            self.logger.info(f"Zero stop exit hit for {order.get_name()} at LTP {order.get_ltp()}")
            return self._create_exit_info(order, 'ZERO_STOP', order.quantity,'FULL')
        return None

    # LOSS STOP
    def _check_loss_stop_exit(self, order: 'OrderObject') -> Optional[Dict[str, Any]]:
        '''
        Check if hard stop exit is triggered.
        This is a LOSS STOP
        '''
        ltp = order.get_ltp()
        loss_stop = order.loss_stop
    
        if basic.tolerance(ltp,loss_stop):
            # print("LOSS STOP HIT")
            order.state = ORDERSTATE.CLOSE
            self.logger.info(f"Loss stop exit hit for {order.get_name()} at LTP {order.get_ltp()}")
            return self._create_exit_info(order, 'LOSS_STOP', order.quantity,'FULL')
        return None
    
    # market close exit: to be implemented
    def _check_market_close_exit(self, order: 'OrderObject') -> bool:
        #TODO: read from config the market close time 
        market_close_time = '13:37'
        if self.time.is_same_time(market_close_time):
            order.state = ORDERSTATE.CLOSE
            self.logger.info(f"Market close exit hit for {order.get_name()} at LTP {order.get_ltp()}")
            return self._create_exit_info(order,'MARKET CLOSE',order.quantity,'FULL')
        return None

    def _check_on_trigger_exit(self, order: 'OrderObject') -> Optional[Dict[str, Any]]:
        
        # TODO: future, convert to enum based flags
        """
            Check if any trigger-based exit conditions are met.
            
            Returns:
                Exit reason string if any trigger condition is met, else empty string.
        """ 
        
        # currently returning only in reterival exit
        # step_exit = self._check_step_exit(order)
        # if step_exit is not None:
        #     return step_exit
        loss_stop = self._check_loss_stop_exit(order)
        if loss_stop is not None:
            # print("L",loss_stop)
            return loss_stop
        
        zero_stop = self._check_zero_stop_exit(order)
        if zero_stop is not None:
            # print("Z",zero_stop)
            return zero_stop
        
        net_zero = self._check_net_zero_stop_exit(order)
        if net_zero is not None:
            # print("N",net_zero)
            return net_zero
        
        # print("HELLO ?")
        retrieval_trigger = self._check_retrieval_trigger_exit(order)
        if retrieval_trigger is not None:
            # print("R",retrieval_trigger)
            return retrieval_trigger
        
        market_close = self._check_market_close_exit(order)
        if market_close is not None:
            # print("M",market_close)
            return market_close
        return None

    
    def _create_exit_info(self, order: 'OrderObject', exit_reason: str, quantity: int, exit_type: str) -> Dict[str, Any]:
        """Create standardized exit information dictionary."""
        return {
            'symbol': order.get_name(),
            'exit_price': order.get_ltp(),
            'exit_reason': exit_reason,
            'exit_type': exit_type,
            'quantity': order.quantity,
        }
    
    def check(self, order: 'OrderObject') -> Optional[Dict[str, Any]]:
        """
        Check all exit conditions based on order state.
        """
        # check step exit 
        
        # check trigger based exits
        trigger = self._check_on_trigger_exit(order)
        
        # print("Exit check result:", trigger)

        if trigger is not None:
            # create exit signal and send it to executor
            # Send exit signal with opposite side
            print('exit trigger true', trigger)
            opposite_side = "SELL" if order.const_side == "BUY" else "BUY"
            exitEvent = OrderEvent(
                order_id=order.id,
                timestamp=order.last_update_time,
                source=self.__class__.__name__,
                instrument=order.const_instrument,
                side=opposite_side,
                price=order.ltp,
                strategy='VWAP',
                type='FULL',
                candle=order.current_candle,
                meta_info= trigger
            )
            
            # print("Publishing")
            self.publish_event(exitEvent)
            return True
            

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

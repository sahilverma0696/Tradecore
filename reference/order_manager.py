from order_object import OrderObject
from order_logger import OrderLogger
from logger_factory import get_logger

class OrderManager:
    def __init__(self, log_dir="logs"):
        """
        Manages multiple OrderObject instances, keyed by name.
        """
        self.orders = {}  # name -> OrderObject
        self.logger = get_logger("OrderManager")
        self.order_logger = OrderLogger(log_dir=log_dir)
        self.on_order_created = None  # Callback for when a new order is created
        self.logger.info("OrderManager initialized.")

    def create_order(self, timestamp, name, instrument, step, trail, side, candle=None):
        if name not in self.orders:
            # Create order with candle data if available
            order = OrderObject(
                name=name,
                instrument=instrument,
                step=step,
                trail=trail,
                side=side,
                candle=candle
            )
            
            # If candle wasn't provided in constructor, set it separately
            if candle and not order.get_entry_price():
                order.set_current_candle(candle)
                
            self.orders[name] = order
            self.logger.info(
                f"Created new order: {timestamp} {name}, "
                f"side={side}, inst={instrument}, "
                f"entry_price={order.get_entry_price():.2f}"
            )
            
            # Log the order creation
            self.order_logger.log_entry(order)
            
            # Trigger order created callback if registered
            if callable(self.on_order_created):
                try:
                    self.on_order_created(
                        name=name,
                        order=order,
                        timestamp=timestamp
                    )
                except Exception as e:
                    self.logger.error(f"Error in on_order_created callback: {e}")
            
            return order
        else:
            existing_order = self.orders[name]
            self.logger.warning(
                f"Order {timestamp} {name} already exists. "
                f"Current state: side={existing_order.get_side()}, "
                f"entry={existing_order.get_entry_price():.2f}"
            )
            return existing_order
    
    def get_order(self, name):
        order = self.orders.get(name)
        if order:
            self.logger.debug(f"Retrieved order: {name}")
        else:
            self.logger.debug(f"Order not found: {name}")
        return order

    def has_order(self, name):
        exists = name in self.orders
        self.logger.debug(f"Checking existence of order {name}: {exists}")
        return exists

    def update_ltp(self, name, ltp, timestamp=None):
        """
        Update the last traded price for an order
        
        Args:
            name (str): Order name/identifier
            ltp (float): Last traded price
            timestamp (datetime, optional): Timestamp of the LTP update
        """
        if name in self.orders:
            self.orders[name].set_ltp(ltp, timestamp=timestamp)
            self.logger.debug(f"Updated LTP for {name}: {ltp} at {timestamp}")
        else:
            self.logger.warning(f"Tried to update LTP for non-existent order: {name}")

    def update_candle(self, name, candle, timestamp=None):
        """
        Update the current candle for an order
        
        Args:
            name (str): Order name/identifier
            candle (dict): Current candle data
            timestamp (datetime, optional): Timestamp of the candle
        """
        if name in self.orders:
            self.orders[name].set_current_candle(candle, timestamp=timestamp)
            self.logger.debug(f"Updated candle for {name}: {candle} at {timestamp}")
            self.orders[name].update_step()
            self.orders[name].update_trail()
            self.logger.debug(f"Applied step/trail logic for {name}")
        else:
            self.logger.warning(f"Tried to update candle for non-existent order: {name}")

    def get_all_orders(self):
        self.logger.debug("Returning all current orders.")
        return self.orders

    def get_order_state(self, name):
        if name in self.orders:
            state = self.orders[name].as_dict()
            self.logger.debug(f"Order state for {name}: {state}")
            return state
        self.logger.warning(f"Tried to get state for non-existent order: {name}")
        return None

    def remove_order(self, name, timestamp, exit_reason=None, exit_price=None):
        if name in self.orders:
            order = self.orders.pop(name)
            self.logger.info(f"Removed order:{timestamp} {name}")
            
            # Log the order exit with reason and exit price if provided
            if exit_reason:
                self.order_logger.log_exit(order, exit_reason=exit_reason, exit_price=exit_price)
            return order
        self.logger.warning(f"Tried to remove non-existent order: {name}")
        return None

    def reset(self):
        self.orders.clear()
        self.logger.info("All orders have been reset.")



# from order_manager import OrderManager

# om = OrderManager()

# # Create new order
# om.create_order(
#     name="NIFTY 27000 CE 26 JUN 25",
#     instrument="NSE_FO|50969",
#     step=[0.1, 0.2, 0.3],
#     trail=[0.03, 0.05, 0.07],
#     side="BUY"
# )

# # Update live LTP
# om.update_ltp("NIFTY 27000 CE 26 JUN 25", 112)

# # Update with new candle
# om.update_candle("NIFTY 27000 CE 26 JUN 25", {'open': 100})

# # Get full state
# print(om.get_order_state("NIFTY 27000 CE 26 JUN 25"))

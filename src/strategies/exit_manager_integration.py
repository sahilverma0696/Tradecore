"""Integration helper for ExitManager to work with OrderManager flow"""

from src.logger_factory import get_logger

class ExitManagerIntegration:
    """Helper class to integrate ExitManager with the order flow"""
    
    def __init__(self, exit_manager):
        self.exit_manager = exit_manager
        self._logger = get_logger("ExitManagerIntegration")
    
    def check_exit(self, order, timestamp=None):
        """Check if order should be exited based on exit manager logic"""
        if not order.is_active():
            return False
            
        # This would call the actual exit manager logic
        # You'll need to implement the specific exit logic in your ExitManager class
        exit_signal = self.exit_manager.should_exit(order, timestamp)
        
        if exit_signal:
            self._logger.info(f"Exit signal generated for order {order.get_name()}: {exit_signal}")
            return True
        
        return False

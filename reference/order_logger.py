import csv
import os
import logging
from datetime import datetime
import pytz

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrderLogger:
    def __init__(self, log_dir="logs"):
        """
        Initialize the OrderLogger with a directory to store logs.
        
        Args:
            log_dir (str): Directory to store log files
        """
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, "order_logs.csv")
        self._ensure_log_directory()
        self._initialize_log_file()
    
    def _ensure_log_directory(self):
        """Ensure the log directory exists."""
        os.makedirs(self.log_dir, exist_ok=True)
    
    def _initialize_log_file(self):
        """Initialize the CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.log_file):
            # Define CSV header with grouped columns
            headers = [
                # Basic info
                "timestamp", "order_id", "instrument",
                
                # Trade details
                "side", "event_type", "entry_price", "exit_price", "exit_reason",
                "pnl_amount", "pnl_percent",
                
                # Order parameters
                "step", "trail", "quantity",
                
                # Candle data
                "current_candle_high", "current_candle_low", "current_candle_close", "vwap"
            ]
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
    
    def log_order_event(self, order, event_type, **kwargs):
        """
        Log an order event to the CSV file.
        
        Args:
            order: The OrderObject instance
            event_type (str): Type of event (ENTRY, EXIT, MODIFICATION, etc.)
            **kwargs: Additional event-specific data
        """
        candle = order.get_current_candle()
        entry_price = order.get_entry_price()
        current_price = order.get_ltp()
        
        # Get timestamp from candle if available, otherwise use current time
        if candle and 'timestamp' in candle:
            timestamp = candle['timestamp']
            if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is None:
                # If timestamp is naive, localize to IST
                timestamp = pytz.timezone('Asia/Kolkata').localize(timestamp)
            elif hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                # Convert to IST if in different timezone
                timestamp = timestamp.astimezone(pytz.timezone('Asia/Kolkata'))
        else:
            # Fallback to current time in IST
            timestamp = datetime.now(pytz.timezone('Asia/Kolkata'))
        
        # Prepare log data with new column order
        log_data = {
            # Basic info
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "order_id": order.get_name(),
            "instrument": order.get_instrument(),
            
            # Trade details
            "side": order.get_side(),
            "event_type": event_type,
            "entry_price": entry_price if entry_price else None,
            "exit_price": current_price if event_type == "EXIT" else None,
            "exit_reason": kwargs.get('exit_reason'),
            "pnl_amount": None,  # Will be calculated for EXIT events
            "pnl_percent": None,  # Will be calculated for EXIT events
            
            # Order parameters
            "step": order.get_step(),
            "trail": order.get_trail(),
            "quantity": 1,  # Assuming quantity is 1, adjust if needed
            
            # Candle data
            "current_candle_high": candle.get('high') if candle else None,
            "current_candle_low": candle.get('low') if candle else None,
            "current_candle_close": candle.get('close') if candle else None,
            "vwap": candle.get('vwap') if candle else None,
            
            # Keep price for backward compatibility (hidden from CSV)
            "price": current_price
        }
        
        # For exit events, include PnL calculation if entry price is available
        if event_type == "EXIT" and entry_price and entry_price > 0:
            exit_price = current_price
            if order.get_side() == "BUY":
                pnl = exit_price - entry_price
                pnl_pct = (pnl / entry_price) * 100
            else:  # SELL
                pnl = entry_price - exit_price
                pnl_pct = (pnl / entry_price) * 100
                
            log_data.update({
                "exit_price": exit_price,
                "pnl_amount": f"{pnl:.2f}",
                "pnl_percent": f"{abs(pnl_pct):.2f}%"
            })
        
        # Write to CSV
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=log_data.keys())
            writer.writerow(log_data)
    
    def log_entry(self, order):
        """Log an order entry event."""
        self.log_order_event(order, "ENTRY")
    
    def log_exit(self, order, exit_reason=None, exit_price=None):
        """
        Log an order exit event.
        
        Args:
            order: The OrderObject instance
            exit_reason (str, optional): Reason for exit
            exit_price (float, optional): Actual exit price. If not provided, uses order's LTP.
        """
        # Use provided exit price or fall back to LTP
        exit_price = exit_price or order.get_ltp()
        entry_price = order.get_entry_price()
        
        # Log the exit event
        self.log_order_event(
            order,
            "EXIT",
            exit_reason=exit_reason,
            entry_price=entry_price,
            exit_price=exit_price
        )
        
        # Log a summary of the trade
        if entry_price and entry_price > 0 and exit_price > 0:
            if order.get_side() == "BUY":
                pnl = exit_price - entry_price
                pnl_pct = (pnl / entry_price) * 100
            else:  # SELL
                pnl = entry_price - exit_price
                pnl_pct = (pnl / entry_price) * 100
                
            logger.info(
                f"TRADE CLOSED | {order.get_name()} | {order.get_side()} | "
                f"Entry: {entry_price:.2f} | Exit: {exit_price:.2f} | "
                f"PnL: {pnl:+.2f} ({pnl_pct:+.2f}%) | Reason: {exit_reason}"
            )
    
    def log_modification(self, order, modification_details):
        """
        Log an order modification event.
        
        Args:
            order: The OrderObject instance
            modification_details (dict): Details about the modification
        """
        self.log_order_event(order, "MODIFICATION", **modification_details)

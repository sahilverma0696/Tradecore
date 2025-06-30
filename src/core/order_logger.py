import csv
import os
from datetime import datetime
from src.logger_factory import get_logger

class OrderLogger:
    """CSV logger for order entries and exits."""
    def __init__(self, log_dir: str = "logs"):
        os.makedirs(log_dir, exist_ok=True)
        self._path = os.path.join(log_dir, "orders.csv")
        self._logger = get_logger("OrderLogger")
        if not os.path.exists(self._path):
            with open(self._path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp",
                        "name",
                        "instrument",
                        "side",
                        "action",  # entry / exit
                        "price",
                        "reason",
                    ]
                )

    def log_entry(self, order):
        self._write(order, action="entry", price=order.get_entry_price(), reason="signal")

    def log_exit(self, order, exit_reason: str, exit_price: float):
        self._write(order, action="exit", price=exit_price, reason=exit_reason)

    # ------------------------------------------------------------------
    def _write(self, order, action: str, price: float, reason: str):
        with open(self._path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(sep=' ', timespec='seconds'),
                order.get_name(),
                order.get_instrument(),
                order.get_side(),
                action,
                price,
                reason,
            ])
        self._logger.debug(f"Logged {action} for {order.get_name()} reason={reason} price={price}")

import csv
import json
import os
from collections import deque
from datetime import datetime
from typing import Optional
from src.logger_factory import get_logger

_CSV_COLUMNS = [
    "exit_time", "entry_time", "duration_s",
    "symbol", "instrument", "side",
    "quantity",
    "entry_price", "exit_price",
    "pnl", "pnl_pct",
    "peak_pct", "min_pct",
    "exit_reason",
]

_ARCHIVE_FILE = "data/order_archive.json"
_ARCHIVE_MAX  = 500   # keep last N closed orders in archive


class OrderLogger:
    """Logs order lifecycle to CSV + rolling JSON archive."""

    def __init__(self, log_dir: str = "logs"):
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs("data", exist_ok=True)
        self._csv_path = os.path.join(log_dir, "orders.csv")
        self._logger   = get_logger("OrderLogger")
        self._archive: deque = deque(maxlen=_ARCHIVE_MAX)

        # Load existing archive so history survives restarts
        self._load_archive()

        if not os.path.exists(self._csv_path):
            with open(self._csv_path, 'w', newline='') as f:
                csv.writer(f).writerow(_CSV_COLUMNS)

    # ── Public API ────────────────────────────────────────────────────────────

    def log_entry(self, order):
        """Called when a new order is opened — no CSV row, just debug."""
        self._logger.info(
            f"ENTRY  {order.get_name()}  {order.get_side()}  "
            f"@ {order.get_entry_price():.4f}  qty={order.quantity}"
        )

    def log_exit(self, order, exit_reason: str, exit_price: float):
        """Called when an order closes — writes CSV row + archive entry."""
        entry_price = order.get_entry_price()
        side        = order.get_side()
        qty         = order.quantity
        entry_time  = order.get_entry_time()
        exit_time   = datetime.now()

        if side == "BUY":
            pnl = (exit_price - entry_price) * qty
        else:
            pnl = (entry_price - exit_price) * qty
        pnl_pct  = (pnl / (entry_price * qty)) * 100 if qty and entry_price else 0.0
        peak_pct = order.get_max_move_percentage()
        min_pct  = order.get_min_move_percentage()

        duration_s = int((exit_time - entry_time).total_seconds()) if entry_time else 0

        row = {
            "exit_time":   exit_time.isoformat(sep=' ', timespec='seconds'),
            "entry_time":  entry_time.isoformat(sep=' ', timespec='seconds') if entry_time else "",
            "duration_s":  duration_s,
            "symbol":      order.get_name(),
            "instrument":  order.get_instrument(),
            "side":        side,
            "quantity":    qty,
            "entry_price": round(entry_price, 4),
            "exit_price":  round(exit_price,  4),
            "pnl":         round(pnl,     2),
            "pnl_pct":     round(pnl_pct, 4),
            "peak_pct":    round(peak_pct, 4),
            "min_pct":     round(min_pct,  4),
            "exit_reason": exit_reason,
        }

        self._write_csv(row)
        self._append_archive(row)

        self._logger.info(
            f"EXIT   {order.get_name()}  {side}  "
            f"@ {exit_price:.4f}  pnl={pnl:+.2f} ({pnl_pct:+.2f}%)  "
            f"reason={exit_reason}  duration={duration_s}s"
        )

    # ── Archive helpers ───────────────────────────────────────────────────────

    def get_archive(self):
        return list(self._archive)

    def _load_archive(self):
        try:
            if os.path.exists(_ARCHIVE_FILE):
                with open(_ARCHIVE_FILE) as f:
                    data = json.load(f)
                for rec in data[-_ARCHIVE_MAX:]:
                    self._archive.append(rec)
        except Exception as e:
            self._logger.debug(f"archive load error: {e}")

    def _append_archive(self, row: dict):
        self._archive.append(row)
        try:
            tmp = _ARCHIVE_FILE + ".tmp"
            with open(tmp, 'w') as f:
                json.dump(list(self._archive), f, indent=2)
            os.replace(tmp, _ARCHIVE_FILE)
        except Exception as e:
            self._logger.debug(f"archive write error: {e}")

    def _write_csv(self, row: dict):
        with open(self._csv_path, 'a', newline='') as f:
            csv.DictWriter(f, fieldnames=_CSV_COLUMNS).writerow(row)

"""Base executor — template pattern for all order execution implementations."""
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional

from src.logger_factory import get_logger
from src.core.event_bus.mixins import Publisher, Subscriber
from src.core.event_bus.events import OrderEvent


class BaseExecutor(ABC, Publisher, Subscriber):
    """
    Template-pattern base for order executors.

    Subclasses must implement:
        _place_order_impl()
        _normalize_symbol()
        _validate_connection()
        _get_order_status_impl()
        _cancel_order_impl()
    """

    def __init__(self, paper_trade: bool = True, config: Dict[str, Any] = None):
        super().__init__()
        self.paper_trade = paper_trade
        self.config = config or {}
        self._logger = get_logger(self.__class__.__name__)

        self.max_retries: int = self.config.get("max_retries", 3)
        self.retry_delay: float = self.config.get("retry_delay", 1.0)

        self.open_trades: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: list = []
        self.total_executed_orders: int = 0

        self.subscribe_to_event(OrderEvent, self._on_order_event)
        self._logger.info(f"{self.__class__.__name__} initialized (paper={self.paper_trade})")

    # ------------------------------------------------------------------
    # Event handler — concrete, dispatches to execute_order
    # ------------------------------------------------------------------

    def _on_order_event(self, event: OrderEvent):
        self.execute_order(
            symbol=event.instrument,
            direction=event.side,
            timestamp=getattr(event, "timestamp", None),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_order(self, symbol: str, direction: str, timestamp: datetime = None) -> bool:
        """Main order execution method."""
        try:
            normalized = self._normalize_symbol(symbol)
            side = self._normalize_direction(direction)
            quantity = self._get_quantity(symbol)
            timestamp = timestamp or datetime.now()

            self._logger.info(f"Executing {side} {quantity} {normalized}")

            if self.paper_trade:
                return self._execute_paper_trade(normalized, side, quantity, timestamp)
            return self._execute_real_trade(normalized, side, quantity, timestamp)

        except Exception as e:
            self._logger.error(f"execute_order failed for {symbol}: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        if self.paper_trade:
            return self.open_trades.get(order_id)
        try:
            return self._get_order_status_impl(order_id)
        except Exception as e:
            self._logger.error(f"get_order_status({order_id}): {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        if self.paper_trade:
            if order_id in self.open_trades:
                self.open_trades[order_id]["status"] = "CANCELLED"
                return True
            return False
        try:
            return self._cancel_order_impl(order_id)
        except Exception as e:
            self._logger.error(f"cancel_order({order_id}): {e}")
            return False

    def get_open_trades(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.open_trades)

    def get_closed_trades(self) -> list:
        return list(self.closed_trades)

    def get_execution_stats(self) -> Dict[str, Any]:
        return {
            "total_orders": self.total_executed_orders,
            "open_trades": len(self.open_trades),
            "closed_trades": len(self.closed_trades),
            "paper_trade": self.paper_trade,
        }

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        pass

    @abstractmethod
    def _normalize_symbol(self, symbol: str) -> str:
        pass

    @abstractmethod
    def _validate_connection(self) -> bool:
        pass

    @abstractmethod
    def _get_order_status_impl(self, order_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def _cancel_order_impl(self, order_id: str) -> bool:
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_direction(self, direction: str) -> str:
        d = direction.upper()
        if d in ("B", "BUY"):
            return "BUY"
        if d in ("S", "SELL"):
            return "SELL"
        raise ValueError(f"Invalid direction: {direction}")

    def _get_quantity(self, symbol: str) -> int:
        try:
            from src.config_manager import ConfigManager
            cfg = ConfigManager()
            quantities = cfg.get_value("quantities") or {}
            default = cfg.get_value("default_quantity") or 1
            return int(quantities.get(symbol, default))
        except Exception:
            return 1

    def _execute_paper_trade(self, symbol: str, side: str, quantity: int, timestamp: datetime) -> bool:
        order_id = f"PAPER_{int(timestamp.timestamp())}_{len(self.open_trades)}"
        self.open_trades[order_id] = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "timestamp": timestamp,
            "status": "FILLED",
            "price": 0.0,
        }
        self.total_executed_orders += 1
        self._logger.info(f"Paper trade filled: {order_id}")
        return True

    def _execute_real_trade(self, symbol: str, side: str, quantity: int, timestamp: datetime) -> bool:
        if not self._validate_connection():
            self._logger.error("Connection validation failed")
            return False

        for attempt in range(self.max_retries):
            try:
                result = self._place_order_impl(symbol, side, quantity)
                if result and result.get("order_id"):
                    order_id = result["order_id"]
                    self.open_trades[order_id] = {
                        "order_id": order_id,
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                        "timestamp": timestamp,
                        "status": result.get("status", "PENDING"),
                        "price": result.get("price", 0.0),
                    }
                    self.total_executed_orders += 1
                    self._logger.info(f"Order placed: {order_id}")
                    return True
                self._logger.warning(f"Order failed attempt {attempt + 1}")
            except Exception as e:
                self._logger.error(f"Order error attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)

        self._logger.error(f"All {self.max_retries} attempts exhausted")
        return False

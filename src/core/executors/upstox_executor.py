"""Upstox order executor."""
from datetime import datetime
from typing import Dict, Any, Optional
from .base_executor import BaseExecutor


class UpstoxExecutor(BaseExecutor):
    """Executes orders via Upstox API."""

    def __init__(self, client=None, paper_trade: bool = True, config: Dict[str, Any] = None):
        super().__init__(paper_trade=paper_trade, config=config)
        self.client = client
        self.exchange: str = self.config.get("exchange", "NSE_FO")
        self.product: str = self.config.get("product", "I")
        self.validity: str = self.config.get("validity", "DAY")

    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Upstox client not initialized")

        params = {
            "quantity": quantity,
            "product": self.product,
            "validity": self.validity,
            "price": 0,
            "tag": f"TC_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "instrument_token": self._get_instrument_token(symbol),
            "order_type": "MARKET" if order_type == "MARKET" else "LIMIT",
            "transaction_type": side,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False,
        }
        if order_type == "LIMIT":
            params["price"] = self.config.get("limit_price", 0)

        response = self.client.place_order(**params)
        return {
            "order_id": response.get("order_id"),
            "status": "PENDING",
            "price": params.get("price", 0),
        }

    def _normalize_symbol(self, symbol: str) -> str:
        return symbol.upper()

    def _validate_connection(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.get_profile()
            return True
        except Exception as e:
            self._logger.error(f"Upstox connection failed: {e}")
            return False

    def _get_order_status_impl(self, order_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            raise RuntimeError("Upstox client not initialized")
        details = self.client.get_order_details(order_id)
        if not details:
            return None
        return {
            "order_id": order_id,
            "status": details.get("status"),
            "filled_quantity": details.get("filled_quantity", 0),
            "pending_quantity": details.get("pending_quantity", 0),
            "average_price": details.get("average_price", 0),
        }

    def _cancel_order_impl(self, order_id: str) -> bool:
        if not self.client:
            raise RuntimeError("Upstox client not initialized")
        try:
            self.client.cancel_order(order_id)
            return True
        except Exception as e:
            self._logger.error(f"Cancel failed {order_id}: {e}")
            return False

    def _get_instrument_token(self, symbol: str) -> str:
        return self.config.get("instrument_map", {}).get(symbol, symbol)

    def get_funds(self) -> Dict[str, Any]:
        if not self.client or self.paper_trade:
            return {}
        try:
            return self.client.get_balance()
        except Exception as e:
            self._logger.error(f"Funds fetch failed: {e}")
            return {}

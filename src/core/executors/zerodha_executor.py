"""Zerodha Kite order executor."""
from typing import Dict, Any, Optional
from .base_executor import BaseExecutor


class ZerodhaExecutor(BaseExecutor):
    """Executes orders via Zerodha Kite API."""

    def __init__(self, client=None, paper_trade: bool = True, config: Dict[str, Any] = None):
        super().__init__(paper_trade=paper_trade, config=config)
        self.client = client
        self.exchange: str = self.config.get("exchange", "NFO")
        self.product: str = self.config.get("product", "MIS")
        self.variety: str = self.config.get("variety", "regular")

    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Zerodha client not initialized")

        transaction_type = (
            self.client.TRANSACTION_TYPE_BUY if side == "BUY" else self.client.TRANSACTION_TYPE_SELL
        )
        params = {
            "variety": self.client.VARIETY_REGULAR,
            "exchange": self._get_exchange(symbol),
            "tradingsymbol": symbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": (
                self.client.ORDER_TYPE_MARKET if order_type == "MARKET" else self.client.ORDER_TYPE_LIMIT
            ),
            "product": self.client.PRODUCT_MIS,
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
            self.client.profile()
            return True
        except Exception as e:
            self._logger.error(f"Zerodha connection failed: {e}")
            return False

    def _get_order_status_impl(self, order_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            raise RuntimeError("Zerodha client not initialized")
        for order in self.client.orders():
            if order.get("order_id") == order_id:
                return {
                    "order_id": order_id,
                    "status": order.get("status"),
                    "filled_quantity": order.get("filled_quantity", 0),
                    "pending_quantity": order.get("pending_quantity", 0),
                    "average_price": order.get("average_price", 0),
                }
        return None

    def _cancel_order_impl(self, order_id: str) -> bool:
        if not self.client:
            raise RuntimeError("Zerodha client not initialized")
        try:
            self.client.cancel_order(variety=self.client.VARIETY_REGULAR, order_id=order_id)
            return True
        except Exception as e:
            self._logger.error(f"Cancel failed {order_id}: {e}")
            return False

    def _get_exchange(self, symbol: str) -> str:
        if "NIFTY" in symbol or "BANKNIFTY" in symbol:
            return "NFO"
        if symbol.endswith("EQ"):
            return "NSE"
        return self.exchange

    def get_positions(self) -> Dict[str, Any]:
        if not self.client or self.paper_trade:
            return {}
        try:
            pos = self.client.positions()
            return {"net": pos.get("net", []), "day": pos.get("day", [])}
        except Exception as e:
            self._logger.error(f"Positions fetch failed: {e}")
            return {}

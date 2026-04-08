"""Binance order executor."""
from typing import Dict, Any, Optional
from .base_executor import BaseExecutor


class BinanceExecutor(BaseExecutor):
    """Executes orders via Binance API."""

    def __init__(self, client=None, paper_trade: bool = True, config: Dict[str, Any] = None):
        super().__init__(paper_trade=paper_trade, config=config)
        self.client = client
        self.test_mode: bool = self.config.get("test_mode", True)
        self.time_in_force: str = self.config.get("time_in_force", "GTC")

    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Binance client not initialized")

        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET" if order_type == "MARKET" else "LIMIT",
            "quantity": quantity,
        }
        if order_type == "LIMIT":
            params["timeInForce"] = self.time_in_force
            params["price"] = self.config.get("limit_price", 0)

        if self.test_mode:
            response = self.client.create_test_order(**params)
        else:
            response = self.client.create_order(**params)

        return {
            "order_id": response.get("orderId"),
            "status": response.get("status", "PENDING"),
            "price": response.get("price", 0),
        }

    def _normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.upper().replace("/", "").replace("-", "")
        if not any(symbol.endswith(q) for q in ("USDT", "BTC", "ETH", "BNB")):
            symbol += "USDT"
        return symbol

    def _validate_connection(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.get_account()
            return True
        except Exception as e:
            self._logger.error(f"Binance connection failed: {e}")
            return False

    def _get_order_status_impl(self, order_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            raise RuntimeError("Binance client not initialized")
        symbol = self.open_trades.get(order_id, {}).get("symbol")
        if not symbol:
            return None
        order = self.client.get_order(symbol=symbol, orderId=order_id)
        return {
            "order_id": order_id,
            "status": order.get("status"),
            "filled_quantity": float(order.get("executedQty", 0)),
            "average_price": float(order.get("avgPrice", 0)),
        }

    def _cancel_order_impl(self, order_id: str) -> bool:
        if not self.client:
            raise RuntimeError("Binance client not initialized")
        symbol = self.open_trades.get(order_id, {}).get("symbol")
        if not symbol:
            return False
        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except Exception as e:
            self._logger.error(f"Cancel failed {order_id}: {e}")
            return False

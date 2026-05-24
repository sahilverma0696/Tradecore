from typing import Dict
from datetime import datetime
import json
import os
from src.core.event_bus import Subscriber, Publisher, EntrySignal
from src.core.event_bus.events import CandleGenerated, QuoteEvent, OrderEvent
from src.logger_factory import get_logger
from src.core.order_object import OrderObject
from src.core.order_logger import OrderLogger
from src.config_manager import ConfigManager
from src.core.thread_manager import ThreadManager
from src.global_enum import ORDERSTATE
import src.basic as basic


class OrderManager(Subscriber, Publisher):
    """Manages order lifecycle: entry, tick updates, exit, and IPC writes."""

    def __init__(self, log_dir: str = "logs"):
        super().__init__()

        self._orders: Dict[str, OrderObject] = {}
        self._logger = get_logger("OrderManager")
        self._order_logger = OrderLogger(log_dir)
        self._thread_manager = ThreadManager()
        self._live_order_file = "data/live_order.json"

        self._config_manager = ConfigManager()
        self._reload_trading_config(self._config_manager.get())
        self._config_manager.register_watcher(self._reload_trading_config)

        self.subscribe_to_event(EntrySignal, self.on_entry_signal)
        self.subscribe_to_event(QuoteEvent, self._on_ltp_update)
        self.subscribe_to_event(CandleGenerated, self._handle_update_candle)
        self._logger.info("OrderManager initialized")

    def _reload_trading_config(self, config: dict) -> None:
        """Cache config values; called on init and hot-reload. New values apply to the next order."""
        self._trail          = float(config.get('trail', 0.03))
        self._loss_stop_low  = float(config.get('loss_stop_low', 0.96))
        self._loss_stop_high = float(config.get('loss_stop_high', 1.06))
        self._quantities     = config.get('quantities', {})
        self._default_qty    = int(config.get('default_quantity', 75))

    def _handle_entry_signal(self, event: EntrySignal):
        symbol = event.symbol
        side = event.direction

        existing = self._orders.get(symbol)
        if existing and existing.state == ORDERSTATE.OPEN:
            if existing.get_side() != side:
                self._logger.info(f"Direction switch for {symbol}: {existing.get_side()} → {side}")
                self._execute_order(existing, order_type='SWITCH')
            else:
                self._logger.info(f"Duplicate entry signal for {symbol} ({side}), ignoring")
                return

        quantity = int(self._quantities.get(symbol, self._default_qty))
        try:
            order = OrderObject(
                name=symbol,
                instrument=event.symbol,
                trail=self._trail,
                side=side,
                quantity=quantity,
                candle=event.candle,
                loss_stop_low=self._loss_stop_low,
                loss_stop_high=self._loss_stop_high,
            )
        except Exception as e:
            self._logger.error(f"Failed to create OrderObject for {symbol}: {e}")
            return

        self._orders[symbol] = order
        self._execute_order(order, order_type="ENTRY")
        self._order_logger.log_entry(order)
        self._write_live_order_data()

    def _execute_order(self, order: OrderObject, order_type: str):
        side = order.get_side()
        if order_type in ('EXIT', 'SWITCH'):
            side = "SELL" if side == "BUY" else "BUY"
            order.state = ORDERSTATE.CLOSE

        self.publish_event(OrderEvent(
            timestamp=order._timestamp,
            order_id=order.id,
            instrument=order.get_instrument(),
            side=side,
            price=order.ltp if order.ltp != 0 else order.const_entry_price,
            strategy="tradecore",
            type=order_type,
            candle=order.current_candle,
            meta_info=None,
            source=self.__class__.__name__,
        ))
        self._cleanup_closed_orders(order.get_instrument())

    def _handle_update_candle(self, event: CandleGenerated):
        order = self._orders.get(event.symbol)
        if order and order.state == ORDERSTATE.OPEN:
            order.set_current_candle(event)

    def _on_ltp_update(self, event: QuoteEvent):
        order = self._orders.get(event.instrument)
        if order and order.state == ORDERSTATE.OPEN:
            self.update_ltp(event)

    def update_ltp(self, event: QuoteEvent):
        order = self._orders.get(event.instrument)
        if not order or order.state != ORDERSTATE.OPEN:
            return

        exit_info = order.set_ltp(event.ltp, event.timestamp)

        if order.state == ORDERSTATE.CLOSE:
            reason     = exit_info.get('exit_reason', 'UNKNOWN') if isinstance(exit_info, dict) else 'UNKNOWN'
            exit_price = exit_info.get('exit_price', event.ltp)   if isinstance(exit_info, dict) else event.ltp
            self._order_logger.log_exit(order, reason, exit_price)
            del self._orders[event.instrument]
            self._logger.info(f"Order closed: {event.instrument}  reason={reason}")

        self._write_live_order_data()

    def update_candle(self, symbol: str, candle: CandleGenerated):
        if symbol in self._orders:
            self._orders[symbol].set_current_candle(candle)

    def has_order(self, symbol: str) -> bool:
        return symbol in self._orders

    def get_order(self, symbol: str):
        return self._orders.get(symbol)

    def all_orders(self):
        return self._orders.values()

    def on_entry_signal(self, event: EntrySignal):
        try:
            self._handle_entry_signal(event)
        except Exception as e:
            self._logger.error(f"Error handling entry signal: {e}")

    def _write_live_order_data(self):
        try:
            os.makedirs("data", exist_ok=True)
            live_orders = []
            for symbol, order in self._orders.items():
                live_orders.append({
                    "id":                       order.id,
                    "symbol":                   symbol,
                    "instrument":               order.get_instrument(),
                    "side":                     order.get_side(),
                    "total_quantity":           order.quantity,
                    "entry_price":              basic.round4(order.const_entry_price),
                    "net_stop":                 order.net_zero_stop,
                    "zero_stop":                order.zero_stop,
                    "loss_stop":                order.loss_stop,
                    "current_ltp":              order.ltp,
                    "current_profit_percentage": order.get_current_profit_percentage(),
                    "current_profit":           order.get_current_profit(),
                    "trigger":                  order.trigger * 100,
                    "retreat":                  order.get_retreat(),
                    "max_move_percentage":      order.get_max_move_percentage(),
                    "min_move_percentage":      order.get_min_move_percentage(),
                    "entry_time":               order.get_entry_time().isoformat() if order.get_entry_time() else None,
                    "last_update":              datetime.now().isoformat(),
                })
            tmp = self._live_order_file + ".tmp"
            with open(tmp, 'w') as f:
                json.dump({"timestamp": datetime.now().isoformat(), "total_orders": len(live_orders), "orders": live_orders}, f, indent=2)
            os.replace(tmp, self._live_order_file)
        except Exception as e:
            self._logger.error(f"Error writing live order data: {e}")

    def _cleanup_closed_orders(self, symbol: str):
        order = self._orders.get(symbol)
        if order and order.state == ORDERSTATE.CLOSE:
            del self._orders[symbol]
            self._logger.info(f"Removed closed order for {symbol}")

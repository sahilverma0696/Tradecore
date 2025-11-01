import asyncio
import json
import csv
import aiohttp
from datetime import datetime, time
from collections import defaultdict


# ============================================================
# ---------------- VWAP CALCULATOR ----------------------------
# ============================================================

class IncrementalVWAP:
    def __init__(self):
        self.cum_tp_vol = 0.0
        self.cum_vol = 0.0
        self.vwap = None

    def update(self, high, low, close, volume):
        typical_price = (high + low + close) / 3
        tp_vol = typical_price * volume
        self.cum_tp_vol += tp_vol
        self.cum_vol += volume
        if self.cum_vol > 0:
            self.vwap = round(self.cum_tp_vol / self.cum_vol, 2)
        return self.vwap

    def update_from_quote(self, ltp, volume):
        tp_vol = ltp * volume
        self.cum_tp_vol += tp_vol
        self.cum_vol += volume
        if self.cum_vol > 0:
            self.vwap = round(self.cum_tp_vol / self.cum_vol, 2)
        return self.vwap


# ============================================================
# ---------------- BINANCE STREAMER ---------------------------
# ============================================================

class BinanceQuoteStreamer:
    """
    Streams Binance trades via WebSocket for BTCUSDT.
    Produces quote dicts with ts, inst, ltp, ltq, etc.
    """
    def __init__(self, symbol="btcusdt"):
        self.symbol = symbol.lower()
        self.quote_handlers = []

    def add_quote_handler(self, handler):
        if callable(handler):
            self.quote_handlers.append(handler)

    async def stream_quotes(self):
        url = f"wss://stream.binance.com:9443/ws/{self.symbol}@trade"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                print(f"Connected to Binance trade stream for {self.symbol.upper()}")
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        ts_dt = datetime.fromtimestamp(data["T"] / 1000.0)
                        quote = {
                            "ts": ts_dt,
                            "inst": self.symbol.upper(),
                            "name": self.symbol.upper(),
                            "ltp": float(data["p"]),
                            "ltq": float(data["q"]),
                            "cp": 0  # placeholder
                        }
                        for handler in self.quote_handlers:
                            handler(quote)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"Error: {msg}")
                        break


# ============================================================
# ---------------- CANDLE MAKER -------------------------------
# ============================================================

class CandleMaker:
    def __init__(self, on_candle_ready, candle_interval_min=1):
        self.on_candle_ready = on_candle_ready
        self.current_candles = {}
        self.interval = candle_interval_min

    def handle_quote(self, quote):
        ts = quote['ts']
        inst = quote['inst']
        ltp = quote['ltp']
        volume = quote['ltq']

        candle_time = ts.replace(second=0, microsecond=0)
        minute = candle_time.minute - (candle_time.minute % self.interval)
        candle_time = candle_time.replace(minute=minute)

        candle = self.current_candles.get(inst)
        if candle is None or candle['timestamp'] != candle_time:
            if candle:
                self.on_candle_ready(inst, candle)
            candle = {
                'timestamp': candle_time,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': volume
            }
        else:
            candle['high'] = max(candle['high'], ltp)
            candle['low'] = min(candle['low'], ltp)
            candle['close'] = ltp
            candle['volume'] += volume

        self.current_candles[inst] = candle


# ============================================================
# ---------------- STRATEGY + RETRIEVAL EXIT ------------------
# ============================================================

class VWAPStrategyLive:
    def __init__(self, order_manager):
        self.vwaps = defaultdict(IncrementalVWAP)
        self.order_manager = order_manager

    def on_candle(self, inst, candle):
        vwap = self.vwaps[inst].update(
            candle['high'], candle['low'], candle['close'], candle['volume']
        )
        open_price = candle['open']
        close_price = candle['close']
        order = self.order_manager.get_order(inst)

        if order is None:
            if open_price < vwap and close_price > vwap:
                print(f"ENTRY SIGNAL BUY | Open={open_price} Close={close_price} VWAP={vwap}")
                self.order_manager.create_order(inst, 'BUY', close_price, candle['timestamp'], vwap)
            elif open_price > vwap and close_price < vwap:
                print(f"ENTRY SIGNAL SELL | Open={open_price} Close={close_price} VWAP={vwap}")
                self.order_manager.create_order(inst, 'SELL', close_price, candle['timestamp'], vwap)
        else:
            self.order_manager.check_retrieval_trigger_exit(inst, close_price)

    def on_quote(self, quote):
        inst = quote['inst']
        ltp = quote['ltp']
        vol = quote['ltq']
        vwap = self.vwaps[inst].update_from_quote(ltp, vol)
        self.order_manager.update_live_price(inst, ltp, vwap, quote['ts'])


# ============================================================
# ---------------- ORDER MANAGEMENT ---------------------------
# ============================================================

class OrderManager:
    def __init__(self, csv_file='trades.csv'):
        self.orders = {}
        self.csv_file = csv_file
        self.count = 0
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'inst', 'side', 'entry_time', 'entry_price', 'exit_time', 'exit_price', 'exit_type', 'pnl', 'pnl_pct'
            ])

    def create_order(self, inst, side, price, timestamp, vwap):
        print(f"ENTER {side} {inst} @ {price} on {timestamp}")
        self.orders[inst] = {
            'side': side,
            'entry_price': price,
            'entry_time': timestamp,
            'max_price': price,
            'min_price': price,
            'ltp': price,
            'trigger': 0.5,  # 0.5% retrace trigger
            'vwap': vwap,
            'state': 'OPEN'
        }

    def get_order(self, inst):
        return self.orders.get(inst)

    def update_live_price(self, inst, ltp, vwap, ts):
        order = self.orders.get(inst)
        if not order:
            return
        order['ltp'] = ltp
        order['vwap'] = vwap
        if order['side'] == "BUY":
            order['max_price'] = max(order['max_price'], ltp)
        else:
            order['min_price'] = min(order['min_price'], ltp)

    def check_retrieval_trigger_exit(self, inst, ltp):
        order = self.orders.get(inst)
        if not order or order['state'] != "OPEN":
            return

        trigger = order['trigger']
        side = order['side']
        max_price = order['max_price']
        min_price = order['min_price']

        if side == "BUY":
            difference = max_price - ltp
            diff_pct = round((difference / max_price) * 100, 4)
            opposite_move = ltp < max_price
        else:
            difference = ltp - min_price
            diff_pct = round((difference / min_price) * 100, 4)
            opposite_move = ltp > min_price

        print(f"[{side}] ltp={ltp} max={max_price} min={min_price} diff%={diff_pct} trigger={trigger}")

        if opposite_move and diff_pct >= trigger:
            self.count += 1
            print(f"RETRIEVAL EXIT TRIGGERED #{self.count} ({side}) @ {ltp}")
            order['state'] = "CLOSED"
            self.record_trade(inst, side, order['entry_time'], order['entry_price'], datetime.utcnow(), ltp, 'RETRIEVAL')

    def record_trade(self, inst, side, entry_time, entry_price, exit_time, exit_price, exit_type):
        pnl = (exit_price - entry_price) if side == 'BUY' else (entry_price - exit_price)
        pnl_pct = (pnl / entry_price) * 100
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([inst, side, entry_time, entry_price, exit_time, exit_price, exit_type, round(pnl, 2), f"{pnl_pct:.2f}%"])
        del self.orders[inst]


# ============================================================
# ---------------- EXECUTION DRIVER ---------------------------
# ============================================================

class Execution:
    def __init__(self, symbol="BTCUSDT"):
        self.symbol = symbol
        self.order_manager = OrderManager("binance_trades.csv")
        self.strategy = VWAPStrategyLive(self.order_manager)
        self.candle_maker = CandleMaker(on_candle_ready=self.strategy.on_candle)
        self.streamer = BinanceQuoteStreamer(symbol)
        self.streamer.add_quote_handler(self.candle_maker.handle_quote)
        self.streamer.add_quote_handler(self.strategy.on_quote)

    async def run(self):
        await self.streamer.stream_quotes()


# ============================================================
# ---------------- MAIN --------------------------------------
# ============================================================

if __name__ == "__main__":
    execution = Execution("BTCUSDT")
    asyncio.run(execution.run())

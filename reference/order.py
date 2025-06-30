import json
from collections import defaultdict
from quotes import QuoteStreamer
from candle import CandleMaker
import time
import csv



import csv
from datetime import datetime

class OrderManager:
    def __init__(self, instruments_json, csv_file='trades.csv'):
        # instruments_json: list of dicts with keys: symbol, name, step, trail
        self.orders = {}  # key: inst name -> order info
        self.instruments = {item['name']: item for item in instruments_json}
        self.csv_file = csv_file
        # Initialize CSV file with header
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'inst', 'name', 'side', 'entry_time', 'entry_price',
                'entry_open', 'entry_close', 'entry_vwap',
                'exit_time', 'exit_price', 'exit_type',
                'pnl', 'pnl_pct'
            ])
        self.executor = None

    def register_executor(self, func):
        self.executor = func

    def _update_vwap(self, order, ltp, volume):
        # incremental VWAP update
        tp_vol = ltp * volume
        order['cum_tp_vol'] += tp_vol
        order['cum_vol'] += volume
        if order['cum_vol'] > 0:
            order['vwap'] = round(order['cum_tp_vol'] / order['cum_vol'], 5)
        else:
            order['vwap'] = None

    def on_quote(self, quote):
        """
        Handle incoming quote:
        quote dict: {ts, inst, name, ltp, ltq, cp}
        Update ltp, update vwap incrementally, check risk exit.
        """
        name = quote['name']
        ltp = quote['ltp']
        vol = quote['ltq']
        ts = quote['ts']

        # If instrument known
        if name not in self.instruments:
            return

        # Get or init order container for this instrument
        order = self.orders.get(name)
        if order is None:
            # No active order, create order data container to track vwap and ltp
            self.orders[name] = {
                'side': None,
                'entry_price': None,
                'entry_time': None,
                'steps': self.instruments[name]['step'],
                'trails': self.instruments[name]['trail'],
                'position_size': 1.0,
                'filled_steps': set(),
                'max_profit_price': None,
                'min_profit_price': None,
                'cum_tp_vol': 0.0,
                'cum_vol': 0.0,
                'vwap': None,
                'ltp': ltp,
                'last_candle': None,
                'current_step_idx': 0,
                'current_trail': self.instruments[name]['trail'][0],
                'entry_open': None,
                'entry_close': None
            }
            order = self.orders[name]
        else:
            order['ltp'] = ltp

        # Update VWAP incrementally
        self._update_vwap(order, ltp, vol)

        # Risk exit check if order is active
        if order['side'] is not None:
            side = order['side']
            vwap = order['vwap']
            if vwap is None:
                return
            # Risk exit: BUY exit if ltp < vwap, SELL exit if ltp > vwap
            if (side == 'BUY' and ltp < vwap) or (side == 'SELL' and ltp > vwap):
                self._exit_order(name, ltp, ts, 'RISK')

    def on_candle(self, name, candle):
        """
        Handle new 5-min candle:
        candle dict: {timestamp, open, high, low, close, volume, name}
        Entry and exit decisions based on candle and vwap.
        """
        if name not in self.instruments:
            return

        order = self.orders.get(name)
        if order is None:
            # Initialize tracking data but no order yet
            self.orders[name] = {
                'side': None,
                'entry_price': None,
                'entry_time': None,
                'steps': self.instruments[name]['step'],
                'trails': self.instruments[name]['trail'],
                'position_size': 1.0,
                'filled_steps': set(),
                'max_profit_price': None,
                'min_profit_price': None,
                'cum_tp_vol': 0.0,
                'cum_vol': 0.0,
                'vwap': None,
                'ltp': None,
                'last_candle': candle,
                'current_step_idx': 0,
                'current_trail': self.instruments[name]['trail'][0],
                'entry_open': None,
                'entry_close': None
            }
            order = self.orders[name]

        order['last_candle'] = candle

        vwap = order['vwap']
        if vwap is None:
            # Can't do anything without VWAP calculated yet
            return

        open_price = candle['open']
        close_price = candle['close']

        # If no position, check entry signals:
        if order['side'] is None:
            # BUY entry: open < vwap and close > vwap
            if open_price < vwap and close_price > vwap:
                self._enter_order(name, 'BUY', close_price, candle)
            # SELL entry: open > vwap and close < vwap
            elif open_price > vwap and close_price < vwap:
                self._enter_order(name, 'SELL', close_price, candle)

        else:
            # Position active, check step exit, trailing exit, time exit

            side = order['side']
            entry_price = order['entry_price']
            steps = order['steps']
            trails = order['trails']
            step_idx = order['current_step_idx']
            position_size = order['position_size']
            filled = order['filled_steps']

            # Calculate profit ratio
            if side == 'BUY':
                profit_ratio = (close_price - entry_price) / entry_price
            else:
                profit_ratio = (entry_price - close_price) / entry_price

            # Check if we should advance step index due to profit
            while step_idx + 1 < len(steps) and profit_ratio >= steps[step_idx + 1]:
                step_idx += 1
            if step_idx != order['current_step_idx']:
                order['current_step_idx'] = step_idx
                order['current_trail'] = trails[step_idx]

            # Update max/min profit price for trailing exit
            if side == 'BUY':
                if order['max_profit_price'] is None or close_price > order['max_profit_price']:
                    order['max_profit_price'] = close_price
            else:
                if order['min_profit_price'] is None or close_price < order['min_profit_price']:
                    order['min_profit_price'] = close_price

            # Step exit check: if profit passes a step and step not filled, exit full position immediately
            # According to your spec, all exits are 100%
            for i, step_pct in enumerate(steps):
                if step_pct not in filled and profit_ratio >= step_pct:
                    self._exit_order(name, close_price, candle['timestamp'], f'STEP {step_pct*100:.1f}%')
                    return

            # Trailing exit check: if price retraces more than current trail % from peak profit price
            if side == 'BUY' and order['max_profit_price'] is not None:
                retrace = (order['max_profit_price'] - close_price) / order['max_profit_price']
                if retrace >= order['current_trail']:
                    self._exit_order(name, close_price, candle['timestamp'], 'TRAIL')
                    return
            elif side == 'SELL' and order['min_profit_price'] is not None:
                retrace = (close_price - order['min_profit_price']) / order['min_profit_price']
                if retrace >= order['current_trail']:
                    self._exit_order(name, close_price, candle['timestamp'], 'TRAIL')
                    return

            # Time exit: for example close market time (assuming 15:29)
            if candle['timestamp'].time() >= datetime.strptime("15:29", "%H:%M").time():
                self._exit_order(name, close_price, candle['timestamp'], 'TIME')
                return

    def _enter_order(self, name, side, price, candle):
        now = candle['timestamp']
        order = self.orders[name]
        order['side'] = side
        order['entry_price'] = price
        order['entry_time'] = now
        order['filled_steps'] = set()
        order['position_size'] = 1.0
        order['max_profit_price'] = price if side == 'BUY' else None
        order['min_profit_price'] = price if side == 'SELL' else None
        order['current_step_idx'] = 0
        order['current_trail'] = order['trails'][0]
        order['entry_open'] = candle['open']
        order['entry_close'] = candle['close']

        # Reset VWAP accumulators for fresh tracking on entry
        order['cum_tp_vol'] = 0.0
        order['cum_vol'] = 0.0
        order['vwap'] = None

        msg = f"ENTRY {side} {name} @ {price} on {now}"
        if self.executor:
            self.executor({'type': 'ENTRY', 'symbol': name, 'side': side, 'price': price, 'time': now})

    def _exit_order(self, name, price, exit_time, exit_type):
        order = self.orders.get(name)
        if not order or order['side'] is None:
            return  # no active order

        side = order['side']
        entry_price = order['entry_price']
        entry_time = order['entry_time']
        pnl = (price - entry_price) if side == 'BUY' else (entry_price - price)
        pnl_pct = (pnl / entry_price) * 100 if entry_price else 0

        print(f"EXIT {side} {name} @ {price} on {exit_time} ({exit_type}) PnL: {pnl:.2f} ({pnl_pct:.2f}%)")

        # Write trade record
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                name,
                self.instruments[name]['name'],
                side,
                entry_time,
                entry_price,
                order['entry_open'],
                order['entry_close'],
                round(order['vwap'], 5) if order['vwap'] else '',
                exit_time,
                price,
                exit_type,
                round(pnl, 2),
                f"{pnl_pct:.2f}%"
            ])

        if self.executor:
            self.executor({'type': 'EXIT', 'symbol': name, 'side': side, 'price': price, 'time': exit_time, 'exit_type': exit_type, 'pnl': pnl, 'pnl_pct': pnl_pct})

        # Clear order data
        self.orders[name] = {
            'side': None,
            'entry_price': None,
            'entry_time': None,
            'steps': self.instruments[name]['step'],
            'trails': self.instruments[name]['trail'],
            'position_size': 1.0,
            'filled_steps': set(),
            'max_profit_price': None,
            'min_profit_price': None,
            'cum_tp_vol': 0.0,
            'cum_vol': 0.0,
            'vwap': None,
            'ltp': None,
            'last_candle': None,
            'current_step_idx': 0,
            'current_trail': self.instruments[name]['trail'][0],
            'entry_open': None,
            'entry_close': None
        }

# --- Optional Executor for Logging ---
def record_trade(trade_info):
    print("LOG:", trade_info)


def main():
    with open("instruments.json", "r") as f:
        instruments_data = json.load(f)  # This should be a list of dicts

    order_mgr = OrderManager(instruments_data)

    order_mgr.register_executor(record_trade)


    candle_maker = CandleMaker(on_candle_ready=order_mgr.on_candle)

    streamer = QuoteStreamer(
        db_file="../../data/upstox/upstox_ltp.db",
        table_name="quotes_20250625",
        date_filter="2025-06-25",
        name_filter="NIFTY 25000 CE 26 JUN 25"
    )

    streamer.register_handler(candle_maker.handle_quote)
    streamer.register_handler(order_mgr.on_quote)


    streamer.stream_quotes()



if __name__ == "__main__":
    main()
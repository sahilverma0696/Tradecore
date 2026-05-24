import os
import time
from datetime import datetime
from typing import Dict, List
import curses
import json

from src.logger_factory import get_logger


class TradingDashboard:
    """Real-time CLI dashboard reading from IPC files."""

    def __init__(self):
        self._logger = get_logger("TradingDashboard", console_output=True)

        self.recent_quotes: Dict[str, dict] = {}
        self.recent_candles: Dict[str, dict] = {}
        self.live_orders: List[dict] = []
        self.start_time = datetime.now()
        self.running = False

        self._quote_file = "data/live_quotes.json"
        self._candle_file = "data/live_candles.json"
        self._order_file = "data/live_order.json"

    # ── IPC readers ──────────────────────────────────────────────────────────

    def _read_live_quotes(self):
        try:
            if os.path.exists(self._quote_file):
                with open(self._quote_file, 'r') as f:
                    data = json.load(f)
                for symbol, q in data.items():
                    try:
                        ts = datetime.fromisoformat(q.get('timestamp', ''))
                    except Exception:
                        ts = datetime.now()
                    self.recent_quotes[symbol] = {
                        'ltp': q.get('ltp', 0.0),
                        'ltq': q.get('ltq', 0.0),
                        'source': q.get('source', ''),
                        'timestamp': ts,
                    }
        except Exception as e:
            self._logger.debug(f"quotes read error: {e}")

    def _read_live_candles(self):
        try:
            if os.path.exists(self._candle_file):
                with open(self._candle_file, 'r') as f:
                    data = json.load(f)
                for symbol, c in data.items():
                    try:
                        ts = datetime.fromisoformat(c.get('timestamp', ''))
                    except Exception:
                        ts = datetime.now()
                    self.recent_candles[symbol] = {**c, 'timestamp': ts}
        except Exception as e:
            self._logger.debug(f"candles read error: {e}")

    def _read_live_orders(self):
        try:
            if os.path.exists(self._order_file):
                with open(self._order_file, 'r') as f:
                    data = json.load(f)
                self.live_orders = data.get('orders', [])
        except Exception as e:
            self._logger.debug(f"orders read error: {e}")

    def _refresh_all(self):
        self._read_live_quotes()
        self._read_live_candles()
        self._read_live_orders()

    # ── Curses dashboard ─────────────────────────────────────────────────────

    def start_curses_dashboard(self):
        try:
            curses.wrapper(self._curses_main)
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False

    def _curses_main(self, stdscr):
        self.running = True
        curses.curs_set(0)
        stdscr.nodelay(1)
        stdscr.timeout(1000)

        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # profit / live
        curses.init_pair(2, curses.COLOR_RED, -1)     # loss / stale
        curses.init_pair(3, curses.COLOR_YELLOW, -1)  # warning / neutral
        curses.init_pair(4, curses.COLOR_CYAN, -1)    # info
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)  # header

        while self.running:
            try:
                self._refresh_all()
                stdscr.erase()
                self._curses_draw(stdscr)
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord('q'), ord('Q')):
                    break
            except Exception as e:
                self._logger.error(f"draw error: {e}")
                time.sleep(1)

    def _safe_addstr(self, stdscr, row, col, text, attr=0):
        height, width = stdscr.getmaxyx()
        if row < 0 or row >= height - 1:
            return
        text = text[:width - col - 1]
        try:
            stdscr.addstr(row, col, text, attr)
        except curses.error:
            pass

    def _curses_draw(self, stdscr):
        height, width = stdscr.getmaxyx()
        G = curses.color_pair(1)
        R = curses.color_pair(2)
        Y = curses.color_pair(3)
        C = curses.color_pair(4)
        H = curses.color_pair(5)
        B = curses.A_BOLD

        row = 0

        # ── header ──
        title = f" Tradecore Dashboard  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  [q] quit "
        self._safe_addstr(stdscr, row, 0, title.ljust(width), H | B)
        row += 1

        uptime = str(datetime.now() - self.start_time).split('.')[0]
        self._safe_addstr(stdscr, row, 0,
            f"Uptime: {uptime}  |  Quotes: {len(self.recent_quotes)}  "
            f"|  Candles: {len(self.recent_candles)}  |  Orders: {len(self.live_orders)}", C)
        row += 2

        # ── live quotes ──
        self._safe_addstr(stdscr, row, 0, "LIVE QUOTES", B)
        row += 1
        hdr = f"{'Symbol':<14} {'LTP':>10}  {'LTQ':>10}  {'Source':<12} {'Age':>6}  Status"
        self._safe_addstr(stdscr, row, 0, hdr, curses.A_UNDERLINE)
        row += 1

        if self.recent_quotes:
            for sym, q in self.recent_quotes.items():
                if row >= height - 2:
                    break
                age = (datetime.now() - q['timestamp']).total_seconds()
                color, status = (G, "LIVE") if age < 5 else (Y, "OK") if age < 30 else (R, "STALE")
                line = (f"{sym:<14} {q['ltp']:>10.4f}  {q['ltq']:>10.4f}  "
                        f"{q['source'][:11]:<12} {age:>5.0f}s  {status}")
                self._safe_addstr(stdscr, row, 0, line, color)
                row += 1
        else:
            self._safe_addstr(stdscr, row, 0, "  no quotes — is main system running?", R)
            row += 1
        row += 1

        # ── orders ──
        self._safe_addstr(stdscr, row, 0, "ORDERS", B)
        row += 1
        hdr = (f"{'Symbol':<14} {'Side':<4}  {'Entry':>9}  {'LTP':>9}  "
               f"{'P&L':>9}  {'P&L%':>6}  {'Max%':>6}  {'Ret%':>6}  {'Qty':>5}")
        self._safe_addstr(stdscr, row, 0, hdr, curses.A_UNDERLINE)
        row += 1

        if self.live_orders:
            for o in self.live_orders:
                if row >= height - 4:
                    break
                pnl = o.get('current_profit', 0.0)
                pnl_pct = o.get('current_profit_percentage', 0.0)
                color = G if pnl_pct >= 0 else R
                line1 = (f"{o.get('symbol',''):<14} {o.get('side',''):<4}  "
                         f"{o.get('entry_price',0):>9.4f}  {o.get('current_ltp',0):>9.4f}  "
                         f"{pnl:>+9.2f}  {pnl_pct:>+6.2f}%  "
                         f"{o.get('max_move_percentage',0):>+6.2f}%  "
                         f"{o.get('retreat',0):>6.2f}%  "
                         f"{str(o.get('total_quantity',''))!s:>5}")
                self._safe_addstr(stdscr, row, 0, line1, color)
                row += 1

                # stops line
                loss = o.get('loss_stop', 0.0)
                zero = o.get('zero_stop', 0.0)
                net  = o.get('net_stop', 0.0)
                trig = o.get('trigger', 0.0)
                min_pct = o.get('min_move_percentage', 0.0)
                stops = (f"{'':>18} Loss:{loss:<9.4f}  Zero:{zero:<9.4f}  "
                         f"Net:{net:<9.4f}  Trig:{trig:.1f}%  Min%:{min_pct:+.2f}%")
                self._safe_addstr(stdscr, row, 0, stops, Y)
                row += 1
        else:
            self._safe_addstr(stdscr, row, 0, "  no open orders", Y)
            row += 1
        row += 1

        # ── recent candles ──
        if self.recent_candles and row < height - 4:
            self._safe_addstr(stdscr, row, 0, "LAST CANDLES", B)
            row += 1
            hdr = f"{'Symbol':<14} {'TF':>3}  {'Open':>9}  {'High':>9}  {'Low':>9}  {'Close':>9}  {'VWAP':>9}  {'Volume':>10}"
            self._safe_addstr(stdscr, row, 0, hdr, curses.A_UNDERLINE)
            row += 1
            for sym, c in self.recent_candles.items():
                if row >= height - 2:
                    break
                line = (f"{sym:<14} {c.get('timeframe','')!s:>3}  "
                        f"{c.get('open',0):>9.4f}  {c.get('high',0):>9.4f}  "
                        f"{c.get('low',0):>9.4f}  {c.get('close',0):>9.4f}  "
                        f"{c.get('vwap',0):>9.4f}  {c.get('volume',0):>10.2f}")
                self._safe_addstr(stdscr, row, 0, line, C)
                row += 1

    # ── Simple (no-curses) dashboard ─────────────────────────────────────────

    def start_simple_dashboard(self):
        self.running = True
        print("Tradecore Trading Dashboard — Ctrl+C to exit\n")
        try:
            while self.running:
                self._print_simple_dashboard()
                time.sleep(2)
        except KeyboardInterrupt:
            self.running = False

    def _print_simple_dashboard(self):
        self._refresh_all()
        os.system('clear' if os.name == 'posix' else 'cls')

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        uptime = str(datetime.now() - self.start_time).split('.')[0]
        print("=" * 90)
        print(f"  Tradecore Dashboard  {now}  |  Uptime: {uptime}")
        print("=" * 90)

        # ── quotes ──
        print("\nLIVE QUOTES")
        print(f"  {'Symbol':<14} {'LTP':>10}  {'LTQ':>10}  {'Source':<12} {'Age':>6}  Status")
        print("  " + "-" * 70)
        if self.recent_quotes:
            for sym, q in self.recent_quotes.items():
                age = (datetime.now() - q['timestamp']).total_seconds()
                status = "LIVE" if age < 5 else "OK" if age < 30 else "STALE"
                print(f"  {sym:<14} {q['ltp']:>10.4f}  {q['ltq']:>10.4f}  "
                      f"{q['source'][:11]:<12} {age:>5.0f}s  {status}")
        else:
            print("  (no quotes — is main system running?)")

        # ── orders ──
        print("\nORDERS")
        if self.live_orders:
            for o in self.live_orders:
                pnl     = o.get('current_profit', 0.0)
                pnl_pct = o.get('current_profit_percentage', 0.0)
                sign    = '+' if pnl_pct >= 0 else ''
                print(f"  {'─'*70}")
                print(f"  {o.get('symbol','')}  |  {o.get('side','')}  "
                      f"|  Entry: {o.get('entry_price',0):.4f}  "
                      f"|  LTP: {o.get('current_ltp',0):.4f}  "
                      f"|  Qty: {o.get('total_quantity','')}")
                print(f"  {'':>2}P&L: {sign}{pnl:.2f}  ({sign}{pnl_pct:.2f}%)  "
                      f"|  Max: {o.get('max_move_percentage',0):+.2f}%  "
                      f"|  Min: {o.get('min_move_percentage',0):+.2f}%  "
                      f"|  Retreat: {o.get('retreat',0):.2f}%  "
                      f"|  Trigger: {o.get('trigger',0):.1f}%")
                print(f"  {'':>2}Loss stop: {o.get('loss_stop',0):.4f}  "
                      f"|  Zero stop: {o.get('zero_stop',0):.4f}  "
                      f"|  Net stop: {o.get('net_stop',0):.4f}")
                entry_time = o.get('entry_time', '')
                last_upd   = o.get('last_update', '')
                print(f"  {'':>2}Entry time: {entry_time}  |  Last update: {last_upd}")
            print(f"  {'─'*70}")
        else:
            print("  (no open orders)")

        # ── candles ──
        if self.recent_candles:
            print("\nLAST CANDLES")
            print(f"  {'Symbol':<14} {'TF':>3}  {'Open':>9}  {'High':>9}  {'Low':>9}  {'Close':>9}  {'VWAP':>9}  {'Volume':>10}")
            print("  " + "-" * 80)
            for sym, c in self.recent_candles.items():
                print(f"  {sym:<14} {c.get('timeframe','')!s:>3}  "
                      f"{c.get('open',0):>9.4f}  {c.get('high',0):>9.4f}  "
                      f"{c.get('low',0):>9.4f}  {c.get('close',0):>9.4f}  "
                      f"{c.get('vwap',0):>9.4f}  {c.get('volume',0):>10.2f}")

        print("\n" + "=" * 90)
        print("  Ctrl+C to exit")


def start_dashboard(use_curses=True):
    dashboard = TradingDashboard()
    if use_curses:
        try:
            dashboard.start_curses_dashboard()
        except Exception:
            dashboard.start_simple_dashboard()
    else:
        dashboard.start_simple_dashboard()
    return dashboard


if __name__ == "__main__":
    start_dashboard()

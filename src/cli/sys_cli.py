"""
System CLI — event bus wiring, live event stream, session stats.
Shows SYSTEM information, not order/trade information (that's in `make cli`).
"""
import os
import time
import json
import curses
from datetime import datetime
from typing import List, Dict

from src.logger_factory import get_logger

_SYSTEM_FILE = "data/live_system.json"
_EVENTS_LOG  = "data/live_events_log.json"

# Canonical flow order for display
_FLOW_ORDER = [
    "QuoteEvent",
    "CandleGenerated",
    "EntrySignal",
    "OrderEvent",
    "FullQuoteEvent",
]

# Color per event type
_TYPE_COLOR = {
    "QuoteEvent":      4,   # cyan
    "CandleGenerated": 3,   # yellow
    "EntrySignal":     1,   # green
    "OrderEvent":      2,   # red

    "FullQuoteEvent":  4,
}


def _read_json(path):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return None


class SysDashboard:
    def __init__(self):
        self._logger = get_logger("SysCLI", console_output=False)
        self.running = False
        self.cli_start = datetime.now()

    def start(self):
        try:
            curses.wrapper(self._main)
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False

    def _main(self, stdscr):
        self.running = True
        curses.curs_set(0)
        stdscr.nodelay(1)
        stdscr.timeout(500)

        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN,  -1)
        curses.init_pair(2, curses.COLOR_RED,    -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_CYAN,   -1)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)

        while self.running:
            try:
                stdscr.erase()
                self._draw(stdscr)
                stdscr.refresh()
                if stdscr.getch() in (ord('q'), ord('Q')):
                    break
            except Exception as e:
                self._logger.error(f"draw: {e}")
                time.sleep(1)

    def _safe(self, stdscr, row, col, text, attr=0):
        h, w = stdscr.getmaxyx()
        if row < 0 or row >= h - 1:
            return
        try:
            stdscr.addstr(row, col, str(text)[:w - col - 1], attr)
        except curses.error:
            pass

    # ── Main draw ────────────────────────────────────────────────────────────

    def _draw(self, stdscr):
        h, w = stdscr.getmaxyx()
        B = curses.A_BOLD
        H = curses.color_pair(5)
        Y = curses.color_pair(3)
        C = curses.color_pair(4)

        system  = _read_json(_SYSTEM_FILE) or {}
        events  = _read_json(_EVENTS_LOG)  or []

        row = 0

        # ── header ───────────────────────────────────────────────────────
        session_start = system.get("session_start", "")
        streamer  = system.get("streamer", "?")
        executor  = system.get("executor", "?")
        cli_up    = str(datetime.now() - self.cli_start).split('.')[0]
        sys_up    = ""
        if session_start:
            try:
                sys_up = str(datetime.now() - datetime.fromisoformat(session_start)).split('.')[0]
            except Exception:
                pass

        title = (f" Tradecore System Monitor  {datetime.now().strftime('%H:%M:%S')}  "
                 f"streamer:{streamer}  executor:{executor}  [q] quit ")
        self._safe(stdscr, row, 0, title.ljust(w), H | B)
        row += 1
        self._safe(stdscr, row, 0,
            f"  System uptime: {sys_up or 'waiting...'}   "
            f"CLI uptime: {cli_up}   "
            f"Events buffered: {len(events)}", C)
        row += 2

        # ── event wiring map ─────────────────────────────────────────────
        self._safe(stdscr, row, 0, "EVENT WIRING", B)
        row += 1

        flows = system.get("event_flows", {})
        # Show in canonical order, then any extras
        ordered = [e for e in _FLOW_ORDER if e in flows]
        ordered += [e for e in flows if e not in ordered]

        if flows:
            for event_type in ordered:
                if row >= h - 2:
                    break
                info  = flows[event_type]
                subs  = info.get("subscribers", [])
                color = curses.color_pair(_TYPE_COLOR.get(event_type, 0))
                # deduplicate while preserving order
                seen, unique = set(), []
                for s in subs:
                    if s not in seen:
                        seen.add(s); unique.append(s)
                arrow = "  →  " + "  +  ".join(unique) if unique else "  (no subscribers)"
                self._safe(stdscr, row, 2, f"{event_type:<22}{arrow}", color)
                row += 1
        else:
            self._safe(stdscr, row, 2, "waiting for system to start...", Y)
            row += 1
        row += 1

        # ── live event stream ─────────────────────────────────────────────
        max_stream_rows = min(18, h - row - 3)
        recent = events[-max_stream_rows:] if max_stream_rows > 0 else []

        self._safe(stdscr, row, 0,
            f"LIVE EVENT STREAM  (last {len(events)} events, showing {len(recent)})", B)
        row += 1
        hdr = f"  {'Time':<10}  {'Type':<22}  {'Source':<20}  Details"
        self._safe(stdscr, row, 0, hdr, curses.A_UNDERLINE)
        row += 1

        for ev in recent:
            if row >= h - 1:
                break
            ev_type = ev.get('type', '?')
            ts_raw  = ev.get('timestamp', '')
            try:
                ts = datetime.fromisoformat(ts_raw).strftime('%H:%M:%S.%f')[:12]
            except Exception:
                ts = ts_raw[:12]

            data   = ev.get('data', {})
            source = str(data.get('source', ''))
            color  = curses.color_pair(_TYPE_COLOR.get(ev_type, 0))
            detail = _event_detail(ev_type, data)

            self._safe(stdscr, row, 0,
                f"  {ts:<12}  {ev_type:<22}  {source:<20}  {detail}", color)
            row += 1


# ── Event detail formatters ───────────────────────────────────────────────────

def _event_detail(ev_type: str, data: dict) -> str:
    if ev_type == "CandleGenerated":
        return (f"{data.get('symbol','')}  tf={data.get('timeframe','')}  "
                f"O={data.get('open',0):.2f}  C={data.get('close',0):.2f}  "
                f"VWAP={data.get('vwap',0):.2f}")
    if ev_type == "EntrySignal":
        return (f"{data.get('symbol','')}  {data.get('direction','')}  "
                f"@ {data.get('price',0):.4f}  strat={data.get('strategy','')}")
    if ev_type == "OrderEvent":
        meta   = data.get('meta_info') or {}
        reason = meta.get('exit_reason', '') if isinstance(meta, dict) else ''
        return (f"{data.get('instrument','')}  {data.get('side','')}  "
                f"@ {data.get('price',0):.4f}  [{data.get('type','')}]"
                + (f"  reason={reason}" if reason else ""))
    symbol = data.get('symbol') or data.get('instrument') or ''
    return f"{symbol}  {str(data)[:60]}"


def start_sys_dashboard():
    SysDashboard().start()


if __name__ == "__main__":
    start_sys_dashboard()

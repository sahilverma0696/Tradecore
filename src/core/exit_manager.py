from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING
from src.core.event_bus.events import OrderEvent
from src.core.event_bus.mixins import Publisher
from src.logger_factory import get_logger
from src.time_control import TimeChecker
from src.config_manager import ConfigManager
from src.global_enum import *
if TYPE_CHECKING:
    from src.core.order_object import OrderObject


class ExitManager(Publisher):
    """
    Peak-retrace-to-last-cleared-level exit logic (mirrors backtest algorithm).

    Exit rules (checked in priority order):
      1. HARD_STOP      — price moves stoploss_pct% against entry  → exit at stop price
      2. MAX_LEVEL      — price reaches max_level_pct from entry   → exit at that level price
      3. RETRACE        — price cleared level N, then retraces to N → exit at level N price
      4. MARKET_CLOSE   — current IST time >= market_close_time    → exit at LTP

    Levels (example step_pct=2, max_level_pct=10): [2, 4, 6, 8, 10]
    A level is "cleared" when the peak move has exceeded it.
    Retrace exit fires when LTP crosses back through the highest cleared level price.
    """

    def __init__(self, name: str = "ExitManager"):
        super().__init__()
        self.logger = get_logger(name)
        self.time = TimeChecker()

        cfg = ConfigManager()
        self._step_pct         = float(cfg.get_value('step_pct')         or 2.0)
        self._max_level_pct    = float(cfg.get_value('max_level_pct')    or 10.0)
        self._stoploss_pct     = float(cfg.get_value('stoploss_pct')     or 2.0)
        self._market_close_time = cfg.get_value('market_close_time')     or '15:30'

        self._levels = self._build_levels()
        self.logger.info(
            f"{name} ready — levels={self._levels}  "
            f"stop={self._stoploss_pct}%  close={self._market_close_time}"
        )

    # ── Level helpers ────────────────────────────────────────────────────────

    def _build_levels(self):
        """[step_pct, 2*step_pct, ..., max_level_pct]"""
        levels, pct = [], self._step_pct
        while pct <= self._max_level_pct + 1e-9:
            levels.append(round(pct, 10))
            pct += self._step_pct
        return levels

    def _level_price(self, entry: float, level_pct: float, side: str) -> float:
        """Exact price corresponding to level_pct% from entry."""
        if side == "BUY":
            return entry * (1 + level_pct / 100)
        return entry * (1 - level_pct / 100)

    def _get_last_cleared_level(self, order: 'OrderObject') -> Optional[float]:
        """
        Highest level % that peak move has exceeded.
        Derived from order's tracked max/min price — no extra state needed.
        """
        entry = order.get_entry_price()
        side  = order.get_side()

        if side == "BUY":
            peak_pct = (order.get_max_price() - entry) / entry * 100
        else:
            peak_pct = (entry - order.get_min_price()) / entry * 100

        cleared = None
        for lvl in self._levels:
            if peak_pct >= lvl:
                cleared = lvl
            else:
                break
        return cleared

    # ── Exit checks — each returns (exit_price, reason) or (None, None) ─────

    def _check_hard_stop(self, order: 'OrderObject') -> Tuple[Optional[float], Optional[str]]:
        entry = order.get_entry_price()
        ltp   = order.get_ltp()
        side  = order.get_side()

        if side == "BUY":
            stop = entry * (1 - self._stoploss_pct / 100)
            if ltp <= stop:
                return stop, "HARD_STOP"
        else:
            stop = entry * (1 + self._stoploss_pct / 100)
            if ltp >= stop:
                return stop, "HARD_STOP"
        return None, None

    def _check_level_exit(self, order: 'OrderObject') -> Tuple[Optional[float], Optional[str]]:
        entry = order.get_entry_price()
        ltp   = order.get_ltp()
        side  = order.get_side()

        if side == "BUY":
            move_pct = (ltp - entry) / entry * 100
        else:
            move_pct = (entry - ltp) / entry * 100

        # 1. MAX level hit — immediate full exit at that level price
        if move_pct >= self._max_level_pct:
            exit_px = self._level_price(entry, self._max_level_pct, side)
            return exit_px, f"MAX_LEVEL_{self._max_level_pct:.0f}pct"

        # 2. Retrace to last cleared level
        last_cleared = self._get_last_cleared_level(order)
        if last_cleared is not None:
            lvl_px  = self._level_price(entry, last_cleared, side)
            retrace = (side == "BUY"  and ltp <= lvl_px) or \
                      (side == "SELL" and ltp >= lvl_px)
            if retrace:
                return lvl_px, f"RETRACE_L{last_cleared:.0f}pct"

        return None, None

    def _check_market_close_exit(self, order: 'OrderObject') -> Tuple[Optional[float], Optional[str]]:
        if self.time.now_ist() >= self._market_close_time:
            return order.get_ltp(), "MARKET_CLOSE"
        return None, None

    # ── Public API ───────────────────────────────────────────────────────────

    def check(self, order: 'OrderObject') -> Optional[bool]:
        """
        Run all exit checks in priority order.
        Publishes OrderEvent and returns True if an exit is triggered, else None.
        """
        exit_px, reason = self._check_hard_stop(order)

        if exit_px is None:
            exit_px, reason = self._check_level_exit(order)

        if exit_px is None:
            exit_px, reason = self._check_market_close_exit(order)

        if exit_px is None:
            return None

        order.state = ORDERSTATE.CLOSE
        self.logger.info(
            f"Exit [{reason}] {order.get_name()}  "
            f"entry={order.get_entry_price():.4f}  exit={exit_px:.4f}  "
            f"ltp={order.get_ltp():.4f}"
        )

        opposite_side = "SELL" if order.const_side == "BUY" else "BUY"
        self.publish_event(OrderEvent(
            order_id=order.id,
            timestamp=order.last_update_time,
            source=self.__class__.__name__,
            instrument=order.const_instrument,
            side=opposite_side,
            price=exit_px,
            strategy='VWAP',
            type='FULL',
            candle=order.current_candle,
            meta_info={'exit_reason': reason, 'exit_price': exit_px},
        ))
        return {'exit_reason': reason, 'exit_price': exit_px}

    def calculate_performance_metrics(self, order_state: Dict[str, Any]) -> Dict[str, float]:
        """Calculate P&L and move metrics from order state dict."""
        entry  = order_state.get('entry_price', 0)
        ltp    = order_state.get('ltp', 0)
        side   = order_state.get('side', '')
        lo     = order_state.get('min_price', 0)
        hi     = order_state.get('max_price', 0)

        if not entry:
            return {'current_profit': 0.0, 'current_profit_percentage': 0.0,
                    'max_move_percentage': 0.0, 'min_move_percentage': 0.0, 'retreat': 0.0}

        if side == "BUY":
            profit     = ltp - entry
            profit_pct = profit / entry * 100
            max_pct    = (hi - entry) / entry * 100
            min_pct    = (lo - entry) / entry * 100
        else:
            profit     = entry - ltp
            profit_pct = profit / entry * 100
            max_pct    = (entry - lo) / entry * 100
            min_pct    = (entry - hi) / entry * 100

        return {
            'current_profit':            profit,
            'current_profit_percentage': profit_pct,
            'max_move_percentage':       max_pct,
            'min_move_percentage':       min_pct,
            'retreat':                   max_pct - profit_pct,
        }

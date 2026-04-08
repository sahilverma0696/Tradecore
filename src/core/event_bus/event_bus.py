import threading
import os
import json
import dataclasses
from collections import deque
from datetime import datetime
from typing import Dict, List, Callable, Type, Any
import traceback

from src.logger_factory import get_logger
from .events import Event


class EventBus:
    """
    Thread-safe singleton pub-sub broker for the trading system.

    Design decisions
    ----------------
    * Subscriber callbacks are invoked OUTSIDE the main lock.
      The lock is held only long enough to snapshot the subscriber list and
      update in-memory state.  This prevents slow callbacks (or callbacks that
      publish their own events) from blocking the entire bus.

    * Event history uses collections.deque(maxlen=N) – O(1) append/trim.

    * IPC files are written atomically via a temp-file + os.replace() so the
      dashboard never reads a half-written file.

    * IPC state is kept in memory dicts; file writes never read back from disk,
      eliminating the read-modify-write race that plagued the original code.

    * QuoteEvents are NOT written to the general live_events.json – they fire
      many times per second and the general file only needs significant events.
    """

    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self._logger = get_logger("EventBus", console_output=True)

        # Subscriptions: class → [callback, ...]
        self._subscribers: Dict[Type[Event], List[Callable]] = {}
        self._sub_lock = threading.RLock()   # guards _subscribers

        # Event history – deque gives O(1) popleft vs O(n) list.pop(0)
        self._history: deque = deque()
        self._max_history: int = 1000
        self._history_lock = threading.Lock()

        # IPC – in-memory state (no disk reads on update)
        self._ipc_enabled = True
        self._ipc_dir = "data"
        self._ipc_event_file = os.path.join(self._ipc_dir, "live_events.json")
        self._quote_file = os.path.join(self._ipc_dir, "live_quotes.json")
        self._candle_file = os.path.join(self._ipc_dir, "live_candles.json")
        os.makedirs(self._ipc_dir, exist_ok=True)

        self._quote_state: Dict[str, dict] = {}    # keyed by instrument
        self._candle_state: Dict[str, dict] = {}   # keyed by symbol
        self._ipc_state_lock = threading.Lock()    # guards both state dicts

        # Lazy ThreadManager reference (avoids circular import at module load)
        self._thread_manager = None
        self._tm_init_lock = threading.Lock()

        self._initialized = True
        self._logger.info("EventBus ready")

    # ------------------------------------------------------------------
    # ThreadManager – lazy, thread-safe
    # ------------------------------------------------------------------

    def _get_thread_manager(self):
        """Return ThreadManager singleton, initialising the reference once."""
        if self._thread_manager is not None:
            return self._thread_manager

        with self._tm_init_lock:
            if self._thread_manager is not None:   # double-checked under lock
                return self._thread_manager
            try:
                from src.core.thread_manager import ThreadManager, ThreadPoolType
                self._thread_manager = ThreadManager()
                self._ThreadPoolType = ThreadPoolType
            except ImportError:
                self._logger.warning("ThreadManager not available – IPC writes will be synchronous")
                self._thread_manager = False   # sentinel: don't retry
            return self._thread_manager

    # ------------------------------------------------------------------
    # Subscribe / unsubscribe
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: Type[Event],
        callback: Callable[[Event], None],
        subscriber_name: str = None,
    ) -> None:
        with self._sub_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

        name = subscriber_name or getattr(callback, "__qualname__", "unknown")
        self._logger.info(f"{name} subscribed to {event_type.__name__}")

    def unsubscribe(
        self, event_type: Type[Event], callback: Callable[[Event], None]
    ) -> None:
        with self._sub_lock:
            bucket = self._subscribers.get(event_type)
            if bucket and callback in bucket:
                bucket.remove(callback)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """
        Broadcast event to all subscribers.

        The subscriber list is snapshot-copied under the lock so the lock is
        released before any callback executes.  This allows:
        - Callbacks to publish their own events without deadlocking.
        - Other threads to publish concurrently without waiting.
        """
        # ── 1. Record in history (fast, under a narrow lock) ──────────
        with self._history_lock:
            self._history.append(event)
            while len(self._history) > self._max_history:
                self._history.popleft()

        # ── 2. Snapshot subscribers – brief lock, no I/O, no callbacks ─
        with self._sub_lock:
            subscribers: List[Callable] = []
            for cls in event.__class__.__mro__:
                if cls in self._subscribers:
                    subscribers.extend(self._subscribers[cls])

        # ── 3. Dispatch – lock released ───────────────────────────────
        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                name = getattr(callback, "__qualname__", "unknown")
                self._logger.error(
                    f"Subscriber '{name}' raised on {event.__class__.__name__}: {e}"
                )
                self._logger.debug(traceback.format_exc())

        # ── 4. Async IPC write (non-blocking) ─────────────────────────
        if self._ipc_enabled:
            self._schedule_ipc_write(event)

    # ------------------------------------------------------------------
    # IPC scheduling
    # ------------------------------------------------------------------

    def _schedule_ipc_write(self, event: Event) -> None:
        tm = self._get_thread_manager()
        if tm and tm is not False and tm.is_alive():
            try:
                tm.submit_task(self._ThreadPoolType.SYSTEM, self._write_ipc, event)
                return
            except Exception:
                pass
        # Fallback: write synchronously (startup or teardown)
        self._write_ipc(event)

    def _write_ipc(self, event: Event) -> None:
        event_type = event.__class__.__name__
        try:
            if event_type == "QuoteEvent":
                self._update_quote_state(event)
                self._flush_quotes()
            elif event_type == "CandleGenerated":
                self._update_candle_state(event)
                self._flush_candles()
            else:
                # Only non-tick events go to the general file
                self._write_general_event(event)
        except Exception as e:
            self._logger.debug(f"IPC write error ({event_type}): {e}")

    # ------------------------------------------------------------------
    # IPC state helpers
    # ------------------------------------------------------------------

    def _update_quote_state(self, event: Event) -> None:
        entry = {
            "symbol": event.instrument,
            "ltp": float(event.ltp),
            "ltq": float(event.ltq),
            "timestamp": event.timestamp.isoformat()
            if hasattr(event.timestamp, "isoformat")
            else str(event.timestamp),
            "source": event.source,
        }
        with self._ipc_state_lock:
            self._quote_state[event.instrument] = entry
            # Keep at most 10 symbols (trim oldest by timestamp)
            if len(self._quote_state) > 10:
                oldest = min(
                    self._quote_state.keys(),
                    key=lambda k: self._quote_state[k].get("timestamp", ""),
                )
                del self._quote_state[oldest]

    def _update_candle_state(self, event: Event) -> None:
        entry = {
            "symbol": event.symbol,
            "timeframe": event.timeframe,
            "timestamp": event.timestamp.isoformat()
            if hasattr(event.timestamp, "isoformat")
            else str(event.timestamp),
            "open": float(event.open),
            "high": float(event.high),
            "low": float(event.low),
            "close": float(event.close),
            "volume": float(event.volume),
            "vwap": float(event.vwap),
            "is_complete": event.is_complete,
            "source": event.source,
        }
        with self._ipc_state_lock:
            self._candle_state[event.symbol] = entry
            if len(self._candle_state) > 5:
                oldest = min(
                    self._candle_state.keys(),
                    key=lambda k: self._candle_state[k].get("timestamp", ""),
                )
                del self._candle_state[oldest]

    def _flush_quotes(self) -> None:
        with self._ipc_state_lock:
            snapshot = dict(self._quote_state)
        self._atomic_json_write(self._quote_file, snapshot)

    def _flush_candles(self) -> None:
        with self._ipc_state_lock:
            snapshot = dict(self._candle_state)
        self._atomic_json_write(self._candle_file, snapshot)

    def _write_general_event(self, event: Event) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "type": event.__class__.__name__,
            "data": self._serialize_event(event),
        }
        self._atomic_json_write(self._ipc_event_file, payload)

    @staticmethod
    def _atomic_json_write(path: str, data: Any) -> None:
        """Write JSON atomically: write to .tmp then rename. Never corrupts."""
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)   # POSIX-atomic; on Windows, also atomic in Python 3.3+

    @staticmethod
    def _serialize_event(event: Event) -> dict:
        """Serialize a dataclass event to a plain dict."""
        try:
            if dataclasses.is_dataclass(event):
                raw = dataclasses.asdict(event)
            else:
                raw = {
                    k: v
                    for k, v in vars(event).items()
                    if not k.startswith("_")
                }
            # Convert datetime values to ISO strings
            result = {}
            for k, v in raw.items():
                if isinstance(v, datetime):
                    result[k] = v.isoformat()
                elif isinstance(v, (str, int, float, bool, list, dict, type(None))):
                    result[k] = v
                else:
                    result[k] = str(v)
            return result
        except Exception:
            return {"error": "serialization_failed"}

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_event_history(
        self, event_type: Type[Event] = None, limit: int = None
    ) -> List[Event]:
        with self._history_lock:
            events = list(self._history)
        if event_type:
            events = [e for e in events if isinstance(e, event_type)]
        if limit:
            events = events[-limit:]
        return events

    def clear_history(self) -> None:
        with self._history_lock:
            self._history.clear()

    def get_subscriber_count(self, event_type: Type[Event]) -> int:
        with self._sub_lock:
            return len(self._subscribers.get(event_type, []))

    def list_event_types(self) -> List[str]:
        with self._sub_lock:
            return [cls.__name__ for cls in self._subscribers]

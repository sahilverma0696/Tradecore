"""
SystemConfigManager — singleton, thread-safe, file-watching system config.

Responsibilities
----------------
* Load and provide system_config.json via dot-notation get().
* Watch the file for changes and notify registered callbacks.
* Own the canonical "active streamer" and "active executor" selection.
* Provide switch_streamer() / switch_executor() for runtime switching;
  writes the change to disk atomically so the next restart picks it up,
  and fires callbacks so running code can react.

Thread safety
-------------
A single RLock guards all reads and writes to _config.
File writes use a temp-file + os.replace() so reads never see a torn file.
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.logger_factory import get_logger


# Keys that must exist for the system to start
_REQUIRED_KEYS = [
    "system.mode",
    "threading.event_bus_workers",
    "threading.streamer_workers",
    "threading.strategy_workers",
    "threading.executor_workers",
    "threading.system_workers",
    "streamer.active",
    "executor.active",
    "candle_maker.default_timeframe",
    "trading_session.start_time",
    "trading_session.end_time",
    "trading_session.timezone",
]

_VALID_STREAMERS = {"offline", "binance", "zerodha", "upstox"}
_VALID_EXECUTORS = {"paper", "binance", "zerodha", "upstox"}

_POLL_INTERVAL = 5.0  # seconds


class SystemConfigManager:
    """
    Singleton system configuration manager.

    Usage
    -----
    cfg = SystemConfigManager()
    cfg.get("streamer.active")          # "binance"
    cfg.switch_streamer("zerodha")      # changes active streamer, writes disk
    cfg.register_watcher(callback)      # called with full config on any change
    """

    _instance: Optional["SystemConfigManager"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls, config_file: str = "system_config.json") -> "SystemConfigManager":
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_file: str = "system_config.json") -> None:
        if hasattr(self, "_initialized"):
            return

        self.logger = get_logger("SystemConfig")
        self._config_file = Path(config_file)
        self._config: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._watchers: List[Callable[[Dict], None]] = []
        self._last_mtime: float = 0.0
        self._stop_event = threading.Event()

        self._load()
        self._validate()

        self._watcher_thread = threading.Thread(
            target=self._watch_loop,
            name="SystemConfig-Watcher",
            daemon=True,
        )
        self._watcher_thread.start()

        self._initialized = True
        self.logger.info(
            f"SystemConfigManager ready – "
            f"streamer={self.get('streamer.active')} "
            f"executor={self.get('executor.active')}"
        )

    # ------------------------------------------------------------------
    # Load / watch
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load config from disk. Uses defaults if file is missing."""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r") as f:
                    with self._lock:
                        self._config = json.load(f)
                self._last_mtime = self._config_file.stat().st_mtime
                self.logger.info(f"Loaded system config from {self._config_file}")
            except Exception as e:
                self.logger.error(f"Error loading {self._config_file}: {e} – using defaults")
                with self._lock:
                    self._config = self._defaults()
        else:
            self.logger.warning(f"{self._config_file} not found – creating with defaults")
            with self._lock:
                self._config = self._defaults()
            self._save()

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=_POLL_INTERVAL)
            if self._stop_event.is_set():
                break
            try:
                self._maybe_reload()
            except Exception as e:
                self.logger.error(f"Config watch error: {e}")

    def _maybe_reload(self) -> None:
        if not self._config_file.exists():
            return
        mtime = self._config_file.stat().st_mtime
        if mtime == self._last_mtime:
            return
        self.logger.info("system_config.json changed – reloading")
        with open(self._config_file, "r") as f:
            new_config = json.load(f)
        with self._lock:
            self._config = new_config
        self._last_mtime = mtime
        self._notify(new_config)

    def _notify(self, config: Dict) -> None:
        for cb in list(self._watchers):
            try:
                cb(config)
            except Exception as e:
                self.logger.error(f"Config watcher error: {e}")

    def stop(self) -> None:
        """Stop the file-watcher thread (useful in tests)."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Public API – read
    # ------------------------------------------------------------------

    def get(self, key_path: str, default: Any = None) -> Any:
        """Dot-notation read: get('streamer.active') → 'binance'."""
        with self._lock:
            node = self._config
            for key in key_path.split("."):
                if not isinstance(node, dict) or key not in node:
                    return default
                node = node[key]
            return node

    def get_all(self) -> Dict:
        """Return a deep copy of the full config."""
        with self._lock:
            return json.loads(json.dumps(self._config))

    def get_active_streamer(self) -> str:
        return self.get("streamer.active", "offline")

    def get_active_executor(self) -> str:
        return self.get("executor.active", "paper")

    def get_streamer_config(self) -> Dict[str, Any]:
        """Return {'type': '...', 'config': {...}} for the active streamer."""
        active = self.get_active_streamer()
        return {
            "type": active,
            "config": self.get(f"streamer.configs.{active}", {}),
        }

    def get_executioner_config(self) -> Dict[str, Any]:
        """Return {'type': '...', 'config': {...}} for the active executor."""
        active = self.get_active_executor()
        return {
            "type": active,
            "config": self.get(f"executor.configs.{active}", {}),
        }

    # ------------------------------------------------------------------
    # Public API – switch
    # ------------------------------------------------------------------

    def switch_streamer(self, streamer_type: str) -> None:
        """
        Change the active streamer.

        Validates the type has a config block, writes to disk atomically,
        and fires all watchers.  The running streamer is NOT stopped here —
        that is the caller's responsibility.
        """
        if streamer_type not in _VALID_STREAMERS:
            raise ValueError(
                f"Unknown streamer '{streamer_type}'. "
                f"Valid options: {sorted(_VALID_STREAMERS)}"
            )
        streamer_cfg = self.get(f"streamer.configs.{streamer_type}")
        if streamer_cfg is None:
            raise ValueError(
                f"No config block found for streamer '{streamer_type}' "
                f"in system_config.json under streamer.configs"
            )
        with self._lock:
            self._config.setdefault("streamer", {})["active"] = streamer_type
            snapshot = json.loads(json.dumps(self._config))
        self._save(snapshot)
        self.logger.info(f"Active streamer switched to '{streamer_type}'")
        self._notify(snapshot)

    def switch_executor(self, executor_type: str) -> None:
        """
        Change the active executor.

        Same semantics as switch_streamer – validates, writes, notifies.
        Stopping/restarting the running executor is the caller's responsibility.
        """
        if executor_type not in _VALID_EXECUTORS:
            raise ValueError(
                f"Unknown executor '{executor_type}'. "
                f"Valid options: {sorted(_VALID_EXECUTORS)}"
            )
        exec_cfg = self.get(f"executor.configs.{executor_type}")
        if exec_cfg is None:
            raise ValueError(
                f"No config block found for executor '{executor_type}' "
                f"in system_config.json under executor.configs"
            )
        with self._lock:
            self._config.setdefault("executor", {})["active"] = executor_type
            snapshot = json.loads(json.dumps(self._config))
        self._save(snapshot)
        self.logger.info(f"Active executor switched to '{executor_type}'")
        self._notify(snapshot)

    def register_watcher(self, cb: Callable[[Dict], None]) -> None:
        """Register a callback invoked whenever config changes on disk."""
        if callable(cb):
            self._watchers.append(cb)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Raise on startup if required keys are missing."""
        missing = [k for k in _REQUIRED_KEYS if self.get(k) is None]
        if missing:
            raise RuntimeError(
                "system_config.json is missing required keys:\n"
                + "\n".join(f"  - {k}" for k in missing)
            )
        active_streamer = self.get("streamer.active")
        if self.get(f"streamer.configs.{active_streamer}") is None:
            raise RuntimeError(
                f"streamer.active is '{active_streamer}' but "
                f"streamer.configs.{active_streamer} is not defined"
            )
        active_executor = self.get("executor.active")
        if self.get(f"executor.configs.{active_executor}") is None:
            raise RuntimeError(
                f"executor.active is '{active_executor}' but "
                f"executor.configs.{active_executor} is not defined"
            )
        self.logger.info("system_config.json validated")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self, config: Dict = None) -> None:
        """Atomically write config to disk."""
        with self._lock:
            data = config if config is not None else json.loads(json.dumps(self._config))
        tmp = str(self._config_file) + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._config_file)
            self._last_mtime = self._config_file.stat().st_mtime
        except Exception as e:
            self.logger.error(f"Failed to save system config: {e}")
            try:
                os.unlink(tmp)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Convenience (keep backward-compat with old callers)
    # ------------------------------------------------------------------

    def is_offline_mode(self) -> bool:
        return self.get("system.mode", "offline") == "offline"

    def is_live_mode(self) -> bool:
        return self.get("system.mode", "offline") == "live"

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    @staticmethod
    def _defaults() -> Dict:
        return {
            "system": {"mode": "offline"},
            "logging": {
                "level": "INFO",
                "file_logging": True,
                "log_directory": "logs",
                "console_logging": True,
            },
            "threading": {
                "event_bus_workers": 2,
                "streamer_workers": 4,
                "strategy_workers": 2,
                "executor_workers": 2,
                "system_workers": 2,
            },
            "streamer": {
                "active": "offline",
                "async_enabled": True,
                "configs": {
                    "offline": {
                        "tick_interval": 1.0,
                        "base_price": 18500.0,
                        "async_mode": True,
                    },
                    "binance": {
                        "reconnect_attempts": 5,
                        "reconnect_delay": 2.0,
                        "stream_timeout": 60,
                        "testnet": False,
                    },
                    "zerodha": {
                        "reconnect_attempts": 5,
                        "reconnect_delay": 2.0,
                    },
                    "upstox": {
                        "reconnect_attempts": 5,
                        "reconnect_delay": 2.0,
                    },
                },
            },
            "executor": {
                "active": "paper",
                "configs": {
                    "paper": {
                        "slippage_factor": 0.0001,
                        "execution_delay": 0.1,
                        "initial_cash": 100000.0,
                    },
                    "binance": {
                        "order_type": "MARKET",
                        "time_in_force": "GTC",
                        "test_mode": True,
                        "max_retries": 3,
                    },
                    "zerodha": {
                        "exchange": "NFO",
                        "product": "MIS",
                        "variety": "regular",
                        "max_retries": 3,
                    },
                    "upstox": {
                        "exchange": "NSE_FO",
                        "product": "I",
                        "validity": "DAY",
                        "max_retries": 3,
                    },
                },
            },
            "candle_maker": {
                "default_timeframe": 3,
                "calculate_vwap": True,
                "persist_candles": True,
            },
            "trading_session": {
                "start_time": "09:15",
                "end_time": "15:30",
                "timezone": "Asia/Kolkata",
            },
        }

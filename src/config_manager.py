"""
ConfigManager — thread-safe, file-watching trading config loader.

Responsibilities
----------------
* Load and provide trading_config.json.
* Watch for file changes and notify registered callbacks.
* Validate required trading fields on load.
* Expose both full-dict access (get()) and dot-notation access (get_value()).

Thread safety
-------------
An RLock guards _config so concurrent reads and the reload write never race.
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.logger_factory import get_logger


CONFIG_FILE = "trading_config.json"

# Fields that must be present and have sensible values for the system to trade
_REQUIRED_FIELDS: List[str] = [
    "symbols",
    "trail",
    "loss_stop_low",
    "loss_stop_high",
    "default_quantity",
    "market_close_time",
]


class ConfigManager:
    """
    Thread-safe, file-polling trading configuration manager.

    Usage
    -----
    cfg = ConfigManager()
    cfg.get()                         # full dict (deep copy)
    cfg.get_value("trail")            # 0.03
    cfg.get_value("execution.delta_sell", default=0.02)
    cfg.register_watcher(callback)    # called with full config on change
    cfg.stop()                        # stop background watcher (tests)
    """

    def __init__(
        self,
        config_path: str = CONFIG_FILE,
        poll_interval: float = 10.0,
    ) -> None:
        self._path = Path(config_path)
        self._poll_interval = poll_interval
        self._logger = get_logger("ConfigManager")
        self._config: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._watchers: List[Callable[[Dict], None]] = []
        self._last_mtime: float = 0.0
        self._stop_event = threading.Event()

        self._load()
        self._validate()

        self._watcher_thread = threading.Thread(
            target=self._watch_loop,
            name="TradingConfig-Watcher",
            daemon=True,
        )
        self._watcher_thread.start()

    # ------------------------------------------------------------------
    # Load / watch
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            self._logger.warning(f"{self._path} not found – using empty config")
            return
        try:
            with open(self._path, "r") as f:
                new_config = json.load(f)
            with self._lock:
                self._config = new_config
            # Record mtime AFTER load so first poll tick doesn't re-trigger
            self._last_mtime = self._path.stat().st_mtime
            self._logger.info(f"Loaded trading config from {self._path}")
        except Exception as e:
            self._logger.error(f"Failed loading {self._path}: {e}")

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._poll_interval)
            if self._stop_event.is_set():
                break
            try:
                self._maybe_reload()
            except Exception as e:
                self._logger.error(f"Config watch error: {e}")

    def _maybe_reload(self) -> None:
        if not self._path.exists():
            return
        mtime = self._path.stat().st_mtime
        if mtime == self._last_mtime:
            return
        self._logger.info("trading_config.json changed – reloading")
        try:
            with open(self._path, "r") as f:
                new_config = json.load(f)
            with self._lock:
                self._config = new_config
            self._last_mtime = mtime
            self._notify(new_config)
        except Exception as e:
            self._logger.error(f"Reload failed: {e} – keeping previous config")

    def _notify(self, config: Dict) -> None:
        for cb in list(self._watchers):
            try:
                cb(config)
            except Exception as e:
                self._logger.error(f"Watcher error: {e}")

    def stop(self) -> None:
        """Stop the background watcher thread."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self) -> Dict:
        """Return a deep copy of the full trading config."""
        with self._lock:
            return json.loads(json.dumps(self._config))

    def get_value(self, key_path: str, default: Any = None) -> Any:
        """
        Dot-notation read.

        get_value("trail")                  → 0.03
        get_value("execution.delta_sell")   → 0.02
        get_value("missing.key", default=0) → 0
        """
        with self._lock:
            node = self._config
            for key in key_path.split("."):
                if not isinstance(node, dict) or key not in node:
                    return default
                node = node[key]
            return node

    def register_watcher(self, cb: Callable[[Dict], None]) -> None:
        """Register a callback invoked on every config reload."""
        if callable(cb):
            self._watchers.append(cb)
            self._logger.debug(f"Registered watcher: {getattr(cb, '__qualname__', cb)}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Raise on startup if required trading fields are missing or invalid."""
        errors: List[str] = []

        for field in _REQUIRED_FIELDS:
            val = self.get_value(field)
            if val is None:
                errors.append(f"  - '{field}' is missing")

        # symbols must be a non-empty list
        symbols = self.get_value("symbols")
        if isinstance(symbols, list) and len(symbols) == 0:
            errors.append("  - 'symbols' is empty")
        elif symbols is not None and not isinstance(symbols, list):
            errors.append("  - 'symbols' must be a list")

        # quantity must be a number (guard against the old string "100" bug)
        qty = self.get_value("default_quantity")
        if qty is not None and not isinstance(qty, (int, float)):
            errors.append(
                f"  - 'default_quantity' must be a number, got {type(qty).__name__!r}"
            )

        # trail / loss stops must be floats in sensible range
        for field, lo, hi in [
            ("trail", 0.001, 0.5),
            ("loss_stop_low", 0.5, 1.0),
            ("loss_stop_high", 1.0, 2.0),
        ]:
            val = self.get_value(field)
            if val is not None:
                try:
                    val = float(val)
                    if not (lo <= val <= hi):
                        errors.append(
                            f"  - '{field}' = {val} is outside expected range [{lo}, {hi}]"
                        )
                except (TypeError, ValueError):
                    errors.append(f"  - '{field}' must be a number")

        if errors:
            raise RuntimeError(
                "trading_config.json validation failed:\n" + "\n".join(errors)
            )
        self._logger.info("trading_config.json validated")

import json
import os
import threading
import time
from typing import Callable, Dict, List

from src.logger_factory import get_logger

CONFIG_FILE = "trading_config.json"
POLL_INTERVAL = 10  # seconds

class ConfigManager:
    """File-polling JSON config loader with callback support."""
    def __init__(self, config_path: str = CONFIG_FILE):
        self._path = config_path
        self._logger = get_logger("ConfigManager")
        self._watchers: List[Callable[[Dict], None]] = []
        self._last_mtime: float = 0.0
        self._config: Dict = {}
        self._reload()
        threading.Thread(target=self._watch_loop, daemon=True).start()

    def get(self) -> Dict:
        return self._config

    def register_watcher(self, cb: Callable[[Dict], None]):
        if callable(cb):
            self._watchers.append(cb)
            self._logger.debug(f"Registered watcher {cb}")

    # internal
    def _watch_loop(self):
        while True:
            try:
                self._maybe_reload()
            except Exception as e:
                self._logger.error(f"Watch loop error: {e}")
            time.sleep(POLL_INTERVAL)

    def _maybe_reload(self):
        if not os.path.exists(self._path):
            return
        mtime = os.path.getmtime(self._path)
        if mtime != self._last_mtime:
            self._last_mtime = mtime
            self._reload()

    def _reload(self):
        try:
            with open(self._path, 'r') as f:
                self._config = json.load(f)
            self._logger.info("Config reloaded")
            for cb in self._watchers:
                try:
                    cb(self._config)
                except Exception as e:
                    self._logger.error(f"Watcher error: {e}")
        except Exception as e:
            self._logger.error(f"Failed loading config: {e}")

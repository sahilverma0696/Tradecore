from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime

from src.logger_factory import get_logger
from src.core.event_bus import Publisher, QuoteEvent
from src.core.thread_manager import ThreadManager, ThreadPoolType


class BaseStreamer(Publisher, ABC):
    """
    Abstract base for all market data streamers.

    Subclasses must implement:
        _setup_connection()
        _run_connection()
        _cleanup_connection()
        _normalize_raw_data(raw_data, symbol) -> QuoteEvent | None

    Optionally override:
        _run_connection_async()   – async streaming path
    """

    def __init__(self, symbols: List[str], name: str = None):
        super().__init__()
        self.symbols = symbols
        self.name = name or self.__class__.__name__
        self._logger = get_logger(self.name)
        self._is_running = False
        self._connection_future = None
        self._thread_manager = ThreadManager()
        self._logger.info(f"{self.name} initialised with {len(symbols)} symbol(s)")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        if self._is_running:
            self._logger.warning(f"{self.name} already running")
            return
        self._is_running = True
        try:
            self._setup_connection()
            self._connection_future = self._thread_manager.submit_task(
                ThreadPoolType.STREAMER, self._run_connection_wrapper
            )
            self._logger.info(f"{self.name} started")
        except Exception as e:
            self._is_running = False
            self._logger.error(f"{self.name} start failed: {e}")
            raise

    def start_async(self) -> Optional[asyncio.Future]:
        if self._is_running:
            self._logger.warning(f"{self.name} already running")
            return None
        self._is_running = True
        try:
            self._setup_connection()
            self._connection_future = self._thread_manager.submit_async_task(
                ThreadPoolType.STREAMER, self._run_connection_async()
            )
            self._logger.info(f"{self.name} started (async)")
            return self._connection_future
        except Exception as e:
            self._is_running = False
            self._logger.error(f"{self.name} async start failed: {e}")
            raise

    def stop(self):
        if not self._is_running:
            return
        self._logger.info(f"Stopping {self.name}...")
        self._is_running = False
        try:
            self._cleanup_connection()
        except Exception as e:
            self._logger.error(f"Error during {self.name} cleanup: {e}")
        self._logger.info(f"{self.name} stopped")

    def is_running(self) -> bool:
        return self._is_running

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_quote(self, event: QuoteEvent):
        """Submit a QuoteEvent to the EVENT_BUS pool for dispatch."""
        def _task():
            try:
                self.publish_event(event)
            except Exception as e:
                self._logger.error(f"Error publishing quote for {event.instrument}: {e}")

        self._thread_manager.submit_task(ThreadPoolType.EVENT_BUS, _task)

    # ------------------------------------------------------------------
    # Internal wrappers
    # ------------------------------------------------------------------

    def _run_connection_wrapper(self):
        try:
            self._run_connection()
        except Exception as e:
            self._logger.error(f"Connection error in {self.name}: {e}")
            self._is_running = False
            raise
        finally:
            self._logger.info(f"{self.name} connection ended")

    async def _run_connection_async(self):
        """Default async path: runs sync connection in a thread executor."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._run_connection)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'is_running': self._is_running,
            'symbols': self.symbols,
            'thread_pool_stats': self._thread_manager.get_pool_stats().get('streamer', {}),
        }

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _setup_connection(self): ...

    @abstractmethod
    def _run_connection(self): ...

    @abstractmethod
    def _cleanup_connection(self): ...

    @abstractmethod
    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> Optional[QuoteEvent]: ...

import threading
import asyncio
import concurrent.futures
import sys
from typing import Dict, Any, Callable, Optional
from enum import Enum
import time
from dataclasses import dataclass

from src.logger_factory import get_logger
from src.system_config_manager import SystemConfigManager


class ThreadPoolType(Enum):
    """Types of thread pools in the system."""
    EVENT_BUS = "event_bus"
    STREAMER = "streamer"
    STRATEGY = "strategy"
    EXECUTOR = "executor"
    SYSTEM = "system"


@dataclass
class ThreadPoolConfig:
    """Configuration for a thread pool."""
    pool_type: ThreadPoolType
    max_workers: int
    thread_name_prefix: str
    daemon: bool = True
    has_async_loop: bool = False


class ThreadManager:
    """
    Centralized thread pool management for the trading system.

    Pools
    -----
    EVENT_BUS  – dispatching event callbacks
    STREAMER   – market data ingestion (has a companion asyncio loop)
    STRATEGY   – signal processing
    EXECUTOR   – order placement
    SYSTEM     – I/O and housekeeping

    Thread-safety guarantees
    ------------------------
    * _stats_lock protects all counter mutations.
    * Pool creation and shutdown are serialised by _init_lock.
    * Singleton is never recreated after shutdown (raises on reuse).
    """

    _instance: Optional["ThreadManager"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls) -> "ThreadManager":
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self.logger = get_logger("ThreadManager", console_output=True)
        self._system_config = SystemConfigManager()

        # Pools and async companions
        self._thread_pools: Dict[ThreadPoolType, concurrent.futures.ThreadPoolExecutor] = {}
        self._async_loops: Dict[ThreadPoolType, asyncio.AbstractEventLoop] = {}
        self._loop_threads: Dict[ThreadPoolType, threading.Thread] = {}

        # Task counters – always mutated under _stats_lock
        self._stats_lock = threading.Lock()
        self._active_tasks: Dict[ThreadPoolType, int] = {}
        self._completed_tasks: Dict[ThreadPoolType, int] = {}
        self._failed_tasks: Dict[ThreadPoolType, int] = {}

        self._init_lock = threading.Lock()
        self._pools_ready = False
        self._is_shutdown = False

        # Build and cache pool configs at init time so callers can inspect them
        # before initialize_pools() is called (tests rely on this).
        self._pool_configs = self._build_pool_configs()

        self._initialized = True
        self.logger.info("ThreadManager created")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _build_pool_configs(self) -> Dict[ThreadPoolType, ThreadPoolConfig]:
        cfg = self._system_config
        return {
            ThreadPoolType.EVENT_BUS: ThreadPoolConfig(
                pool_type=ThreadPoolType.EVENT_BUS,
                max_workers=cfg.get("threading.event_bus_workers", 2),
                thread_name_prefix="EventBus",
                daemon=True,
                has_async_loop=False,
            ),
            ThreadPoolType.STREAMER: ThreadPoolConfig(
                pool_type=ThreadPoolType.STREAMER,
                max_workers=cfg.get("threading.streamer_workers", 4),
                thread_name_prefix="Streamer",
                daemon=True,
                has_async_loop=True,   # streamers may be async
            ),
            ThreadPoolType.STRATEGY: ThreadPoolConfig(
                pool_type=ThreadPoolType.STRATEGY,
                max_workers=cfg.get("threading.strategy_workers", 2),
                thread_name_prefix="Strategy",
                daemon=True,
            ),
            ThreadPoolType.EXECUTOR: ThreadPoolConfig(
                pool_type=ThreadPoolType.EXECUTOR,
                max_workers=cfg.get("threading.executor_workers", 2),
                thread_name_prefix="Executor",
                daemon=True,
            ),
            ThreadPoolType.SYSTEM: ThreadPoolConfig(
                pool_type=ThreadPoolType.SYSTEM,
                max_workers=cfg.get("threading.system_workers", 2),
                thread_name_prefix="System",
                daemon=True,
            ),
        }

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialize_pools(self) -> None:
        """Create all thread pools. Safe to call only once; raises on double-init."""
        with self._init_lock:
            if self._pools_ready:
                raise RuntimeError("ThreadManager.initialize_pools() called twice – pools already running")
            if self._is_shutdown:
                raise RuntimeError("ThreadManager has been shut down; create a new instance")

            for pool_type, config in self._pool_configs.items():
                self._create_pool(pool_type, config)
                with self._stats_lock:
                    self._active_tasks[pool_type] = 0
                    self._completed_tasks[pool_type] = 0
                    self._failed_tasks[pool_type] = 0

            self._pools_ready = True
            self.logger.info(f"Initialized {len(self._thread_pools)} thread pools")

    def _create_pool(self, pool_type: ThreadPoolType, config: ThreadPoolConfig) -> None:
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=config.max_workers,
            thread_name_prefix=config.thread_name_prefix,
        )
        self._thread_pools[pool_type] = executor

        if config.has_async_loop:
            loop = asyncio.new_event_loop()
            self._async_loops[pool_type] = loop
            loop_thread = threading.Thread(
                target=self._run_async_loop,
                args=(pool_type, loop),
                name=f"{config.thread_name_prefix}-AsyncLoop",
                daemon=config.daemon,
            )
            loop_thread.start()
            self._loop_threads[pool_type] = loop_thread

        self.logger.info(
            f"Pool '{pool_type.value}' ready – {config.max_workers} workers"
            + (" + async loop" if config.has_async_loop else "")
        )

    def _run_async_loop(self, pool_type: ThreadPoolType, loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        except Exception as e:
            self.logger.error(f"Async loop for {pool_type.value} crashed: {e}")
        finally:
            # Clean up any pending callbacks before closing
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    def submit_task(
        self,
        pool_type: ThreadPoolType,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> concurrent.futures.Future:
        """Submit a synchronous callable to the given pool."""
        self._assert_ready(pool_type)

        # Submit first; only count on success so the counter stays accurate
        future = self._thread_pools[pool_type].submit(func, *args, **kwargs)

        with self._stats_lock:
            self._active_tasks[pool_type] += 1

        future.add_done_callback(lambda f: self._on_task_done(pool_type, f))
        return future

    def submit_async_task(
        self, pool_type: ThreadPoolType, coro
    ) -> "concurrent.futures.Future":
        """Schedule a coroutine on the pool's companion asyncio loop."""
        if pool_type not in self._async_loops:
            raise ValueError(f"Pool '{pool_type.value}' has no async loop")

        loop = self._async_loops[pool_type]
        future = asyncio.run_coroutine_threadsafe(coro, loop)

        with self._stats_lock:
            self._active_tasks[pool_type] += 1

        future.add_done_callback(lambda f: self._on_task_done(pool_type, f))
        return future

    def _on_task_done(
        self, pool_type: ThreadPoolType, future: concurrent.futures.Future
    ) -> None:
        with self._stats_lock:
            self._active_tasks[pool_type] = max(0, self._active_tasks[pool_type] - 1)

        try:
            exc = future.exception()          # raises CancelledError if cancelled
        except concurrent.futures.CancelledError:
            # Task was cancelled during shutdown – not a failure
            with self._stats_lock:
                self._completed_tasks[pool_type] += 1
            return
        except Exception:
            exc = None

        if exc is not None:
            with self._stats_lock:
                self._failed_tasks[pool_type] += 1
            self.logger.error(f"Task failed in pool '{pool_type.value}': {exc}")
        else:
            with self._stats_lock:
                self._completed_tasks[pool_type] += 1

    # ------------------------------------------------------------------
    # Health / stats
    # ------------------------------------------------------------------

    def get_pool_stats(self) -> Dict[str, Dict[str, Any]]:
        stats: Dict[str, Dict[str, Any]] = {}
        with self._stats_lock:
            for pool_type, executor in self._thread_pools.items():
                stats[pool_type.value] = {
                    "max_workers": executor._max_workers,
                    "active_tasks": self._active_tasks.get(pool_type, 0),
                    "completed_tasks": self._completed_tasks.get(pool_type, 0),
                    "failed_tasks": self._failed_tasks.get(pool_type, 0),
                    "has_async_loop": pool_type in self._async_loops,
                }
        return stats

    def is_alive(self) -> bool:
        return self._pools_ready and not self._is_shutdown

    def _assert_ready(self, pool_type: ThreadPoolType) -> None:
        if self._is_shutdown:
            raise RuntimeError("ThreadManager has been shut down")
        if pool_type not in self._thread_pools:
            raise ValueError(f"Pool '{pool_type.value}' not initialised – call initialize_pools() first")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self, wait: bool = True, timeout: float = 10.0) -> None:
        """
        Shut down all pools in safe order:
          1. Cancel and drain thread pools (stops new work).
          2. Stop asyncio loops (pool threads are already done so no deadlock).
          3. Join loop threads.
        """
        with self._init_lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True

        self.logger.info("Shutting down thread pools...")

        # ── Step 1: thread pool executors ────────────────────────────────
        for pool_type, executor in self._thread_pools.items():
            try:
                if sys.version_info >= (3, 9):
                    executor.shutdown(wait=wait, cancel_futures=True)
                else:
                    executor.shutdown(wait=wait)
                self.logger.info(f"Pool '{pool_type.value}' shut down")
            except Exception as e:
                self.logger.error(f"Error shutting down pool '{pool_type.value}': {e}")

        # ── Step 2: asyncio loops ────────────────────────────────────────
        for pool_type, loop in self._async_loops.items():
            try:
                if loop.is_running():
                    loop.call_soon_threadsafe(loop.stop)
            except Exception as e:
                self.logger.error(f"Error stopping async loop for '{pool_type.value}': {e}")

        # ── Step 3: join loop threads ────────────────────────────────────
        for pool_type, thread in self._loop_threads.items():
            if thread.is_alive():
                thread.join(timeout=timeout)
                if thread.is_alive():
                    self.logger.warning(
                        f"Async loop thread for '{pool_type.value}' did not stop within {timeout}s"
                    )

        self.logger.info("Thread pool shutdown complete")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def get_thread_manager() -> ThreadManager:
    return ThreadManager()


def submit_to_pool(
    pool_type: ThreadPoolType, func: Callable, *args: Any, **kwargs: Any
) -> concurrent.futures.Future:
    return get_thread_manager().submit_task(pool_type, func, *args, **kwargs)


def submit_async_to_pool(pool_type: ThreadPoolType, coro) -> "concurrent.futures.Future":
    return get_thread_manager().submit_async_task(pool_type, coro)

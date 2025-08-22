import threading
import asyncio
import concurrent.futures
from typing import Dict, Any, Callable, Optional
from enum import Enum
import time
import queue
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
    queue_size: Optional[int] = None


class ThreadManager:
    """
    Centralized thread pool management for the trading system.
    Manages different types of thread pools for different system components.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self.logger = get_logger("ThreadManager",console_output=True)
        self.system_config = SystemConfigManager()
        
        # Thread pools for different components
        self._thread_pools: Dict[ThreadPoolType, concurrent.futures.ThreadPoolExecutor] = {}
        self._async_loops: Dict[ThreadPoolType, asyncio.AbstractEventLoop] = {}
        self._loop_threads: Dict[ThreadPoolType, threading.Thread] = {}
        
        # Thread pool configurations
        self._pool_configs = self._load_thread_pool_configs()
        
        # Monitoring
        self._active_tasks: Dict[ThreadPoolType, int] = {}
        self._completed_tasks: Dict[ThreadPoolType, int] = {}
        self._failed_tasks: Dict[ThreadPoolType, int] = {}
        
        self._shutdown_event = threading.Event()
        self._initialized = True
        
        self.logger.info("ThreadManager initialized")
    
    def _load_thread_pool_configs(self) -> Dict[ThreadPoolType, ThreadPoolConfig]:
        """Load thread pool configurations from system config."""
        configs = {}
        
        # Default configurations
        default_configs = {
            ThreadPoolType.EVENT_BUS: ThreadPoolConfig(
                pool_type=ThreadPoolType.EVENT_BUS,
                max_workers=self.system_config.get('threading.event_bus_workers', 2),
                thread_name_prefix="EventBus",
                daemon=True,
                queue_size=self.system_config.get('event_bus.max_event_history', 1000)
            ),
            ThreadPoolType.STREAMER: ThreadPoolConfig(
                pool_type=ThreadPoolType.STREAMER,
                max_workers=self.system_config.get('threading.streamer_workers', 4),
                thread_name_prefix="Streamer",
                daemon=True,
                queue_size=self.system_config.get('streamers.buffer_size', 1024)
            ),
            ThreadPoolType.STRATEGY: ThreadPoolConfig(
                pool_type=ThreadPoolType.STRATEGY,
                max_workers=self.system_config.get('threading.strategy_workers', 2),
                thread_name_prefix="Strategy",
                daemon=True
            ),
            ThreadPoolType.EXECUTOR: ThreadPoolConfig(
                pool_type=ThreadPoolType.EXECUTOR,
                max_workers=self.system_config.get('threading.executor_workers', 2),
                thread_name_prefix="Executor",
                daemon=True
            ),
            ThreadPoolType.SYSTEM: ThreadPoolConfig(
                pool_type=ThreadPoolType.SYSTEM,
                max_workers=self.system_config.get('threading.system_workers', 2),
                thread_name_prefix="System",
                daemon=True
            )
        }
        
        return default_configs
    
    def initialize_pools(self):
        """Initialize all thread pools."""
        try:
            for pool_type, config in self._pool_configs.items():
                self._create_thread_pool(pool_type, config)
                self._active_tasks[pool_type] = 0
                self._completed_tasks[pool_type] = 0
                self._failed_tasks[pool_type] = 0
            
            self.logger.info(f"Initialized {len(self._thread_pools)} thread pools")
            
        except Exception as e:
            self.logger.error(f"Error initializing thread pools: {e}")
            raise
    
    def _create_thread_pool(self, pool_type: ThreadPoolType, config: ThreadPoolConfig):
        """Create a specific thread pool."""
        try:
            # Create ThreadPoolExecutor
            executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=config.max_workers,
                thread_name_prefix=config.thread_name_prefix
            )
            
            self._thread_pools[pool_type] = executor
            
            # Create async event loop for async operations
            if pool_type in [ThreadPoolType.STREAMER, ThreadPoolType.EVENT_BUS]:
                loop = asyncio.new_event_loop()
                self._async_loops[pool_type] = loop
                
                # Start loop in separate thread
                loop_thread = threading.Thread(
                    target=self._run_async_loop,
                    args=(pool_type, loop),
                    name=f"{config.thread_name_prefix}-AsyncLoop",
                    daemon=config.daemon
                )
                loop_thread.start()
                self._loop_threads[pool_type] = loop_thread
            
            self.logger.info(f"Created {pool_type.value} thread pool with {config.max_workers} workers")
            
        except Exception as e:
            self.logger.error(f"Error creating {pool_type.value} thread pool: {e}")
            raise
    
    def _run_async_loop(self, pool_type: ThreadPoolType, loop: asyncio.AbstractEventLoop):
        """Run asyncio event loop in a separate thread."""
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        except Exception as e:
            self.logger.error(f"Error in {pool_type.value} async loop: {e}")
        finally:
            loop.close()
    
    def submit_task(self, pool_type: ThreadPoolType, func: Callable, *args, **kwargs) -> concurrent.futures.Future:
        """Submit a task to the specified thread pool."""
        try:
            if pool_type not in self._thread_pools:
                raise ValueError(f"Thread pool {pool_type.value} not initialized")
            
            self._active_tasks[pool_type] += 1
            
            future = self._thread_pools[pool_type].submit(func, *args, **kwargs)
            
            # Add completion callback
            future.add_done_callback(lambda f: self._task_completed(pool_type, f))
            
            return future
            
        except Exception as e:
            self.logger.error(f"Error submitting task to {pool_type.value}: {e}")
            raise
    
    def submit_async_task(self, pool_type: ThreadPoolType, coro) -> asyncio.Future:
        """Submit an async task to the specified async loop."""
        try:
            if pool_type not in self._async_loops:
                raise ValueError(f"Async loop {pool_type.value} not available")
            
            loop = self._async_loops[pool_type]
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            
            self._active_tasks[pool_type] += 1
            future.add_done_callback(lambda f: self._task_completed(pool_type, f))
            
            return future
            
        except Exception as e:
            self.logger.error(f"Error submitting async task to {pool_type.value}: {e}")
            raise
    
    def _task_completed(self, pool_type: ThreadPoolType, future: concurrent.futures.Future):
        """Handle task completion."""
        self._active_tasks[pool_type] -= 1
        
        if future.exception():
            self._failed_tasks[pool_type] += 1
            self.logger.error(f"Task failed in {pool_type.value}: {future.exception()}")
        else:
            self._completed_tasks[pool_type] += 1
    
    def get_pool_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics for all thread pools."""
        stats = {}
        
        for pool_type in ThreadPoolType:
            if pool_type in self._thread_pools:
                executor = self._thread_pools[pool_type]
                stats[pool_type.value] = {
                    'max_workers': executor._max_workers,
                    'active_tasks': self._active_tasks.get(pool_type, 0),
                    'completed_tasks': self._completed_tasks.get(pool_type, 0),
                    'failed_tasks': self._failed_tasks.get(pool_type, 0),
                    'has_async_loop': pool_type in self._async_loops
                }
        
        return stats
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """Shutdown all thread pools."""
        self.logger.info("Shutting down thread pools...")
        self._shutdown_event.set()
        
        # Shutdown thread pools
        for pool_type, executor in self._thread_pools.items():
            try:
                # Use shutdown without timeout parameter for compatibility
                executor.shutdown(wait=wait)
                self.logger.info(f"Shutdown {pool_type.value} thread pool")
            except Exception as e:
                self.logger.error(f"Error shutting down {pool_type.value}: {e}")
        
        # Stop async loops
        for pool_type, loop in self._async_loops.items():
            try:
                loop.call_soon_threadsafe(loop.stop)
                
                # Wait for loop thread to finish
                if pool_type in self._loop_threads:
                    self._loop_threads[pool_type].join(timeout=5.0)
                
                self.logger.info(f"Stopped {pool_type.value} async loop")
            except Exception as e:
                self.logger.error(f"Error stopping {pool_type.value} async loop: {e}")
        
        self.logger.info("Thread pool shutdown complete")


# Convenience functions for global access
def get_thread_manager() -> ThreadManager:
    """Get the thread manager singleton."""
    return ThreadManager()


def submit_to_pool(pool_type: ThreadPoolType, func: Callable, *args, **kwargs) -> concurrent.futures.Future:
    """Submit a task to a specific thread pool."""
    return get_thread_manager().submit_task(pool_type, func, *args, **kwargs)


def submit_async_to_pool(pool_type: ThreadPoolType, coro) -> asyncio.Future:
    """Submit an async task to a specific async loop."""
    return get_thread_manager().submit_async_task(pool_type, coro)

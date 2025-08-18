from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import threading
import asyncio
from datetime import datetime

from src.logger_factory import get_logger
from src.core.event_bus import Publisher, QuoteReceived
from src.core.thread_manager import ThreadManager, ThreadPoolType
from .quote_normalizer import QuoteNormalizer


class BaseStreamer(Publisher, ABC):
    """
    Abstract base class for all market data streamers with thread pool support.
    
    Provides core functionality:
    - Event bus integration via Publisher mixin
    - Lifecycle management (start/stop)
    - Quote normalization
    - Thread pool integration for async operations
    """
    
    def __init__(self, symbols: List[str], name: str = None):
        super().__init__()  # Initialize Publisher mixin
        self.symbols = symbols
        self.name = name or self.__class__.__name__
        self._logger = get_logger(self.name)
        self._is_running = False
        self._connection_thread = None
        self._quote_normalizer = QuoteNormalizer()
        
        # Thread management
        self._thread_manager = ThreadManager()
        self._async_tasks = []
        
        self._logger.info(f"{self.name} initialized with symbols: {symbols}")
    
    def start(self):
        """Start the streaming service using thread pools."""
        if self._is_running:
            self._logger.warning(f"{self.name} is already running")
            return
        
        self._logger.info(f"Starting {self.name}...")
        self._is_running = True
        
        try:
            # Setup connection
            self._setup_connection()
            
            # Submit connection task to streamer thread pool
            connection_future = self._thread_manager.submit_task(
                ThreadPoolType.STREAMER,
                self._run_connection_wrapper
            )
            
            # Store future for monitoring
            self._connection_future = connection_future
            
            self._logger.info(f"{self.name} started successfully")
        except Exception as e:
            self._logger.error(f"Failed to start {self.name}: {e}")
            self._is_running = False
            raise
    
    def start_async(self) -> asyncio.Future:
        """Start streaming with async support."""
        if self._is_running:
            self._logger.warning(f"{self.name} is already running")
            return None
        
        self._logger.info(f"Starting {self.name} with async support...")
        self._is_running = True
        
        try:
            # Setup connection
            self._setup_connection()
            
            # Submit async connection task
            if hasattr(self, '_run_connection_async'):
                future = self._thread_manager.submit_async_task(
                    ThreadPoolType.STREAMER,
                    self._run_connection_async()
                )
            else:
                # Fallback to sync version in thread pool
                future = self._thread_manager.submit_task(
                    ThreadPoolType.STREAMER,
                    self._run_connection_wrapper
                )
            
            self._connection_future = future
            self._logger.info(f"{self.name} started successfully with async support")
            return future
            
        except Exception as e:
            self._logger.error(f"Failed to start {self.name} async: {e}")
            self._is_running = False
            raise
    
    def _run_connection_wrapper(self):
        """Wrapper for connection that handles exceptions."""
        try:
            self._run_connection()
        except Exception as e:
            self._logger.error(f"Connection error in {self.name}: {e}")
            self._is_running = False
            raise
        finally:
            self._logger.info(f"{self.name} connection ended")
    
    def stop(self):
        """Stop the streaming service."""
        if not self._is_running:
            return
        
        self._logger.info(f"Stopping {self.name}...")
        self._is_running = False
        
        try:
            # Cancel connection future if running
            if hasattr(self, '_connection_future') and self._connection_future:
                self._connection_future.cancel()
            
            # Cancel any async tasks
            for task in self._async_tasks:
                if not task.done():
                    task.cancel()
            self._async_tasks.clear()
            
            self._cleanup_connection()
            self._logger.info(f"{self.name} stopped successfully")
        except Exception as e:
            self._logger.error(f"Error stopping {self.name}: {e}")
    
    def is_running(self) -> bool:
        """Check if streamer is running."""
        return self._is_running
    
    def publish_quote(self, symbol: str, ltp: float, volume: int = 0, 
                     bid: float = 0, ask: float = 0, raw_data: Dict[str, Any] = None):
        """
        Publish a normalized quote as QuoteReceived event using event bus thread pool.
        """
        def _publish_quote_task():
            try:
                quote_event = QuoteReceived(
                    timestamp=datetime.now(),
                    source=self.name,
                    symbol=symbol,
                    instrument=hash(symbol),  # Simple hash for instrument ID
                    ltp=ltp,
                    volume=volume,
                    last_quantity=volume,
                    change=0.0,  # Can be calculated if needed
                    raw_data=raw_data or {}
                )
                
                self.publish_event(quote_event)
                self._logger.debug(f"Published quote for {symbol}: LTP={ltp}, Volume={volume}")
                
            except Exception as e:
                self._logger.error(f"Error publishing quote for {symbol}: {e}")
        
        # Submit quote publishing to event bus thread pool
        self._thread_manager.submit_task(ThreadPoolType.EVENT_BUS, _publish_quote_task)
    
    async def publish_quote_async(self, symbol: str, ltp: float, volume: int = 0, 
                                 bid: float = 0, ask: float = 0, raw_data: Dict[str, Any] = None):
        """Async version of quote publishing."""
        try:
            quote_event = QuoteReceived(
                timestamp=datetime.now(),
                source=self.name,
                symbol=symbol,
                instrument=hash(symbol),
                ltp=ltp,
                volume=volume,
                last_quantity=volume,
                change=0.0,
                raw_data=raw_data or {}
            )
            
            # Publish in current event loop
            self.publish_event(quote_event)
            self._logger.debug(f"Published quote async for {symbol}: LTP={ltp}, Volume={volume}")
            
        except Exception as e:
            self._logger.error(f"Error publishing quote async for {symbol}: {e}")
    
    def get_normalizer(self) -> QuoteNormalizer:
        """Get the quote normalizer instance."""
        return self._quote_normalizer
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the streamer."""
        return {
            'name': self.name,
            'is_running': self._is_running,
            'symbols': self.symbols,
            'thread_pool_stats': self._thread_manager.get_pool_stats().get('streamer', {}),
            'active_async_tasks': len([t for t in self._async_tasks if not t.done()])
        }
    
    # Abstract methods - subclasses must implement these
    @abstractmethod
    def _setup_connection(self):
        """Setup the connection to the data source."""
        pass
    
    @abstractmethod
    def _run_connection(self):
        """Run the main connection loop."""
        pass
    
    @abstractmethod
    def _cleanup_connection(self):
        """Clean up the connection."""
        pass
    
    # Optional async methods - subclasses can implement these
    async def _run_connection_async(self):
        """Optional async version of connection loop."""
        # Default implementation runs sync version in executor
        await asyncio.get_event_loop().run_in_executor(None, self._run_connection)

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import threading
from datetime import datetime

from src.logger_factory import get_logger
from src.core.event_bus import Publisher
from .quote_normalizer import QuoteNormalizer
from .events import QuoteEvent


class BaseStreamer(Publisher, ABC):
    """
    Abstract base class for all market data streamers.
    
    This class implements the Template Method pattern where the overall
    streaming workflow is defined, but specific implementation details
    are left to subclasses.
    """
    
    def __init__(self, symbols: List[str], name: str = None):
        super().__init__()
        self.symbols = symbols
        self.name = name or self.__class__.__name__
        self._logger = get_logger(self.name)
        self._is_running = False
        self._connection_thread = None
        self._quote_normalizer = QuoteNormalizer()
        self._symbol_mapping = {}  # Map exchange symbols to our standard symbols
        
        self._logger.info(f"{self.name} initialized with symbols: {symbols}")
    
    def add_symbol_mapping(self, exchange_symbol: str, standard_symbol: str):
        """Map exchange-specific symbol to standard symbol format."""
        self._symbol_mapping[exchange_symbol] = standard_symbol
    
    def get_standard_symbol(self, exchange_symbol: str) -> str:
        """Get standard symbol from exchange symbol."""
        return self._symbol_mapping.get(exchange_symbol, exchange_symbol)
    
    def start(self):
        """Start the streaming service."""
        if self._is_running:
            self._logger.warning(f"{self.name} is already running")
            return
        
        self._logger.info(f"Starting {self.name}...")
        self._is_running = True
        
        try:
            self._setup_connection()
            self._connection_thread = threading.Thread(
                target=self._run_connection, 
                daemon=True,
                name=f"{self.name}-Connection"
            )
            self._connection_thread.start()
            self._logger.info(f"{self.name} started successfully")
        except Exception as e:
            self._logger.error(f"Failed to start {self.name}: {e}")
            self._is_running = False
            raise
    
    def stop(self):
        """Stop the streaming service."""
        if not self._is_running:
            return
        
        self._logger.info(f"Stopping {self.name}...")
        self._is_running = False
        
        try:
            self._cleanup_connection()
            if self._connection_thread and self._connection_thread.is_alive():
                self._connection_thread.join(timeout=5.0)
            self._logger.info(f"{self.name} stopped successfully")
        except Exception as e:
            self._logger.error(f"Error stopping {self.name}: {e}")
    
    def is_running(self) -> bool:
        """Check if streamer is running."""
        return self._is_running
    
    # Template methods - subclasses must implement these
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
    
    @abstractmethod
    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> QuoteEvent:
        """Normalize raw exchange data to standardized QuoteEvent."""
        pass
    
    # Common functionality for all streamers
    def _process_raw_quote(self, raw_data: Dict[str, Any], exchange_symbol: str):
        """
        Process raw quote data from exchange and publish standardized QuoteEvent.
        This is the main method that ensures consistency across all streamers.
        """
        try:
            # Get standard symbol
            standard_symbol = self.get_standard_symbol(exchange_symbol)
            
            # Normalize the raw data to QuoteEvent
            quote_event = self._normalize_raw_data(raw_data, standard_symbol)
            
            # Validate the quote event
            self._validate_quote_event(quote_event)
            
            # Store raw data for debugging
            self._store_raw_data(raw_data)
            
            # Publish the standardized event
            self.publish_event(quote_event)
            
            self._logger.debug(f"Processed quote for {standard_symbol}: LTP={quote_event.ltp}, LTQ={quote_event.ltq}")
            
        except Exception as e:
            self._logger.error(f"Error processing quote for {exchange_symbol}: {e}")
    
    def _validate_quote_event(self, quote_event: QuoteEvent):
        """Validate quote event before publishing."""
        if quote_event.ltp <= 0:
            raise ValueError(f"Invalid LTP: {quote_event.ltp}")
        if quote_event.ltq < 0:
            raise ValueError(f"Invalid LTQ: {quote_event.ltq}")
        if not quote_event.symbol:
            raise ValueError("Symbol cannot be empty")
    
    def _store_raw_data(self, raw_data: Dict[str, Any]):
        """Store raw data for debugging (optional implementation)."""
        # Subclasses can override this for specific storage needs
        pass
    
    def _handle_connection_error(self, error: Exception):
        """Handle connection errors."""
        self._logger.error(f"Connection error in {self.name}: {error}")
        # Subclasses can override for specific error handling
    
    def _handle_data_error(self, error: Exception, raw_data: Dict[str, Any]):
        """Handle data processing errors."""
        self._logger.error(f"Data processing error in {self.name}: {error}")
        self._logger.debug(f"Raw data that caused error: {raw_data}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the streamer."""
        return {
            'name': self.name,
            'is_running': self._is_running,
            'symbols': self.symbols,
            'symbol_mapping': self._symbol_mapping,
            'thread_alive': self._connection_thread.is_alive() if self._connection_thread else False
        }

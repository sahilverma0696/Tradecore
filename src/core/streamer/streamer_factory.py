"""Factory for creating different types of market data streamers."""
from typing import Dict, Any, List, Union
from src.logger_factory import get_logger
from .base_streamer import BaseStreamer


class StreamerFactory:
    """Factory class for creating market data streamers."""
    
    _streamer_registry = {}
    
    @classmethod
    def register_streamer(cls, streamer_type: str, streamer_class):
        """Register a streamer class with the factory."""
        if not issubclass(streamer_class, BaseStreamer):
            raise ValueError("Streamer class must inherit from BaseStreamer")
        cls._streamer_registry[streamer_type.lower()] = streamer_class
    
    @classmethod
    def create_streamer(cls, streamer_type: str, symbols: List[Union[str, int]], 
                       config: Dict[str, Any] = None) -> BaseStreamer:
        """
        Create a streamer instance based on type and configuration.
        
        Args:
            streamer_type: Type of streamer ('zerodha', 'offline', 'binance')
            symbols: List of symbols to stream
            config: Configuration dictionary for the streamer
            
        Returns:
            BaseStreamer: Configured streamer instance
        """
        logger = get_logger("StreamerFactory")
        config = config or {}
        
        streamer_type = streamer_type.lower()
        
        if streamer_type not in cls._streamer_registry:
            available = list(cls._streamer_registry.keys())
            raise ValueError(f"Unknown streamer type: {streamer_type}. Available: {available}")
        
        streamer_class = cls._streamer_registry[streamer_type]
        
        try:
            # Convert symbols to appropriate format for each streamer type
            if streamer_type == 'offline':
                str_symbols = [str(s) for s in symbols]
                return streamer_class(
                    symbols=str_symbols,
                    base_price=config.get('base_price', 18500.0),
                    tick_interval=config.get('tick_interval', 1.0)
                )
            else:
                # For other streamers, pass symbols and config as-is
                return streamer_class(symbols=symbols, **config)
                
        except Exception as e:
            logger.error(f"Failed to create {streamer_type} streamer: {e}")
            raise
    
    @classmethod
    def get_available_streamers(cls) -> List[str]:
        """Get list of available streamer types."""
        return list(cls._streamer_registry.keys())
    
    @classmethod
    def is_streamer_available(cls, streamer_type: str) -> bool:
        """Check if a streamer type is available."""
        return streamer_type.lower() in cls._streamer_registry


# Register built-in streamers
def _register_built_in_streamers():
    """Register all built-in streamer types."""
    logger = get_logger("StreamerFactory")
    
    # Register Offline streamer
    try:
        from .offline_streamer import OfflineStreamer
        StreamerFactory.register_streamer('offline', OfflineStreamer)
        logger.info("Registered OfflineStreamer")
    except ImportError as e:
        logger.warning(f"Could not register OfflineStreamer: {e}")
    
    # Register other streamers (if available)
    try:
        from src.market.zerodha.zerodha_streamer import ZerodhaStreamer
        StreamerFactory.register_streamer('zerodha', ZerodhaStreamer)
        logger.info("Registered ZerodhaStreamer")
    except ImportError as e:
        logger.debug(f"ZerodhaStreamer not available: {e}")


# Auto-register built-in streamers when module is imported
_register_built_in_streamers()
        )
    
    @classmethod
    def _create_binance_streamer(cls, streamer_class, symbols: List[Union[str, int]], 
                                config: Dict[str, Any]):
        """Create Binance streamer with specific configuration."""
        # Convert symbols to strings for Binance
        str_symbols = [str(s) for s in symbols]
        
        return streamer_class(
            symbols=str_symbols,
            **config
        )
    
    @classmethod
    def get_available_streamers(cls) -> List[str]:
        """Get list of available streamer types."""
        return list(cls._streamer_registry.keys())
    
    @classmethod
    def is_streamer_available(cls, streamer_type: str) -> bool:
        """Check if a streamer type is available."""
        return streamer_type.lower() in cls._streamer_registry


# Register built-in streamers
def _register_built_in_streamers():
    """Register all built-in streamer types."""
    logger = get_logger("StreamerFactory")
    
    # Register Zerodha streamer
    try:
        from .zerodha_streamer import ZerodhaStreamer
        StreamerFactory.register_streamer('zerodha', ZerodhaStreamer)
        logger.info("Registered ZerodhaStreamer")
    except ImportError as e:
        logger.warning(f"Could not register ZerodhaStreamer: {e}")
    
    # Register Offline streamer
    try:
        from .offline_streamer import OfflineStreamer
        StreamerFactory.register_streamer('offline', OfflineStreamer)
        logger.info("Registered OfflineStreamer")
    except ImportError as e:
        logger.warning(f"Could not register OfflineStreamer: {e}")
    
    # Register Binance streamer (if available)
    try:
        from src.market.binance.binance_streamer import BinanceStreamer
        StreamerFactory.register_streamer('binance', BinanceStreamer)
        logger.info("Registered BinanceStreamer")
    except ImportError as e:
        logger.debug(f"BinanceStreamer not available: {e}")


# Auto-register built-in streamers when module is imported
_register_built_in_streamers()

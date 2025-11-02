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
            # Create streamer based on type with appropriate configuration
            if streamer_type == 'offline':
                return cls._create_offline_streamer(streamer_class, symbols, config)
            elif streamer_type == 'zerodha':
                return cls._create_zerodha_streamer(streamer_class, symbols, config)
            elif streamer_type == 'binance':
                return cls._create_binance_streamer(streamer_class, symbols, config)
            elif streamer_type == 'upstox':
                return cls._create_upstox_streamer(streamer_class, symbols, config)
            else:
                # Generic creation for other streamers
                return streamer_class(symbols=symbols, **config)
                
        except Exception as e:
            logger.error(f"Failed to create {streamer_type} streamer: {e}")
            raise
    
    @classmethod
    def _create_offline_streamer(cls, streamer_class, symbols: List[Union[str, int]], 
                                config: Dict[str, Any]):
        """Create offline streamer with specific configuration."""
        str_symbols = [str(s) for s in symbols]
        return streamer_class(
            symbols=str_symbols,
            base_price=config.get('base_price', 18500.0),
            tick_interval=config.get('tick_interval', 1.0)
        )
    
    @classmethod
    def _create_zerodha_streamer(cls, streamer_class, symbols: List[Union[str, int]], 
                                config: Dict[str, Any]):
        """Create Zerodha streamer with specific configuration."""
        int_symbols = [int(s) for s in symbols]
        return streamer_class(
            symbols=int_symbols,
            api_key=config.get('api_key'),
            api_secret=config.get('api_secret'),
            name_symbol=config.get('name_symbol', 'UNKNOWN'),
            paper_trade=config.get('paper_trade', True)
        )
    
    @classmethod
    def _create_binance_streamer(cls, streamer_class, symbols: List[Union[str, int]], 
                                config: Dict[str, Any]):
        """Create Binance streamer with specific configuration."""
        str_symbols = [str(s) for s in symbols]
        
        # Pass all relevant config parameters to BinanceStreamer
        return streamer_class(
            symbols=str_symbols,
            name_symbol=config.get('name_symbol'),
            reconnect_attempts=config.get('reconnect_attempts', 3),
            reconnect_delay=config.get('reconnect_delay', 5.0),
            stream_timeout=config.get('stream_timeout', 60),
            ping_interval=config.get('ping_interval', 180),
            testnet=config.get('testnet', False)
        )
        
    @classmethod
    def _create_upstox_streamer(cls, streamer_class, symbols: List[Union[str, int]], 
                                config: Dict[str, Any]):
        """Create Upstox streamer with specific configuration."""
        str_symbols = [str(s) for s in symbols]
        
        # Pass all relevant config parameters to UpstoxStreamer
        return streamer_class(
            symbols=str_symbols,
            access_token=config.get('access_token'),
            name_symbol=config.get('name_symbol', 'UPSTOX')
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
    
    # Register Offline streamer
    try:
        from .offline_streamer import OfflineStreamer
        StreamerFactory.register_streamer('offline', OfflineStreamer)
        logger.info("Registered OfflineStreamer")
    except ImportError as e:
        logger.warning(f"Could not register OfflineStreamer: {e}")
    
    # Register Zerodha streamer
    try:
        from src.core.streamer.zerodha_streamer import ZerodhaStreamer
        StreamerFactory.register_streamer('zerodha', ZerodhaStreamer)
        logger.info("Registered ZerodhaStreamer")
    except ImportError as e:
        logger.debug(f"ZerodhaStreamer not available: {e}")
    
    # Register Binance streamer (from core.streamer directory)
    try:
        from src.core.streamer.binance_streamer import BinanceStreamer
        StreamerFactory.register_streamer('binance', BinanceStreamer)
        logger.info("Registered BinanceStreamer")
    except ImportError as e:
        logger.debug(f"BinanceStreamer not available: {e}")
    
    # Register Upstox streamer (if available)
    try:
        from src.core.streamer.upstox_streamer import UpstoxStreamer
        StreamerFactory.register_streamer('upstox', UpstoxStreamer)
        logger.info("Registered UpstoxStreamer")
    except ImportError as e:
        logger.debug(f"UpstoxStreamer not available: {e}")


# Auto-register built-in streamers when module is imported
_register_built_in_streamers()

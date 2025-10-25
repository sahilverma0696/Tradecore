from typing import Dict, Any, Optional
from .base_executor import BaseExecutor
from src.logger_factory import get_logger

# Import broker executors with fallback handling
try:
    from .zerodha_executor import ZerodhaExecutor
except ImportError:
    ZerodhaExecutor = None

try:
    from .binance_executor import BinanceExecutor
except ImportError:
    BinanceExecutor = None

try:
    from .upstox_executor import UpstoxExecutor
except ImportError:
    UpstoxExecutor = None


class ExecutorFactory:
    """Factory for creating executor instances based on broker type."""
    
    EXECUTOR_CLASSES = {}
    
    # Add broker executors if available
    if ZerodhaExecutor:
        EXECUTOR_CLASSES['zerodha'] = ZerodhaExecutor
    if BinanceExecutor:
        EXECUTOR_CLASSES['binance'] = BinanceExecutor
    if UpstoxExecutor:
        EXECUTOR_CLASSES['upstox'] = UpstoxExecutor
    
    @classmethod
    def create_executor(
        cls, 
        broker: str, 
        client=None, 
        paper_trade: bool = True, 
        config: Optional[Dict[str, Any]] = None
    ) -> BaseExecutor:
        """
        Create an executor instance for the specified broker.
        
        Args:
            broker: Broker name ('mock', 'zerodha', 'binance', 'upstox')
            client: Broker-specific client instance
            paper_trade: Whether to enable paper trading
            config: Broker-specific configuration
            
        Returns:
            BaseExecutor: Executor instance for the specified broker
            
        Raises:
            ValueError: If broker is not supported
        """
        broker = broker.lower()
        
        if broker not in cls.EXECUTOR_CLASSES:
            supported_brokers = ', '.join(cls.EXECUTOR_CLASSES.keys())
            raise ValueError(f"Unsupported broker: {broker}. Supported brokers: {supported_brokers}")
        
        executor_class = cls.EXECUTOR_CLASSES[broker]
        logger = get_logger("ExecutorFactory")
        
        logger.info(f"Creating {broker} executor - Paper Trade: {paper_trade}")
        
        # Handle MockExecutor which doesn't need client parameter
        
        return executor_class(
            client=client,
            paper_trade=paper_trade,
            logger=logger,
            config=config or {}
        )
    
    @classmethod
    def get_supported_brokers(cls) -> list:
        """Get list of supported brokers."""
        return list(cls.EXECUTOR_CLASSES.keys())
    
    @classmethod
    def register_executor(cls, broker: str, executor_class: type):
        """Register a new executor class for a broker."""
        if not issubclass(executor_class, BaseExecutor):
            raise ValueError("Executor class must inherit from BaseExecutor")
        
        cls.EXECUTOR_CLASSES[broker.lower()] = executor_class
        
        logger = get_logger("ExecutorFactory")
        logger.info(f"Registered new executor for broker: {broker}")

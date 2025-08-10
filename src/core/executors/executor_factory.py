from typing import Dict, Any, Optional
from .base_executor import BaseExecutor
from .zerodha_executor import ZerodhaExecutor
from .binance_executor import BinanceExecutor
from .upstox_executor import UpstoxExecutor
from src.logger_factory import get_logger


class ExecutorFactory:
    """Factory for creating executor instances based on broker type."""
    
    EXECUTOR_CLASSES = {
        'zerodha': ZerodhaExecutor,
        'binance': BinanceExecutor,
        'upstox': UpstoxExecutor,
    }
    
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
            broker: Broker name ('zerodha', 'binance', 'upstox')
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
        logger = get_logger(f"ExecutorFactory")
        
        logger.info(f"Creating {broker} executor - Paper Trade: {paper_trade}")
        
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

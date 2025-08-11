"""
Order execution module containing all executor implementations.
"""

from .base_executor import BaseExecutor
from .mock_executor import MockExecutor
from .executor_factory import ExecutorFactory

# Import broker-specific executors if they exist
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

__all__ = [
    'BaseExecutor',
    'MockExecutor', 
    'ExecutorFactory'
]

# Add broker executors to exports if available
if ZerodhaExecutor:
    __all__.append('ZerodhaExecutor')
if BinanceExecutor:
    __all__.append('BinanceExecutor')
if UpstoxExecutor:
    __all__.append('UpstoxExecutor')

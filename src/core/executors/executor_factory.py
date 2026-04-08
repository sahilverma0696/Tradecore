"""Factory for creating order executors."""
from typing import Any, Dict, List

from src.logger_factory import get_logger
from .base_executor import BaseExecutor


class ExecutorFactory:
    """
    Registry + factory for executor creation.

    Executors are registered at module import time. Credentials are read
    from trading_config.json; system_config carries only behaviour config.

    The special type 'paper' creates any executor with paper_trade=True
    and no broker client — useful for simulation.
    """

    _registry: Dict[str, type] = {}
    _logger = get_logger("ExecutorFactory")

    @classmethod
    def register(cls, name: str, klass):
        if not issubclass(klass, BaseExecutor):
            raise ValueError(f"{klass} must subclass BaseExecutor")
        cls._registry[name.lower()] = klass
        cls._logger.info(f"Registered executor: {name}")

    @classmethod
    def create_executor(
        cls,
        executor_type: str,
        config: Dict[str, Any] = None,
    ) -> BaseExecutor:
        """
        Create an executor.

        executor_type  – 'paper', 'binance', 'zerodha', 'upstox'
        config         – the executor-type block from system_config
        """
        key = executor_type.lower()

        # 'paper' is a virtual type: any executor run in paper-trade mode
        # We use BinanceExecutor (no client needed for paper) as the paper impl.
        if key == "paper":
            return cls._build_paper(config or {})

        if key not in cls._registry:
            raise ValueError(
                f"Unknown executor '{executor_type}'. "
                f"Available: {list(cls._registry)}"
            )

        config = config or {}
        klass = cls._registry[key]
        creds = cls._get_credentials(key)

        try:
            return cls._build(key, klass, config, creds)
        except Exception as e:
            cls._logger.error(f"Failed to create {executor_type} executor: {e}")
            raise

    @classmethod
    def _build_paper(cls, config: Dict[str, Any]) -> BaseExecutor:
        """Paper executor — no real broker client, always paper_trade=True."""
        # Use BinanceExecutor as the paper implementation (client=None → paper path)
        key = "binance"
        if key in cls._registry:
            klass = cls._registry[key]
        else:
            # Fallback: try any registered executor
            if not cls._registry:
                raise RuntimeError("No executors registered; cannot create paper executor")
            klass = next(iter(cls._registry.values()))

        return klass(client=None, paper_trade=True, config=config)

    @classmethod
    def _build(cls, key: str, klass, config: Dict[str, Any], creds: Dict[str, Any]) -> BaseExecutor:
        if key == "binance":
            try:
                from binance.client import Client
                client = Client(
                    api_key=creds.get("api_key", ""),
                    api_secret=creds.get("api_secret", ""),
                    testnet=config.get("test_mode", True),
                )
            except Exception:
                client = None
                cls._logger.warning("Binance client unavailable — falling back to paper mode")
            return klass(client=client, paper_trade=(client is None), config=config)

        if key == "zerodha":
            try:
                from kiteconnect import KiteConnect
                client = KiteConnect(api_key=creds.get("api_key", ""))
                client.set_access_token(creds.get("access_token", ""))
            except Exception:
                client = None
                cls._logger.warning("Zerodha client unavailable — falling back to paper mode")
            return klass(client=client, paper_trade=(client is None), config=config)

        if key == "upstox":
            try:
                import upstox_client
                cfg = upstox_client.Configuration()
                cfg.access_token = creds.get("access_token", "")
                client = upstox_client.OrderApiV3(upstox_client.ApiClient(cfg))
            except Exception:
                client = None
                cls._logger.warning("Upstox client unavailable — falling back to paper mode")
            return klass(client=client, paper_trade=(client is None), config=config)

        # Generic fallback
        return klass(client=None, paper_trade=True, config=config)

    @classmethod
    def _get_credentials(cls, broker: str) -> Dict[str, Any]:
        try:
            from src.config_manager import ConfigManager
            return ConfigManager().get_value(f"credentials.{broker}") or {}
        except Exception:
            return {}

    @classmethod
    def available(cls) -> List[str]:
        return list(cls._registry) + ["paper"]

    @classmethod
    def is_available(cls, executor_type: str) -> bool:
        return executor_type.lower() in cls._registry or executor_type.lower() == "paper"


# ---------------------------------------------------------------------------
# Auto-register built-in executors
# ---------------------------------------------------------------------------

def _register_builtins():
    try:
        from .binance_executor import BinanceExecutor
        ExecutorFactory.register("binance", BinanceExecutor)
    except Exception as e:
        get_logger("ExecutorFactory").debug(f"BinanceExecutor unavailable: {e}")

    try:
        from .zerodha_executor import ZerodhaExecutor
        ExecutorFactory.register("zerodha", ZerodhaExecutor)
    except Exception as e:
        get_logger("ExecutorFactory").debug(f"ZerodhaExecutor unavailable: {e}")

    try:
        from .upstox_executor import UpstoxExecutor
        ExecutorFactory.register("upstox", UpstoxExecutor)
    except Exception as e:
        get_logger("ExecutorFactory").debug(f"UpstoxExecutor unavailable: {e}")


_register_builtins()

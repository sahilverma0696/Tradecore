"""Factory for creating market data streamers."""
from typing import Any, Dict, List, Union

from src.logger_factory import get_logger
from .base_streamer import BaseStreamer


class StreamerFactory:
    """
    Registry + factory for streamer creation.

    Streamers are registered at module import time. Creation reads
    credentials from trading_config.json so system_config only carries
    connection/behaviour settings (reconnect, timeout, etc.).
    """

    _registry: Dict[str, type] = {}
    _logger = get_logger("StreamerFactory")

    @classmethod
    def register(cls, name: str, klass):
        if not issubclass(klass, BaseStreamer):
            raise ValueError(f"{klass} must subclass BaseStreamer")
        cls._registry[name.lower()] = klass
        cls._logger.info(f"Registered streamer: {name}")

    # kept for backward-compat with old call sites
    register_streamer = register

    @classmethod
    def create_streamer(
        cls,
        streamer_type: str,
        symbols: List[Union[str, int]],
        config: Dict[str, Any] = None,
    ) -> BaseStreamer:
        """
        Create a streamer.

        config  – the streamer-type block from system_config
                  (e.g. system_config.streamer.configs.binance)
        Credentials for live brokers are read from trading_config.json
        under credentials.{type}.
        """
        key = streamer_type.lower()
        if key not in cls._registry:
            raise ValueError(
                f"Unknown streamer '{streamer_type}'. "
                f"Available: {list(cls._registry)}"
            )

        config = config or {}
        klass  = cls._registry[key]

        # Read credentials from trading config (not from system config)
        creds = cls._get_credentials(key)

        try:
            return cls._build(key, klass, symbols, config, creds)
        except Exception as e:
            cls._logger.error(f"Failed to create {streamer_type} streamer: {e}")
            raise

    @classmethod
    def _build(cls, key, klass, symbols, config, creds):
        str_syms = [str(s) for s in symbols]
        int_syms = []
        try:
            int_syms = [int(s) for s in symbols]
        except (ValueError, TypeError):
            pass

        if key == "offline":
            return klass(
                symbols=str_syms,
                base_price=config.get("base_price", 18500.0),
                tick_interval=config.get("tick_interval", 1.0),
            )

        if key == "binance":
            return klass(
                symbols=str_syms,
                reconnect_attempts=config.get("reconnect_attempts", 5),
                reconnect_delay=config.get("reconnect_delay", 2.0),
                stream_timeout=config.get("stream_timeout", 60),
                testnet=config.get("testnet", False),
            )

        if key == "zerodha":
            streamer = klass(
                symbols=int_syms or str_syms,
                api_key=creds.get("api_key", ""),
                access_token=creds.get("access_token", ""),
                name_symbol=config.get("name_symbol", "ZERODHA"),
            )
            # init_kite is called here if access_token present
            if creds.get("access_token"):
                streamer.init_kite(creds["access_token"])
            return streamer

        if key == "upstox":
            return klass(
                symbols=str_syms,
                access_token=creds.get("access_token", ""),
                name_symbol=config.get("name_symbol", "UPSTOX"),
            )

        # Generic fallback for custom/registered streamers
        return klass(symbols=str_syms, **config)

    @classmethod
    def _get_credentials(cls, broker: str) -> Dict[str, Any]:
        try:
            from src.config_manager import ConfigManager
            return ConfigManager().get_value(f"credentials.{broker}") or {}
        except Exception:
            return {}

    @classmethod
    def available(cls) -> List[str]:
        return list(cls._registry)

    # backward-compat alias
    @classmethod
    def get_available_streamers(cls) -> List[str]:
        return cls.available()

    @classmethod
    def is_streamer_available(cls, streamer_type: str) -> bool:
        return streamer_type.lower() in cls._registry


# ---------------------------------------------------------------------------
# Auto-register built-in streamers
# ---------------------------------------------------------------------------

def _register_builtins():
    try:
        from .offline_streamer import OfflineStreamer
        StreamerFactory.register("offline", OfflineStreamer)
    except Exception as e:
        get_logger("StreamerFactory").warning(f"OfflineStreamer unavailable: {e}")

    try:
        from .binance_streamer import BinanceStreamer
        StreamerFactory.register("binance", BinanceStreamer)
    except Exception as e:
        get_logger("StreamerFactory").debug(f"BinanceStreamer unavailable: {e}")

    try:
        from .zerodha_streamer import ZerodhaStreamer
        StreamerFactory.register("zerodha", ZerodhaStreamer)
    except Exception as e:
        get_logger("StreamerFactory").debug(f"ZerodhaStreamer unavailable: {e}")

    try:
        from .upstox_streamer import UpstoxStreamer
        StreamerFactory.register("upstox", UpstoxStreamer)
    except Exception as e:
        get_logger("StreamerFactory").debug(f"UpstoxStreamer unavailable: {e}")


_register_builtins()

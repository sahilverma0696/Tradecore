"""High-level wiring for VWAP trading system with thread pool management."""
import time
import signal
import sys
from datetime import datetime
from threading import Event

from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.system_config_manager import SystemConfigManager
from src.core.thread_manager import ThreadManager, ThreadPoolType

# Core components
from src.core.event_bus import EventBus
from src.core.candle_maker import CandleMaker
from src.core.order_manager import OrderManager

# Strategy components
from src.strategies.vwap_strategy import VwapStrategy
from src.strategies.exit_manager import ExitManager

# Factory imports for dynamic component creation
from src.core.executors.executor_factory import ExecutorFactory
from src.core.streamer.base_streamer import BaseStreamer

# Specific streamer imports for factory registration
from src.core.streamer.offline_streamer import OfflineStreamer
from src.market.zerodha.zerodha_streamer import ZerodhaStreamer

logger = get_logger("MAIN")

# Global shutdown event for graceful cleanup
shutdown_event = Event()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received, initiating graceful shutdown...")
    shutdown_event.set()

def initialize_thread_pools():
    """Initialize thread pool manager."""
    logger.info("Initializing thread pool system...")
    
    try:
        thread_manager = ThreadManager()
        thread_manager.initialize_pools()
        
        # Log thread pool statistics
        stats = thread_manager.get_pool_stats()
        for pool_name, pool_stats in stats.items():
            logger.info(f"Thread pool '{pool_name}': {pool_stats['max_workers']} workers")
        
        logger.info("✅ Thread pools initialized successfully")
        return thread_manager
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize thread pools: {e}")
        raise

def initialize_event_bus():
    """Initialize EventBus singleton."""
    logger.info("Initializing EventBus...")
    
    try:
        event_bus = EventBus()
        logger.info("✅ EventBus initialized successfully")
        return event_bus
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize EventBus: {e}")
        raise

def create_streamer(system_config: SystemConfigManager, trading_config: ConfigManager) -> BaseStreamer:
    """Create streamer based on system configuration."""
    logger.info("Creating streamer based on configuration...")
    
    try:
        # Get streamer configuration
        streamer_config = system_config.get_streamer_config()
        streamer_type = streamer_config['type']
        config = streamer_config['config']
        
        # Get symbols from trading config
        symbols = trading_config.get().get('symbols', [])
        name_symbol = trading_config.get().get('name_symbol', 'UNKNOWN')
        
        if not symbols:
            raise ValueError("No symbols configured for streaming")
        
        # Create streamer based on type
        if streamer_type == 'offline':
            logger.info("Creating OfflineStreamer for testing")
            streamer = OfflineStreamer(
                symbols=[str(s) for s in symbols],
                base_price=config.get('base_price', 18500.0),
                tick_interval=config.get('tick_interval', 1.0)
            )
            
        elif streamer_type == 'zerodha':
            logger.info("Creating ZerodhaStreamer for live trading")
            # Get API credentials from trading config
            api_key = trading_config.get().get('api_key')
            api_secret = trading_config.get().get('api_secret')
            paper_trade = trading_config.get().get('paper_trade', True)
            
            if not api_key or not api_secret:
                raise ValueError("Zerodha API credentials not found in trading config")
            
            streamer = ZerodhaStreamer(
                symbols=[int(s) for s in symbols],
                api_key=api_key,
                api_secret=api_secret,
                name_symbol=name_symbol,
                paper_trade=paper_trade
            )
            
        else:
            raise ValueError(f"Unsupported streamer type: {streamer_type}")
        
        logger.info(f"✅ Created {streamer_type} streamer with {len(symbols)} symbols")
        return streamer
        
    except Exception as e:
        logger.error(f"❌ Failed to create streamer: {e}")
        raise

def create_executor(system_config: SystemConfigManager):
    """Create executor using factory pattern."""
    logger.info("Creating executor using factory pattern...")
    
    try:
        # Get executor configuration
        exec_config = system_config.get_executioner_config()
        exec_type = exec_config['type']
        config = exec_config['config']
        
        # Create executor using factory
        executor = ExecutorFactory.create_executor(
            broker=exec_type,
            config=config
        )
        
        logger.info(f"✅ Created {exec_type} executor")
        return executor
        
    except Exception as e:
        logger.error(f"❌ Failed to create executor: {e}")
        raise

def initialize_core_components(trading_config: ConfigManager):
    """Initialize core trading components."""
    logger.info("Initializing core components...")
    
    try:
        # Initialize CandleMaker
        logger.info("Initializing CandleMaker...")
        candle_maker = CandleMaker()
        
        # Initialize OrderManager  
        logger.info("Initializing OrderManager...")
        order_manager = OrderManager()
        
        logger.info("✅ Core components initialized successfully")
        return candle_maker, order_manager
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize core components: {e}")
        raise

def initialize_strategy_components(trading_config: ConfigManager):
    """Initialize strategy components."""
    logger.info("Initializing strategy components...")
    
    try:
        config = trading_config.get()
        
        # Initialize VWAP Strategy
        logger.info("Initializing VwapStrategy...")
        vwap_strategy = VwapStrategy(config=config)
        
        # Initialize Exit Manager
        logger.info("Initializing ExitManager...")
        exit_manager = ExitManager(
            exit_steps=config.get('exit_steps', []),
            reterival_exit=config.get('reterival_exit', 0.01),
            default_quantity=config.get('default_quantity', 75),
            market_close=config.get('market_close_time')
        )
        
        logger.info("✅ Strategy components initialized successfully")
        return vwap_strategy, exit_manager
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize strategy components: {e}")
        raise

def wire_components(order_manager, exit_manager, executor):
    """Wire components together."""
    logger.info("Wiring components together...")
    
    try:
        # Wire exit manager to order manager
        order_manager.set_exit_manager(exit_manager)
        
        # Wire executor to order manager
        order_manager.register_handler(executor.execute_order)
        
        logger.info("✅ Components wired successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to wire components: {e}")
        raise

def start_streaming(streamer, system_config: SystemConfigManager):
    """Start market data streaming."""
    logger.info("Starting market data streaming...")
    
    try:
        # Check if async streaming is enabled
        async_enabled = system_config.get('streamer.async_enabled', False)
        
        if async_enabled and hasattr(streamer, 'start_async'):
            logger.info("Starting streamer with async support...")
            future = streamer.start_async()
            logger.info("✅ Async streaming started")
            return future
        else:
            logger.info("Starting streamer with standard threading...")
            streamer.start()
            logger.info("✅ Standard streaming started")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to start streaming: {e}")
        raise

def main():
    """Main trading system entry point with thread pool management."""
    logger.info("🚀 Starting VWAP Algorithmic Trading System...")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    thread_manager = None
    streamer = None
    
    try:
        # Step 1: Initialize thread pool system
        thread_manager = initialize_thread_pools()
        
        # Step 2: Initialize EventBus
        event_bus = initialize_event_bus()
        
        # Step 3: Load configurations
        logger.info("Loading configurations...")
        system_config = SystemConfigManager()
        trading_config = ConfigManager()
        
        logger.info(f"System mode: {system_config.get('system.mode', 'offline')}")
        logger.info(f"Streamer type: {system_config.get('streamer.type', 'offline')}")
        logger.info(f"Executor type: {system_config.get('executor.type', 'mock')}")
        
        # Step 4: Create components using factories
        streamer = create_streamer(system_config, trading_config)
        executor = create_executor(system_config)
        
        # Step 5: Initialize core components
        candle_maker, order_manager = initialize_core_components(trading_config)
        
        # Step 6: Initialize strategy components
        vwap_strategy, exit_manager = initialize_strategy_components(trading_config)
        
        # Step 7: Wire components together
        wire_components(order_manager, exit_manager, executor)
        
        # Step 8: Start market data streaming
        streaming_future = start_streaming(streamer, system_config)
        
        logger.info("🎯 System initialization complete!")
        logger.info("📊 All components are running and connected via EventBus")
        logger.info("🔄 Market data streaming active")
        
        # Main system monitoring loop
        logger.info("Entering main monitoring loop... Press Ctrl+C to stop")
        
        while not shutdown_event.is_set():
            try:
                # System health monitoring
                if thread_manager:
                    stats = thread_manager.get_pool_stats()
                    total_active = sum(pool.get('active_tasks', 0) for pool in stats.values())
                    
                    if total_active > 0:
                        logger.debug(f"Active tasks across all pools: {total_active}")
                
                # Check streamer status
                if streamer and hasattr(streamer, 'get_status'):
                    status = streamer.get_status()
                    if not status.get('is_running', False):
                        logger.warning("⚠️ Streamer is not running - may need restart")
                
                # Sleep and check for shutdown signal
                shutdown_event.wait(timeout=30.0)  # Check every 30 seconds
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                break
                
    except Exception as e:
        logger.error(f"💥 Critical error in main: {e}")
        return 1
        
    finally:
        # Graceful shutdown sequence
        logger.info("🛑 Initiating system shutdown sequence...")
        
        # Step 1: Stop streaming
        if streamer:
            try:
                logger.info("Stopping market data streamer...")
                streamer.stop()
                logger.info("✅ Streamer stopped")
            except Exception as e:
                logger.error(f"Error stopping streamer: {e}")
        
        # Step 2: Stop thread pools
        if thread_manager:
            try:
                logger.info("Shutting down thread pools...")
                thread_manager.shutdown(wait=True, timeout=10.0)
                logger.info("✅ Thread pools shutdown complete")
            except Exception as e:
                logger.error(f"Error shutting down thread pools: {e}")
        
        # Step 3: Final cleanup
        logger.info("✅ System shutdown complete")
        logger.info("👋 Thank you for using VWAP Trading System")
        
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

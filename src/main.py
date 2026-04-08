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
from src.core.candle.candle_maker import CandleMaker
from src.core.order_manager import OrderManager

# Strategy components
from src.strategies.vwap_strategy import VwapStrategy

# Factory imports for dynamic component creation
from src.core.executors.executor_factory import ExecutorFactory
from src.core.streamer.streamer_factory import StreamerFactory

from src.data_store.quote_event_db_subscriber import QuoteEventDBSubscriber

logger = get_logger("MAIN", console_output=True)

# Global shutdown event for graceful cleanup
shutdown_event = Event()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received, initiating graceful shutdown...")
    shutdown_event.set()

def load_configurations():
    """Load system and trading configurations."""
    logger.info("📋 Loading system configurations...")
    
    try:
        system_config = SystemConfigManager()
        trading_config = ConfigManager()
        
        logger.info(f"System mode: {system_config.get('system.mode')}")
        logger.info(f"Active streamer: {system_config.get_active_streamer()}")
        logger.info(f"Active executor: {system_config.get_active_executor()}")
        
        logger.info("✅ Configurations loaded successfully")
        return system_config, trading_config
        
    except Exception as e:
        logger.error(f"❌ Failed to load configurations: {e}")
        raise

def initialize_foundation():
    """Initialize the system foundation: thread pools and event bus."""
    logger.info("🏗️ Initializing system foundation...")
    
    # Step 1: Initialize thread pool system
    logger.info("1️⃣ Initializing thread pool system...")
    try:
        thread_manager = ThreadManager()
        thread_manager.initialize_pools()
        
        # Log thread pool statistics
        stats = thread_manager.get_pool_stats()
        for pool_name, pool_stats in stats.items():
            logger.info(f"   Thread pool '{pool_name}': {pool_stats['max_workers']} workers")
        
        logger.info("✅ Thread pools initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize thread pools: {e}")
        raise
    
    # Step 2: Initialize EventBus
    logger.info("2️⃣ Initializing EventBus communication layer...")
    try:
        event_bus = EventBus()
        logger.info("✅ EventBus initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize EventBus: {e}")
        raise
    
    logger.info("🎯 Foundation ready - Thread pools and EventBus operational")
    return thread_manager, event_bus

def create_and_register_components(system_config, trading_config):
    """Create all system components and register them with the event bus."""
    logger.info("🔧 Creating and registering system components...")
    
    components = {}
    
    try:
        # Create core components first
        logger.info("Creating core components...")
        
        # CandleMaker - subscribes to quotes, publishes candles
        components['candle_maker'] = CandleMaker()
        
        # OrderManager - subscribes to signals, manages orders (now with integrated exit logic)
        # logger.info("   📋 Creating OrderManager...")
        components['order_manager'] = OrderManager()
        # logger.info("   ✅ OrderManager registered for order lifecycle management with integrated exits")
        
        # Create strategy components
        logger.info("Creating strategy components...")
        config = trading_config.get()
        
        # VwapStrategy - subscribes to candles, publishes entry signals
        # logger.info("   💡 Creating VwapStrategy...")
        components['vwap_strategy'] = VwapStrategy(config=config)
        # logger.info("   ✅ VwapStrategy registered for candle → signal generation")
        
        components['quote_db_subscriber'] = QuoteEventDBSubscriber()
        
        # Create executor using factory
        logger.info("Creating executor...")
        exec_config = system_config.get_executioner_config()
        exec_type = exec_config['type']
        config_data = exec_config['config']
        
        logger.info(f"   ⚡ Creating {exec_type} executor...")
        components['executor'] = ExecutorFactory.create_executor(
            broker=exec_type,
            config=config_data
        )
        
        # Create streamer using factory
        logger.info("Creating market data streamer...")
        streamer_config = system_config.get_streamer_config()
        streamer_type = streamer_config['type']
        streamer_config_data = streamer_config['config']
        
        # Get symbols from main configuration for other streamers
        symbols = trading_config.get().get('symbols')
        if not symbols:
            logger.error("No symbols configured for streaming.")
            shutdown_event.set()
            raise RuntimeError("No symbols configured – cannot start streamer")
        
        logger.info(f"   📡 Creating {streamer_type} streamer...")
        components['streamer'] = StreamerFactory.create_streamer(
            streamer_type=streamer_type,
            symbols=symbols,
            config=streamer_config_data
        )
        logger.info(f"   ✅ {streamer_type} streamer created for market data")
        
        # Log subscription status
        from src.core.event_bus.events import QuoteEvent, CandleGenerated, EntrySignal
        logger.info("Event subscription summary:")
        event_bus = EventBus()
        logger.info(f"   QuoteEvent subscribers: {event_bus.get_subscriber_count(QuoteEvent)}")
        logger.info(f"   CandleGenerated subscribers: {event_bus.get_subscriber_count(CandleGenerated)}")
        logger.info(f"   EntrySignal subscribers: {event_bus.get_subscriber_count(EntrySignal)}")
        
        logger.info("✅ All components created and registered with EventBus")
        return components
        
    except Exception as e:
        logger.error(f"❌ Failed to create components: {e}")
        raise

def validate_system_wiring():
    """
    Pre-flight check: verify every critical event flow has its minimum
    number of subscribers before the streamer is allowed to start.

    If any flow is broken the system raises immediately rather than
    running silently with missing components.

    Critical wiring map
    -------------------
    QuoteEvent      -> CandleMaker + OrderManager            (min 2)
    CandleGenerated -> VwapStrategy + OrderManager           (min 2)
    EntrySignal     -> OrderManager                          (min 1)
    OrderEvent      -> Executor                              (min 1)
    """
    from src.core.event_bus.events import (
        QuoteEvent, CandleGenerated, EntrySignal, OrderEvent
    )

    REQUIRED: dict = {
        QuoteEvent:      (2, "CandleMaker + OrderManager"),
        CandleGenerated: (2, "VwapStrategy + OrderManager"),
        EntrySignal:     (1, "OrderManager"),
        OrderEvent:      (1, "Executor"),
    }

    event_bus = EventBus()
    failures = []
    ok = []

    for event_type, (min_count, expected) in REQUIRED.items():
        actual = event_bus.get_subscriber_count(event_type)
        if actual < min_count:
            failures.append(
                f"  MISSING  {event_type.__name__:<20} "
                f"got {actual}, need >={min_count}  ({expected})"
            )
        else:
            ok.append(
                f"  OK       {event_type.__name__:<20} "
                f"{actual} subscriber(s)  ({expected})"
            )

    logger.info("System wiring check:")
    for line in ok:
        logger.info(line)
    for line in failures:
        logger.error(line)

    if failures:
        raise RuntimeError(
            f"System wiring incomplete – {len(failures)} flow(s) not connected. "
            "Fix component registration before starting."
        )

    logger.info("All event flows connected – system ready to start")


def start_system_components(components, system_config):
    """Start all system components in proper order."""
    logger.info("🚀 Starting system components...")
    
    try:
        streamer = components['streamer']
        
        # Check if async streaming is enabled
        async_enabled = system_config.get('streamer.async_enabled', True)
        
        if async_enabled and hasattr(streamer, 'start_async'):
            logger.info("   🚀 Starting streamer with async support...")
            streaming_future = streamer.start_async()
            logger.info("   ✅ Async streaming started")
        else:
            logger.info("   🚀 Starting streamer with standard threading...")
            streamer.start()
            streaming_future = None
            logger.info("   ✅ Standard streaming started")
        
        # Log system status
        logger.info("📊 System component status:")
        logger.info(f"   📡 Streamer: {'Running' if streamer.is_running() else 'Stopped'}")
        logger.info(f"   📊 CandleMaker: Active (event-driven)")
        logger.info(f"   💡 VwapStrategy: Active (event-driven)")
        logger.info(f"   📋 OrderManager: Active (event-driven)")
        
        logger.info("✅ All system components started successfully")
        return streaming_future
        
    except Exception as e:
        logger.error(f"❌ Failed to start system components: {e}")
        raise

def run_monitoring_loop(components, thread_manager, streaming_future=None):
    """Run the main system monitoring loop."""
    logger.info("Entering main monitoring loop... Press Ctrl+C to stop")

    streamer = components.get('streamer')

    while not shutdown_event.is_set():
        try:
            # Check whether the async streamer task died unexpectedly
            if streaming_future is not None and streaming_future.done():
                exc = None
                try:
                    exc = streaming_future.exception()
                except Exception as e:
                    exc = e
                if exc is not None:
                    logger.error(f"Streamer task failed: {exc} – initiating shutdown")
                    shutdown_event.set()
                    break
                # Future completed cleanly (streamer ran to end) – treat as stop
                if not shutdown_event.is_set():
                    logger.warning("Streamer task ended without error – shutting down")
                    shutdown_event.set()
                    break

            # System health
            if thread_manager and thread_manager.is_alive():
                stats = thread_manager.get_pool_stats()
                total_active = sum(p.get('active_tasks', 0) for p in stats.values())
                if total_active > 0:
                    logger.debug(f"Active tasks across pools: {total_active}")

            # Check streamer is still alive
            if streamer and hasattr(streamer, 'get_status'):
                status = streamer.get_status()
                if not status.get('is_running', False):
                    logger.warning("Streamer is not running – may need restart")

            shutdown_event.wait(timeout=30.0)

        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            break

def shutdown_system(components, thread_manager):
    """Gracefully shutdown all system components."""
    logger.info("🛑 Initiating graceful system shutdown...")
    
    # Step 1: Stop streaming first
    streamer = components.get('streamer')
    if streamer:
        try:
            logger.info("   🛑 Stopping market data streamer...")
            streamer.stop()
            logger.info("   ✅ Streamer stopped")
        except Exception as e:
            logger.error(f"   ❌ Error stopping streamer: {e}")
    
    # Step 2: Allow components to process remaining events
    logger.info("   ⏳ Allowing components to process remaining events...")
    time.sleep(2.0)
    
    # Step 3: Stop thread pools
    if thread_manager:
        try:
            logger.info("   🛑 Shutting down thread pools...")
            thread_manager.shutdown(wait=True, timeout=10.0)
            logger.info("   ✅ Thread pools shutdown complete")
        except Exception as e:
            logger.error(f"   ❌ Error shutting down thread pools: {e}")
    
    logger.info("✅ System shutdown complete")
    logger.info("👋 Thank you for using VWAP Trading System")

def main():
    """Main trading system entry point with proper architectural flow."""
    logger.info("🚀 Starting VWAP Algorithmic Trading System...")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    thread_manager = None
    components = {}
    
    try:
        # PHASE 1: Load configurations
        system_config, trading_config = load_configurations()
        
        # PHASE 2: Initialize foundation (thread pools + event bus)
        thread_manager, event_bus = initialize_foundation()
        
        # PHASE 3: Create and register all components with event bus
        components = create_and_register_components(system_config, trading_config)

        # PHASE 4: Validate every critical event flow is wired before starting
        validate_system_wiring()

        # PHASE 5: Start all system components
        streaming_future = start_system_components(components, system_config)
        
        # logger.info("🎯 System initialization complete!")
        # logger.info("📊 All components operational and communicating via EventBus")
        # logger.info("🔄 Market data streaming and strategy processing active")
        
        # PHASE 6: Run monitoring loop
        run_monitoring_loop(components, thread_manager, streaming_future)
        
    except Exception as e:
        logger.error(f"💥 Critical error in main: {e}")
        return 1
        
    finally:
        # PHASE 7: Graceful shutdown
        shutdown_system(components, thread_manager)
        
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

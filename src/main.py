"""High-level wiring for VWAP trading system."""
import signal
from threading import Event

from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.system_config_manager import SystemConfigManager
from src.core.event_bus import EventBus

# Import all components
from src.core.candle.candle_maker import CandleMaker
from src.core.order_manager import OrderManager
from src.core.executors.mock_executioner import MockExecutioner
from src.strategies.vwap_strategy import VwapStrategy

# Import streamers based on system config
from src.market.offline.offline_streamer import OfflineStreamer

# Global shutdown event
shutdown_event = Event()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger = get_logger("Main")
    logger.info("Shutdown signal received, stopping all components...")
    shutdown_event.set()

def create_streamer(system_config: SystemConfigManager):
    """Create appropriate streamer based on system configuration."""
    logger = get_logger("Main")
    streamer_config = system_config.get_streamer_config()
    streamer_type = streamer_config['type']
    config = streamer_config['config']
    
    if streamer_type == 'offline':
        logger.info("Creating offline streamer")
        return OfflineStreamer(
            data_dir=config.get('data_dir', 'data'),
            playback_speed=config.get('playback_speed', 1.0)
        )
    elif streamer_type == 'zerodha':
        logger.info("Creating Zerodha streamer")
        # Import and create Zerodha streamer
        from src.market.zerodha.zerodha_streamer import ZerodhaStreamer
        return ZerodhaStreamer()
    elif streamer_type == 'binance':
        logger.info("Creating Binance streamer")
        # Import and create Binance streamer  
        from src.market.binance.binance_streamer import BinanceStreamer
        return BinanceStreamer()
    else:
        raise ValueError(f"Unknown streamer type: {streamer_type}")

def create_executioner(system_config: SystemConfigManager):
    """Create appropriate executioner based on system configuration."""
    logger = get_logger("Main")
    exec_config = system_config.get_executioner_config()
    exec_type = exec_config['type']
    config = exec_config['config']
    
    if exec_type == 'mock':
        logger.info("Creating mock executioner")
        executioner = MockExecutioner()
        if 'slippage_factor' in config:
            executioner.set_slippage_factor(config['slippage_factor'])
        return executioner
    elif exec_type == 'kite':
        logger.info("Creating Kite executioner")
        from src.core.executioner import KiteExecutioner
        return KiteExecutioner()
    elif exec_type == 'paper':
        logger.info("Creating paper executioner")
        from src.core.executioner import PaperExecutioner
        return PaperExecutioner()
    else:
        raise ValueError(f"Unknown executioner type: {exec_type}")

def main():
    """Main trading system entry point with system configuration support."""
    logger = get_logger("Main")
    logger.info("🚀 Starting Algorithmic Trading System...")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Load configurations
        system_config = SystemConfigManager()
        trading_config = ConfigManager()
        
        logger.info(f"System mode: {system_config.get('system.mode', 'offline')}")
        logger.info(f"Streamer type: {system_config.get('streamer.type', 'offline')}")
        logger.info(f"Executioner type: {system_config.get('executioner.type', 'mock')}")
        
        # Initialize EventBus (singleton)
        event_bus = EventBus()
        
        # Create components based on system configuration
        streamer = create_streamer(system_config)
        executioner = create_executioner(system_config)
        
        # Initialize core components
        candle_maker = CandleMaker()
        order_manager = OrderManager(executioner)
        strategy = VwapStrategy()
        
        logger.info("✅ All components initialized")
        
        # Start streaming market data
        symbols = trading_config.get('symbols', [])
        if symbols:
            if hasattr(streamer, 'start_streaming'):
                streamer.start_streaming(symbols)
            else:
                # For legacy streamers that use connect()
                streamer.connect()
            logger.info(f"📊 Started streaming for symbols: {symbols}")
        else:
            logger.warning("No symbols configured for streaming")
        
        # Main loop
        logger.info("🔄 System running... Press Ctrl+C to stop")
        
        while not shutdown_event.is_set():
            try:
                # System health check
                if hasattr(streamer, 'get_status'):
                    status = streamer.get_status()
                    if not status.get('is_streaming', False):
                        logger.warning("Streamer is not active")
                
                # Sleep and check for shutdown
                shutdown_event.wait(timeout=10.0)
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
                
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        
    finally:
        # Cleanup
        logger.info("🛑 Shutting down system...")
        
        # Stop streamer
        try:
            if hasattr(streamer, 'stop_streaming'):
                streamer.stop_streaming()
            elif hasattr(streamer, 'disconnect'):
                streamer.disconnect()
        except:
            pass
            
        # Stop other components
        try:
            if hasattr(order_manager, 'stop'):
                order_manager.stop()
        except:
            pass
            
        logger.info("✅ System shutdown complete")

if __name__ == "__main__":
    main()

# VWAP Algorithmic Trading System

A production-grade event-driven algorithmic trading system implementing VWAP (Volume Weighted Average Price) strategies for Indian markets (NSE F&O) and cryptocurrency markets.

## 🏗️ Architecture Overview

This system is built on a **thread-managed event-driven architecture** with the following core components:

### Thread Pool Management
- **ThreadManager**: Centralized singleton managing all thread pools
- **Segregated Pools**: Separate thread pools for different component types
- **Async Support**: Event loops for components requiring async operations
- **Configuration-Driven**: Thread pool sizes configurable via system_config.json

### Event-Driven Communication
- **EventBus**: Singleton message broker for all inter-component communication
- **Publisher/Subscriber Pattern**: Components inherit from mixins for event handling
- **Typed Events**: Strongly typed event system (QuoteEvent, CandleGenerated, etc.)

### Factory Pattern Components
- **Dynamic Creation**: Components created based on configuration files
- **Multiple Brokers**: Support for Zerodha, Binance, and mock trading
- **Extensible**: Easy to add new brokers and exchanges

## 🚀 Quick Start

### Prerequisites
```bash
pip install -r requirements.txt
```

### Configuration
1. Copy and configure trading settings:
```bash
cp trading_config.json.example trading_config.json
# Edit with your API keys and trading parameters
```

2. Copy and configure system settings:
```bash
cp system_config.json.example system_config.json
# Edit thread pool sizes and component types
```

### Running the System

#### Live Trading Mode
```bash
# Configure system_config.json with:
# "streamer": {"type": "zerodha"}
# "executor": {"type": "zerodha"}

python3 -m src.main
```

#### Paper Trading Mode
```bash
# Configure system_config.json with:
# "streamer": {"type": "zerodha"}
# "executor": {"type": "mock"}

python3 -m src.main
```

#### Offline Testing Mode
```bash
# Configure system_config.json with:
# "streamer": {"type": "offline"}
# "executor": {"type": "mock"}

python3 -m src.main
```

### Monitoring Dashboard
Run the CLI dashboard in a separate terminal:
```bash
python3 -m src.cli.cli_main          # Live dashboard
python3 -m src.cli.cli_main --demo   # Demo mode
```

## 🧪 Testing

### Running All Tests
```bash
# Run complete test suite
python3 -m unittest discover -s tests -v

# Run with coverage
python3 -m coverage run -m unittest discover -s tests
python3 -m coverage report -m
```

### Thread Manager Tests
```bash
# Core functionality tests
python3 -m unittest tests.test_thread_manager -v

# Performance tests
python3 -m unittest tests.test_thread_manager_performance -v

# Stress tests
python3 -m unittest tests.test_thread_manager_stress -v

# Run specific test methods
python3 -m unittest tests.test_thread_manager.TestThreadManager.test_singleton_pattern
python3 -m unittest tests.test_thread_manager.TestThreadManager.test_thread_safe_singleton
```

### Component Tests
```bash
# Event bus tests
python3 -m unittest tests.test_event_bus -v

# Factory pattern tests  
python3 -m unittest tests.test_executor_factory -v
python3 -m unittest tests.test_streamer_factory -v

# Integration tests
python3 -m unittest tests.test_vwap_flow -v
python3 -m unittest tests.test_candle_maker -v
```

### Performance Testing
```bash
# Thread manager performance under load
python3 -m unittest tests.test_thread_manager_performance.TestThreadManagerPerformance.test_high_volume_task_submission -v

# Concurrent pool usage
python3 -m unittest tests.test_thread_manager_performance.TestThreadManagerPerformance.test_concurrent_pool_usage -v

# Memory usage monitoring
python3 -m unittest tests.test_thread_manager_performance.TestThreadManagerPerformance.test_memory_usage_under_load -v
```

### Stress Testing
```bash
# Exception handling under load
python3 -m unittest tests.test_thread_manager_stress.TestThreadManagerStress.test_exception_handling_stress -v

# Thread pool saturation
python3 -m unittest tests.test_thread_manager_stress.TestThreadManagerStress.test_thread_pool_saturation -v

# Mixed chaotic workload
python3 -m unittest tests.test_thread_manager_stress.TestThreadManagerStress.test_mixed_workload_chaos -v
```

## 📋 Test Coverage Areas

### ThreadManager Tests
- **Singleton Pattern**: Thread-safe singleton creation and access
- **Pool Management**: Thread pool initialization and configuration
- **Task Submission**: Sync and async task handling
- **Error Handling**: Exception propagation and recovery
- **Performance**: High-volume task processing
- **Stress Testing**: Edge cases and failure scenarios
- **Memory Management**: Memory usage under sustained load

### Integration Tests
- **Event Flow**: End-to-end event propagation
- **Component Wiring**: Factory-created component interaction
- **Configuration**: Dynamic component creation based on config
- **Graceful Shutdown**: Clean system termination

## 🔧 Configuration

For comprehensive configuration options, see **[CONFIG_OPTIONS.md](CONFIG_OPTIONS.md)** - Complete reference of all available settings.

### Quick Configuration Examples

#### Basic Offline Testing Setup
```json
// system_config.json
{
  "threading": {
    "event_bus_workers": 2,
    "streamer_workers": 4,
    "strategy_workers": 2
  },
  "streamer": {"type": "offline"},
  "executor": {"type": "mock"},
  "logging": {"console_output": true}
}

// trading_config.json  
{
  "symbols": ["260105"],
  "name_symbol": "NIFTY_50",
  "paper_trade": true,
  "default_quantity": 75,
  "exit_steps": [[0.02, 0.3], [0.04, 0.3]]
}
```

#### Live Trading Setup
```json
// system_config.json
{
  "streamer": {"type": "zerodha", "async_enabled": true},
  "executor": {"type": "zerodha"},
  "logging": {"level": "INFO", "console_output": true}
}

// trading_config.json
{
  "symbols": ["260105"],
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "paper_trade": false,
  "risk_management": {
    "max_daily_loss": 50000,
    "max_daily_trades": 50
  }
}
```

### Configuration Files Overview

- **`system_config.json`**: Thread pools, streamers, executors, logging, performance settings
- **`trading_config.json`**: Symbols, strategies, risk management, API credentials, exit rules
- **`CONFIG_OPTIONS.md`**: Complete reference with all available options and examples

## 📊 Performance Monitoring

The system provides real-time monitoring through:

- **Thread Pool Statistics**: Monitor active/completed/failed tasks across all pools
- **Console Logging**: Real-time system status with configurable verbosity
- **Event Bus Metrics**: Track event throughput and processing latency
- **Memory Usage**: Monitor memory consumption under load
- **Component Health**: Check status of streamers, strategies, and executors

### Monitoring Commands
```bash
# Enable console logging for real-time monitoring
# Set "logging.console_output": true in system_config.json

# View thread pool statistics programmatically
python3 -c "
from src.core.thread_manager import ThreadManager
tm = ThreadManager()
tm.initialize_pools()
print(tm.get_pool_stats())
"

# Monitor system with CLI dashboard
python3 -m src.cli.cli_main
```

## 🚨 Important Notes

- **Thread Safety**: All components designed for concurrent access via ThreadManager
- **Event-Driven**: Use EventBus for all inter-component communication
- **Factory Pattern**: Always use factories for component creation
- **Configuration-Driven**: System behavior controlled via JSON configs
- **Console Logging**: Enable `console_output: true` for real-time monitoring
- **Testing**: Comprehensive test coverage ensures system reliability

For detailed architectural information and development guidelines, see **[LLM_README.md](LLM_README.md)**.
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
- **Typed Events**: Strongly typed event system for reliable communication

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

### Thread Pool Configuration (system_config.json)
```json
{
  "threading": {
    "event_bus_workers": 2,
    "streamer_workers": 4,
    "strategy_workers": 2,
    "executor_workers": 2,
    "system_workers": 2
  },
  "streamer": {
    "type": "offline",
    "async_enabled": true
  },
  "executor": {
    "type": "mock"
  }
}
```

### Trading Configuration (trading_config.json)
```json
{
  "symbols": ["260105"],
  "name_symbol": "NIFTY_50",
  "paper_trade": true,
  "default_quantity": 75,
  "exit_steps": [[0.02, 0.3], [0.04, 0.3]]
}
```

## 📊 Performance Metrics

The system supports comprehensive performance monitoring:

- **Thread Pool Statistics**: Active/completed/failed task counts
- **Event Bus Metrics**: Event throughput and processing latency
- **Memory Usage**: Real-time memory consumption tracking
- **Latency Distribution**: Task execution timing analysis

View metrics via the CLI dashboard or programmatically through the ThreadManager API.

## 🔄 Development Workflow

1. **Make Changes**: Edit components following the factory pattern
2. **Run Unit Tests**: Test individual components in isolation
3. **Run Integration Tests**: Test component interactions
4. **Run Performance Tests**: Ensure no performance regressions
5. **Run Stress Tests**: Verify system stability under load

## 📁 Project Structure

```
src/
├── main.py                     # Entry point with thread pool initialization
├── core/
│   ├── thread_manager.py      # Centralized thread pool management
│   ├── event_bus/             # Event-driven communication
│   ├── executors/             # Order execution layer
│   └── streamer/              # Market data streaming
├── strategies/                # Trading strategies
└── cli/                      # Command-line interface

tests/
├── test_thread_manager*.py    # Thread manager test suite
├── test_event_bus.py         # Event system tests
└── test_*_factory.py         # Factory pattern tests
```

## 🚨 Important Notes

- **Thread Safety**: All components are designed for concurrent access
- **Event-Driven**: Use EventBus for all inter-component communication
- **Factory Pattern**: Always use factories for component creation
- **Configuration-Driven**: System behavior controlled via JSON configs
- **Testing**: Comprehensive test coverage ensures system reliability

For detailed architectural information, see [LLM_README.md](LLM_README.md).
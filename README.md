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

### Integrated Order Management
- **OrderObject with Exit Logic**: Orders manage their own exit conditions via ExitManager library
- **Real-time Exit Detection**: Exit conditions checked on every LTP update
- **Step-based Exits**: Automatic partial exits when profit targets are reached
- **Integrated Performance Tracking**: Real-time profit/loss and retreat calculations

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
# "streamer": {"type": "binance"}
# "executor": {"type": "mock"}

python3 -m src.main
```

#### Paper Trading Mode
```bash
# Configure system_config.json with:
# "streamer": {"type": "binance"}
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

## 🔄 Current System Flow

### Market Data to Order Execution
```
BinanceStreamer → QuoteEvent → CandleMaker → CandleGenerated → VwapStrategy → EntrySignal → OrderManager
                                                                                              ↓
                                                                        OrderObject (with ExitManager) ← LTP Updates
                                                                                              ↓
                                                                                         Exit Detection
                                                                                              ↓
                                                                                        Order Execution
```

### Real-time Order Management
```
QuoteEvent (LTP Update)
    ↓
OrderObject.set_ltp()
    ↓
ExitManager.check_exit_conditions()
    ├── Trail Exit Check
    ├── Stop Loss Check  
    ├── Step Exit Check
    └── Market Close Check (disabled)
    ↓
Return Exit Info (if triggered)
    ↓
OrderManager.handle_exit()
    ↓
Execute Exit Order
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

## 📋 Current System Configuration

### Essential System Configuration
```json
// system_config.json
{
  "threading": {
    "event_bus_workers": 2,
    "streamer_workers": 4,
    "strategy_workers": 2,
    "executor_workers": 2,
    "system_workers": 2
  },
  "streamer": {
    "type": "binance",
    "async_enabled": true
  },
  "executor": {
    "type": "mock"
  },
  "logging": {
    "level": "INFO",
    "console_output": true
  }
}
```

### Trading Configuration
```json
// trading_config.json
{
  "symbols": ["btcusdt"],
  "name_symbol": "btcusdt",
  "paper_trade": true,
  "exit_steps": [
    [0.002, 0.3],
    [0.004, 0.3],
    [0.005, 0.3],
    [0.007, 0.3],
    [0.01, 0.3]
  ],
  "quantities": [100, 75, 50, 25, 10],
  "trails": [0.01, 0.02, 0.03],
  "reterival_exit": 0.1
}
```

## 📊 Live Order Monitoring

The system provides real-time order monitoring through:

- **Live Order JSON**: `data/live_order.json` contains real-time order information
- **Console Logging**: Real-time system status with configurable verbosity
- **Event Bus Metrics**: Track event throughput and processing latency
- **Order Performance**: Real-time profit/loss, retreat, and step tracking

### Live Order Data Structure
```json
{
  "timestamp": "2025-09-13T20:46:00.235845",
  "total_orders": 1,
  "orders": [
    {
      "symbol": "BTCUSDT",
      "side": "SELL",
      "total_quantity": 265,
      "current_quantity": 265,
      "entry_price": 111131.24,
      "current_ltp": 111259.98,
      "current_profit_percentage": -0.115,
      "retreat": 0.0,
      "max_move_percentage": 0.0,
      "status": "ACTIVE",
      "exit_steps": [0.002, 0.004, 0.005, 0.007, 0.01],
      "trail_steps": 0.01
    }
  ]
}
```

## 🎯 Key System Features

### Integrated Exit Management
- **Library Pattern**: ExitManager used as library by OrderObject
- **Real-time Detection**: Exit conditions checked on every LTP update  
- **Multiple Exit Types**: Trail, stop-loss, step-based, and time-based exits
- **Performance Metrics**: Real-time calculation of profit, retreat, and maximum movement

### Thread-Safe Architecture
- **Centralized Threading**: All concurrent operations via ThreadManager
- **Event-Driven**: Components communicate only through EventBus
- **Factory Creation**: Dynamic component instantiation based on configuration
- **Live Data Writing**: Real-time IPC file updates for dashboard integration

### Current Supported Markets
- **Cryptocurrency**: Binance WebSocket streaming for BTCUSDT and other pairs
- **Demo Mode**: Offline streamer for testing and development
- **Mock Execution**: Paper trading with realistic order simulation

## 🚨 Important Notes

- **Real-time Exit Logic**: Orders automatically detect exit conditions during LTP updates
- **Thread Safety**: All components designed for concurrent access via ThreadManager
- **Event-Driven**: Use EventBus for all inter-component communication
- **Configuration-Driven**: System behavior controlled via JSON configs
- **Live Monitoring**: Real-time order data available via `data/live_order.json`
- **Console Logging**: Enable `console_output: true` for real-time monitoring

For detailed architectural information and development guidelines, see **[LLM_README.md](LLM_README.md)**.
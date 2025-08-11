# LLM_README - Algorithmic Trading System Architecture

## 🚨 CRITICAL GUIDELINES FOR LLM AGENTS

**ALWAYS READ THIS ENTIRE DOCUMENT BEFORE MAKING ANY CHANGES**

This system follows strict architectural patterns. Violating these patterns will break the system. Follow these rules:

1. **NEVER** create new event types without updating the event bus imports
2. **ALWAYS** use the EventBus for inter-component communication 
3. **NEVER** use direct callbacks or handler registration between components
4. **ALWAYS** inherit from Publisher/Subscriber mixins for event communication
5. **NEVER** import from the wrong locations - follow the directory structure
6. **ALWAYS** check existing tests before implementing new features
7. **NEVER** modify core architecture without understanding the entire flow

---

## Project Overview

This is a **production-grade algorithmic trading system** implementing VWAP (Volume Weighted Average Price) strategies for Indian markets (NSE F&O) using multiple broker APIs (Zerodha, Binance, Upstox). The system is built on an **event-driven architecture** with strict separation of concerns and factory patterns for extensibility.

### Core Philosophy
- **Event-Driven**: All communication via EventBus singleton
- **Decoupled Components**: No direct dependencies between modules
- **Publisher-Subscriber Pattern**: Components publish/subscribe to typed events
- **Factory Pattern**: Dynamic component creation based on configuration
- **Thread-Safe**: Concurrent access handled properly
- **Testable**: Each component tested in isolation

---

## 🏗️ SYSTEM ARCHITECTURE

### Event Bus Foundation

The **EventBus** is the backbone of the system. ALL components communicate through typed events.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamers     │───▶│   EventBus      │◀───│  CandleMaker    │
│  (Publishers)   │    │   (Singleton)   │    │ (Pub/Sub)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Strategies    │◀───│   All Events    │───▶│ Order Manager   │
│  (Subscribers)  │    │   Flow Here     │    │ (Subscriber)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Factory Pattern Integration

```
SystemConfigManager ──┐
                     ├──► StreamerFactory ──► BaseStreamer
                     │                          ├── ZerodhaStreamer
                     │                          ├── BinanceStreamer
                     │                          └── OfflineStreamer
                     │
                     └──► ExecutorFactory ──► BaseExecutor
                                               ├── ZerodhaExecutor
                                               ├── MockExecutor
                                               └── BinanceExecutor
```

---

## 📁 DIRECTORY STRUCTURE (UPDATED)

```
src/
├── main.py                          # 🎯 ENTRY POINT - Factory-based wiring
├── config_manager.py                # Hot-reload trading config
├── system_config_manager.py         # System-wide configuration
├── logger_factory.py               # Centralized logging
│
├── core/
│   ├── event_bus/                   # 🚨 CORE ARCHITECTURE
│   │   ├── __init__.py             # Event exports (UPDATE when adding events)
│   │   ├── event_bus.py            # EventBus singleton (NEVER modify lightly)
│   │   ├── events.py               # All event definitions
│   │   └── mixins.py               # Publisher/Subscriber mixins
│   │
│   ├── executors/                   # 🎯 EXECUTION LAYER (Factory Pattern)
│   │   ├── __init__.py             # Executor exports
│   │   ├── base_executor.py        # Abstract base for all executors
│   │   ├── executor_factory.py     # Factory for creating executors
│   │   ├── mock_executor.py        # Paper trading executor
│   │   ├── zerodha_executor.py     # Zerodha Kite executor
│   │   └── binance_executor.py     # Binance executor
│   │
│   ├── streamer/                    # 🎯 STREAMING LAYER (Template Pattern)
│   │   ├── __init__.py             # Streamer exports
│   │   ├── base_streamer.py        # Abstract base for all streamers
│   │   ├── quote_normalizer.py     # Standardizes quote formats
│   │   ├── events.py               # Streamer-specific events
│   │   └── offline_streamer.py     # Mock data generator
│   │
│   ├── candle_maker.py             # 🎯 OHLCV + VWAP candle generation
│   ├── order_manager.py            # Manages active orders
│   ├── order_object.py             # Order state encapsulation
│   ├── order_logger.py             # CSV order logging
│   └── executioner.py              # Legacy executor wrapper
│
├── market/                          # 🎯 BROKER-SPECIFIC IMPLEMENTATIONS
│   ├── zerodha/
│   │   ├── zerodha_streamer.py     # Live Kite tick streaming
│   │   └── quote_database.py       # SQLite tick persistence
│   └── binance/
│       └── binance_streamer.py     # Crypto streaming
│
├── strategies/
│   ├── vwap_strategy.py            # 🎯 MAIN TRADING LOGIC
│   └── exit_manager.py             # Exit condition handling
│
└── cli/
    ├── dashboard.py                # Real-time monitoring
    ├── cli_main.py                 # CLI entry point
    └── demo_data.py                # Testing data generator

tests/
├── test_event_bus.py               # 🧪 EventBus comprehensive tests
├── test_candle_maker.py            # CandleMaker event integration
├── test_vwap_flow.py               # End-to-end workflow tests
├── test_executors.py               # Executor factory tests
└── test_streamers.py               # Streamer factory tests

trading_config.json                 # 🔧 TRADING CONFIGURATION
system_config.json                  # 🔧 SYSTEM CONFIGURATION
```

---

## 🔄 EVENT FLOW ARCHITECTURE

### 1. **Market Data Flow**
```
StreamerFactory → BaseStreamer Implementation (Zerodha/Binance/Offline)
    │ publishes QuoteEvent/QuoteReceived
    ▼
EventBus
    │ routes to subscribers
    ▼  
CandleMaker (Publisher + Subscriber)
    │ subscribes to QuoteReceived
    │ aggregates 5-min candles with VWAP
    │ publishes CandleGenerated
    ▼
VwapStrategy (Subscriber)
    │ subscribes to CandleGenerated
    │ analyzes VWAP crossovers
```

### 2. **Trading Signal Flow**
```
VwapStrategy (Publisher)
    │ publishes EntrySignal/ExitSignal
    ▼
EventBus
    │ routes to order management
    ▼
OrderManager (Subscriber)
    │ subscribes to Entry/Exit signals
    │ manages order lifecycle
    │ calls ExecutorFactory → BaseExecutor implementation
```

### 3. **Configuration-Driven Component Creation**
```
SystemConfigManager
    │ reads system_config.json
    ▼
Main.py
    │ creates components based on config
    ├── StreamerFactory.create_streamer(type='zerodha'|'binance'|'offline')
    └── ExecutorFactory.create_executor(type='zerodha'|'mock'|'binance')
```

---

## 🚨 CRITICAL IMPLEMENTATION RULES

### Rule 1: Factory Pattern Usage
```python
# ✅ CORRECT - Use factories for component creation
from src.core.executors.executor_factory import ExecutorFactory
from src.system_config_manager import SystemConfigManager

system_config = SystemConfigManager()
executor_config = system_config.get_executioner_config()
executor = ExecutorFactory.create_executor(
    broker=executor_config['type'],
    config=executor_config['config']
)

# ❌ WRONG - Direct instantiation
from src.core.executors.mock_executor import MockExecutor
executor = MockExecutor()  # Bypasses factory pattern
```

### Rule 2: Correct Directory Structure
```python
# ✅ CORRECT - Current structure
from src.core.executors.base_executor import BaseExecutor
from src.core.streamer.base_streamer import BaseStreamer
from src.core.event_bus import EventBus, QuoteReceived, CandleGenerated

# ❌ WRONG - Old or incorrect paths
from src.core.executioner import BaseExecutor  # Old location
from src.core.streamers.base_streamer import BaseStreamer  # Wrong directory
```

### Rule 3: Configuration Management
```python
# ✅ CORRECT - Use SystemConfigManager for system settings
from src.system_config_manager import SystemConfigManager
from src.config_manager import ConfigManager

system_config = SystemConfigManager()  # system_config.json
trading_config = ConfigManager()       # trading_config.json

# Get streamer type from system config
streamer_type = system_config.get('streamer.type', 'offline')

# ❌ WRONG - Hardcoded configurations
streamer_type = 'zerodha'  # Should come from config
```

### Rule 4: Abstract Base Class Implementation
```python
# ✅ CORRECT - Proper inheritance from base classes
class CustomExecutor(BaseExecutor):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config=config)  # Initialize base class
    
    def _place_order_impl(self, symbol, side, quantity, order_type):
        # Implementation required
        pass

# ❌ WRONG - Missing base class methods
class BadExecutor(BaseExecutor):
    def __init__(self):
        pass  # Missing super().__init__() and required methods
```

---

## 🧪 TESTING ARCHITECTURE

### Test Structure (Updated)
```
tests/
├── test_event_bus.py          # Core EventBus functionality
├── test_executors.py          # ExecutorFactory and implementations
│   ├── Factory pattern tests
│   ├── Mock executor tests
│   ├── Configuration-driven creation
│   └── Error handling
├── test_streamers.py          # StreamerFactory and implementations
│   ├── BaseStreamer template pattern
│   ├── Offline streamer tests
│   └── Quote normalization
├── test_candle_maker.py       # CandleMaker with EventBus
└── test_vwap_flow.py          # End-to-end workflow
```

### Factory Test Patterns
```python
# Factory test pattern
def test_executor_factory(self):
    # Test factory creates correct type
    mock_executor = ExecutorFactory.create_executor('mock')
    self.assertIsInstance(mock_executor, MockExecutor)
    
    # Test configuration passing
    config = {'slippage_factor': 0.01}
    executor = ExecutorFactory.create_executor('mock', config=config)
    self.assertEqual(executor.slippage_factor, 0.01)
    
    # Test invalid broker handling
    with self.assertRaises(ValueError):
        ExecutorFactory.create_executor('invalid_broker')
```

---

## 🔧 CONFIGURATION SYSTEM (UPDATED)

### system_config.json Structure (System-wide settings)
```json
{
  "streamer": {
    "type": "offline",
    "config": {
      "offline": {
        "tick_interval": 1.0,
        "base_price": 18500.0
      },
      "zerodha": {
        "reconnect_attempts": 5
      }
    }
  },
  "executor": {
    "type": "mock",
    "config": {
      "mock": {
        "slippage_factor": 0.0001,
        "initial_cash": 100000.0
      }
    }
  }
}
```

### trading_config.json Structure (Trading-specific settings)
```json
{
  "symbols": ["260105"],
  "name_symbol": "NIFTY_50",
  "paper_trade": true,
  "default_quantity": 75,
  "exit_steps": [[0.02, 0.3], [0.04, 0.3]],
  "execution": {
    "delta_sell": 0.02,
    "max_retries": 3
  }
}
```

---

## 🎯 EXTENDING THE SYSTEM

### Adding New Executors
1. **Create executor class**
```python
class NewBrokerExecutor(BaseExecutor):
    def _place_order_impl(self, symbol, side, quantity, order_type):
        # Broker-specific implementation
        pass
```

2. **Register with factory**
```python
ExecutorFactory.register_executor('new_broker', NewBrokerExecutor)
```

3. **Update system_config.json**
```json
{
  "executor": {
    "type": "new_broker",
    "config": {
      "new_broker": {
        "api_key": "xxx",
        "secret": "yyy"
      }
    }
  }
}
```

### Adding New Streamers
1. **Create streamer class**
```python
class NewExchangeStreamer(BaseStreamer):
    def _setup_connection(self):
        # Exchange-specific setup
        pass
        
    def _normalize_raw_data(self, raw_data, symbol):
        # Exchange-specific normalization
        pass
```

2. **Update directory structure**
```
src/market/new_exchange/
├── new_exchange_streamer.py
└── market_data_handler.py
```

---

## ⚠️ COMMON PITFALLS FOR LLM AGENTS

### 1. **Wrong Directory Structure**
```python
# ❌ WRONG - Incorrect paths
from src.core.executors.executor_factory import ExecutorFactory  # Correct
from src.core.executor_factory import ExecutorFactory            # Wrong

# ✅ CORRECT - Follow directory structure
from src.core.executors.executor_factory import ExecutorFactory
from src.core.streamer.base_streamer import BaseStreamer
```

### 2. **Bypassing Factory Pattern**
```python
# ❌ WRONG - Direct instantiation
from src.core.executors.mock_executor import MockExecutor
executor = MockExecutor()

# ✅ CORRECT - Use factory
from src.core.executors.executor_factory import ExecutorFactory
executor = ExecutorFactory.create_executor('mock', config=config)
```

### 3. **Configuration Confusion**
```python
# ❌ WRONG - Mixing configuration types
system_config = ConfigManager()        # Should be SystemConfigManager
trading_config = SystemConfigManager() # Should be ConfigManager

# ✅ CORRECT - Use appropriate config managers
system_config = SystemConfigManager()   # For system settings
trading_config = ConfigManager()        # For trading settings
```

### 4. **Missing Abstract Method Implementation**
```python
# ❌ WRONG - Incomplete base class implementation
class CustomExecutor(BaseExecutor):
    def __init__(self):
        super().__init__()
    # Missing required abstract methods

# ✅ CORRECT - Implement all abstract methods
class CustomExecutor(BaseExecutor):
    def _place_order_impl(self, symbol, side, quantity, order_type):
        pass
    
    def _get_order_status_impl(self, order_id):
        pass
    
    # ... other required methods
```

---

## 📋 SYSTEM STATUS & CAPABILITIES (UPDATED)

### ✅ Implemented & Tested
- Event-driven architecture with EventBus singleton
- Factory pattern for executors and streamers
- Configuration-driven component creation
- Abstract base classes with template method pattern
- Mock/offline components for testing
- System and trading configuration separation
- Publisher/Subscriber mixins for components

### 🔄 Current Component Types
**Executors:**
- MockExecutor (paper trading)
- ZerodhaExecutor (Kite API)
- BinanceExecutor (Binance API)

**Streamers:**
- OfflineStreamer (demo data)
- ZerodhaStreamer (live Kite data)
- BinanceStreamer (live crypto data)

### 🎯 Architecture Strengths
- **Factory-driven**: Dynamic component creation based on configuration
- **Template Pattern**: Consistent behavior across implementations
- **Configuration-separated**: System vs trading settings clearly divided
- **Extensible**: Easy to add new brokers/exchanges
- **Testable**: Mock implementations for all components
- **Type-safe**: Strong typing with abstract base classes

---

**🚨 REMEMBER: This system's power comes from the factory pattern combined with event-driven architecture. Always use factories for component creation and follow the established directory structure. When in doubt, check the existing patterns and test thoroughly.**
- Configuration hot-reloading

### 🔄 Current Event Types
- QuoteReceived (market data)
- CandleGenerated (OHLCV + VWAP)
- EntrySignal (strategy decisions)  
- ExitSignal (exit conditions)
- OrderExecuted (order placement)
- PositionUpdate (position tracking)

### 🎯 Architecture Strengths
- **Decoupled**: Components communicate only via events
- **Testable**: Each component tests in isolation
- **Extensible**: New events/components easy to add
- **Thread-safe**: Concurrent access properly handled
- **Observable**: All system activity flows through EventBus

---

**🚨 REMEMBER: This system's power comes from strict adherence to the event-driven architecture. Breaking these patterns will break the system. When in doubt, follow the existing patterns and test thoroughly.**

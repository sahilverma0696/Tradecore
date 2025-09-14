# LLM_README - Algorithmic Trading System Architecture

## 🚨 CRITICAL GUIDELINES FOR LLM AGENTS

**ALWAYS READ THIS ENTIRE DOCUMENT BEFORE MAKING ANY CHANGES**

This system follows strict architectural patterns. Violating these patterns will break the system. Follow these rules:

1. **NEVER** create new thread pools without using ThreadManager
2. **ALWAYS** use ThreadManager for all concurrent operations
3. **NEVER** create threads directly - use thread pool submission
4. **ALWAYS** use the EventBus for inter-component communication 
5. **NEVER** modify OrderObject exit logic without understanding ExitManager integration
6. **ALWAYS** inherit from Publisher/Subscriber mixins for event communication
7. **NEVER** create separate ExitManager instances - it's integrated into OrderObject
8. **ALWAYS** check existing tests before implementing new features
9. **NEVER** modify core architecture without understanding the entire flow

---

## Project Overview

This is a **production-grade algorithmic trading system** implementing VWAP (Volume Weighted Average Price) strategies for cryptocurrency markets using Binance WebSocket streaming. The system features **integrated order management with real-time exit detection** built on a **thread-managed event-driven architecture**.

### Core Philosophy
- **Thread-Managed**: Centralized thread pool management for all concurrent operations
- **Event-Driven**: All communication via EventBus singleton
- **Integrated Exit Logic**: OrderObject contains ExitManager as library for real-time exit detection
- **Real-time Processing**: Exit conditions checked on every LTP update
- **Publisher-Subscriber Pattern**: Components publish/subscribe to typed events
- **Factory Pattern**: Dynamic component creation based on configuration
- **Thread-Safe**: Concurrent access handled properly through ThreadManager

---

## 🏗️ CURRENT SYSTEM ARCHITECTURE

### Thread Management Foundation

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ThreadManager │───▶│  Thread Pools   │◀───│  All Components │
│   (Singleton)   │    │   (Segregated)  │    │  (Submit Tasks) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   EventBus      │    │  Async Loops    │
│   Pool (2)      │    │  (Streamer/Bus) │
└─────────────────┘    └─────────────────┘
```

### Current Order Management Architecture

```
QuoteEvent (BinanceStreamer)
        │
        ▼
OrderManager.update_ltp()
        │
        ▼
OrderObject.set_ltp() ──┐
        │               │
        ▼               ▼
ExitManager Library     Performance Metrics Update
(Integrated)           (Real-time calculation)
        │               │
        ▼               ▼
Exit Condition Check ──┘
        │
        ▼
Return Exit Info (if triggered)
        │
        ▼
OrderManager._handle_exit_signal_from_dict()
        │
        ▼
Execute Exit Order
```

### Real-time Exit Detection Flow

```
LTP Update → OrderObject.set_ltp()
                   │
                   ├─→ ExitManager.check_exit_conditions()
                   │   ├─→ Trail Exit Check (retreat >= trail)
                   │   ├─→ Stop Loss Check (profit <= -retrieval_exit)
                   │   └─→ Market Close Check (disabled)
                   │
                   ├─→ ExitManager.check_step_exit()
                   │   └─→ Step Change Exit (partial quantities)
                   │
                   └─→ ExitManager.calculate_performance_metrics()
                       ├─→ Current Profit/Loss
                       ├─→ Maximum Movement %
                       ├─→ Retreat Calculation
                       └─→ Min/Max Price Tracking
```

---

## 📁 CURRENT DIRECTORY STRUCTURE

```
src/
├── main.py                          # 🎯 ENTRY POINT - ThreadManager initialization
├── config_manager.py                # Trading configuration (hot-reload)
├── system_config_manager.py         # System configuration
├── logger_factory.py               # Centralized logging with console output
│
├── core/
│   ├── thread_manager.py            # 🚨 THREAD POOL MANAGEMENT (Singleton)
│   │
│   ├── event_bus/                   # 🚨 CORE ARCHITECTURE
│   │   ├── event_bus.py            # EventBus singleton (Uses EVENT_BUS pool)
│   │   ├── events.py               # All event definitions
│   │   └── mixins.py               # Publisher/Subscriber mixins
│   │
│   ├── executors/                   # 🎯 EXECUTION LAYER (Uses EXECUTOR pool)
│   │   ├── base_executor.py        # Abstract base (Thread-safe)
│   │   ├── executor_factory.py     # Factory for creating executors
│   │   └── mock_executor.py        # Paper trading executor
│   │
│   ├── streamer/                    # 🎯 STREAMING LAYER (Uses STREAMER pool)
│   │   ├── base_streamer.py        # Abstract base with ThreadManager integration
│   │   ├── streamer_factory.py     # Factory for creating streamers
│   │   ├── offline_streamer.py     # Demo data generator
│   │   └── binance_streamer.py     # 🔥 LIVE BINANCE WEBSOCKET STREAMING
│   │
│   ├── exit_manager.py             # 🆕 EXIT MANAGEMENT LIBRARY
│   │                               # - Used as library by OrderObject
│   │                               # - Real-time exit condition checking
│   │                               # - Performance metrics calculation
│   │                               # - Step-based exit logic
│   │
│   ├── order_manager.py            # 🔄 ORDER LIFECYCLE MANAGEMENT
│   │                               # - Integrated with ExitManager
│   │                               # - Real-time IPC file writing
│   │                               # - Thread-safe order handling
│   │
│   ├── order_object.py             # 🔄 ORDER STATE + EXIT INTEGRATION
│   │                               # - Contains ExitManager as library
│   │                               # - Real-time exit detection on LTP updates
│   │                               # - Integrated performance tracking
│   │
│   └── candle/
│       └── candle_maker.py         # 🎯 OHLCV + VWAP (Uses EVENT_BUS pool)
│
├── strategies/
│   └── vwap_strategy.py            # 🎯 TRADING LOGIC (Uses STRATEGY pool)
│
└── static/
    └── sample_binance.py           # 📘 REFERENCE WEBSOCKET IMPLEMENTATION

data/
└── live_order.json                 # 🔄 REAL-TIME ORDER DATA (IPC)

trading_config.json                  # 🔧 SYMBOLS, EXIT STEPS, QUANTITIES
system_config.json                  # 🔧 THREAD POOLS, STREAMER TYPE
```

---

## 🔄 CURRENT SYSTEM FLOW

### 1. **Market Data Flow (Binance WebSocket)**
```
BinanceStreamer (STREAMER Pool)
    │ WebSocket: wss://stream.binance.com:9443/ws/btcusdt@trade
    │ Real-time trade data processing
    ▼
ThreadManager → EventBus (EVENT_BUS Pool)
    │ QuoteEvent publishing
    ▼  
CandleMaker (EVENT_BUS Pool)
    │ OHLCV + VWAP calculation
    │ CandleGenerated event publishing
    ▼
VwapStrategy (STRATEGY Pool)
    │ Signal analysis and EntrySignal generation
```

### 2. **Order Management Flow (Integrated Exit Logic)**
```
VwapStrategy (STRATEGY Pool)
    │ EntrySignal → EventBus
    ▼
OrderManager (EXECUTOR Pool)
    │ Creates OrderObject with ExitManager library
    │ Sets exit configuration (retrieval_exit, trail, steps)
    ▼
OrderObject + ExitManager
    │ Real-time exit condition monitoring
    │ Performance metrics calculation
    │ Step-based exit detection
```

### 3. **Real-time Exit Detection (On Every LTP Update)**
```
BinanceStreamer → QuoteEvent → OrderManager.update_ltp()
                                      │
                                      ▼
                               OrderObject.set_ltp()
                                      │
                                      ├─→ ExitManager.check_exit_conditions()
                                      ├─→ ExitManager.check_step_exit()
                                      └─→ ExitManager.calculate_performance_metrics()
                                      │
                                      ▼
                               Return Exit Info (if triggered)
                                      │
                                      ▼
                               OrderManager.handle_exit()
                                      │
                                      ▼
                               Execute Exit Order
```

---

## 🚨 CRITICAL IMPLEMENTATION RULES (CURRENT SYSTEM)

### Rule 1: OrderObject Exit Integration (MANDATORY)
```python
# ✅ CORRECT - OrderObject with integrated ExitManager
class OrderObject:
    def __init__(self, name, instrument, step, trail, side, quantity, candle=None):
        # Initialize exit manager as a library
        self.exit_manager = ExitManager(f"ExitManager-{name}")
        # ...other initialization...
    
    def set_ltp(self, ltp, timestamp=None) -> Optional[Dict[str, Any]]:
        # Update order state
        self.ltp = ltp
        self._update_min_max_price(ltp)
        self._update_performance_metrics()  # Uses ExitManager
        
        # Get current order state for exit manager
        order_state = self._get_order_state()
        
        # Check for exit conditions using exit manager
        exit_info = self.exit_manager.check_exit_conditions(order_state, timestamp)
        
        return exit_info  # Returns exit info if triggered

# ❌ WRONG - Creating separate ExitManager instances
exit_manager = ExitManager()  # Don't create standalone instances
```

### Rule 2: Real-time IPC File Writing
```python
# ✅ CORRECT - IPC file writing in OrderManager
def _write_live_order_data(self):
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Collect live order data
    live_orders = []
    for symbol, order in self._orders.items():
        order_data = {
            "symbol": symbol,
            "current_ltp": order.get_ltp(),
            "current_profit_percentage": order.get_current_profit_percentage(),
            "retreat": order.get_retreat(),
            # ...other real-time data...
        }
        live_orders.append(order_data)
    
    # Write to IPC file for dashboard
    with open("data/live_order.json", 'w') as f:
        json.dump(ipc_data, f, indent=2)

# ❌ WRONG - Not updating IPC files
def update_ltp(self, event):
    order.set_ltp(event.ltp, event.timestamp)
    # Missing: self._write_live_order_data()
```

### Rule 3: Current Configuration Pattern
```python
# ✅ CORRECT - Current trading configuration structure
{
  "symbols": ["btcusdt"],                    # Binance symbol format
  "name_symbol": "btcusdt",                  # Display name
  "exit_steps": [
    [0.002, 0.3], [0.004, 0.3], [0.005, 0.3]  # [profit%, trail%]
  ],
  "quantities": [100, 75, 50, 25, 10],       # Step quantities
  "trails": [0.01, 0.02, 0.03],             # Trail values
  "reterival_exit": 0.1                      # Stop loss %
}

# ✅ CORRECT - Current system configuration
{
  "streamer": {"type": "binance", "async_enabled": true},
  "executor": {"type": "mock"},
  "threading": {
    "streamer_workers": 4,
    "event_bus_workers": 2
  }
}
```

### Rule 4: ExitManager Library Usage
```python
# ✅ CORRECT - ExitManager as library in OrderObject
def _update_performance_metrics(self):
    """Update performance metrics using exit manager calculations."""
    order_state = self._get_order_state()
    metrics = self.exit_manager.calculate_performance_metrics(order_state)
    
    # Update instance variables with calculated metrics
    self.current_profit = metrics['current_profit']
    self.current_profit_percentage = metrics['current_profit_percentage']
    self.retreat = metrics['retreat']

# ❌ WRONG - Manual performance calculation
def _update_performance_metrics(self):
    # Don't calculate manually, use ExitManager library
    self.current_profit = self.ltp - self.entry_price  # Use library instead
```

---

## 🧪 CURRENT TESTING PRIORITIES

### Integration Tests for New Architecture
```python
# Test OrderObject with integrated ExitManager
def test_order_object_exit_integration(self):
    order = OrderObject(
        name="BTCUSDT",
        instrument="BTCUSDT", 
        step=[0.002, 0.004],
        trail=[0.01],
        side="BUY",
        quantity=[100, 50]
    )
    
    # Test exit detection on LTP update
    exit_info = order.set_ltp(18600.0)  # Should trigger exit
    self.assertIsNotNone(exit_info)
    self.assertEqual(exit_info['exit_type'], 'TRAIL')

# Test real-time IPC file writing
def test_live_order_ipc_writing(self):
    order_manager = OrderManager()
    # Create test order
    # Update LTP
    # Verify data/live_order.json is updated
    self.assertTrue(os.path.exists("data/live_order.json"))
```

### Current System Testing Commands
```bash
# Test integrated order management
python3 -m unittest tests.test_order_object -v

# Test real-time exit detection
python3 -m unittest tests.test_exit_manager -v

# Test Binance streaming
python3 -m unittest tests.test_binance_streamer -v

# Test complete trading flow
python3 -m unittest tests.test_trading_integration -v
```

---

## 📋 CURRENT SYSTEM STATUS

### ✅ Operational Components
- **BinanceStreamer**: Live WebSocket streaming for BTCUSDT
- **OrderObject with ExitManager**: Integrated exit logic and performance tracking
- **Real-time IPC**: Live order data written to `data/live_order.json`
- **Thread-safe Architecture**: All operations via ThreadManager
- **Event-driven Flow**: Complete market data → signal → order → exit flow

### 🔄 Current Data Flow
- **Market Data**: Binance WebSocket → QuoteEvent → CandleMaker → CandleGenerated
- **Strategy**: VwapStrategy → EntrySignal → OrderManager
- **Order Management**: OrderObject + ExitManager → Real-time exit detection
- **IPC**: Live order data → `data/live_order.json` → Dashboard integration

### 🎯 Key Features Working
- **Real-time Exit Detection**: Checks on every LTP update
- **Step-based Exits**: Partial exits when profit targets hit
- **Performance Tracking**: Real-time profit, retreat, maximum movement
- **Live Monitoring**: Dashboard-ready JSON data in real-time
- **Thread Safety**: Concurrent processing via ThreadManager

### ⚠️ Current System Notes
- **Market Close Exits**: Disabled due to time comparison issues
- **Crypto Focus**: Currently optimized for Binance cryptocurrency trading
- **Mock Execution**: Using paper trading executor for safety
- **Real-time Updates**: IPC file updated on every LTP change

---

**🚨 REMEMBER: The current system has integrated OrderObject + ExitManager for real-time exit detection. Every LTP update triggers exit condition checking and performance metric calculation. Use ExitManager as a library within OrderObject, never as a standalone component. Always update IPC files for dashboard integration.**
- **`trading_config.json`**: Symbols, strategies, risk management, API credentials  
- **`CONFIG_OPTIONS.md`**: Complete reference of all configuration options

### Essential System Configuration
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
  },
  "logging": {
    "level": "INFO",
    "console_output": true,
    "file_output": true
  }
}
```

---

## ⚠️ COMMON PITFALLS FOR LLM AGENTS

### 1. **Direct Threading (CRITICAL ERROR)**
```python
# ❌ WRONG - Direct thread creation
import threading
def start_background_work():
    thread = threading.Thread(target=work_function)
    thread.start()

# ✅ CORRECT - Use ThreadManager
def start_background_work():
    thread_manager = ThreadManager()
    thread_manager.initialize_pools()
    future = thread_manager.submit_task(ThreadPoolType.SYSTEM, work_function)
```

### 2. **Missing Initialization**
```python
# ❌ WRONG - Using ThreadManager without initialization
thread_manager = ThreadManager()
thread_manager.submit_task(ThreadPoolType.SYSTEM, task)  # Will fail

# ✅ CORRECT - Initialize pools first
thread_manager = ThreadManager()
thread_manager.initialize_pools()
thread_manager.submit_task(ThreadPoolType.SYSTEM, task)
```

### 3. **Wrong Thread Pool Selection**
```python
# ❌ WRONG - Using wrong pool for component type
thread_manager.submit_task(ThreadPoolType.EXECUTOR, strategy_calculation)

# ✅ CORRECT - Use appropriate pool for component type
thread_manager.submit_task(ThreadPoolType.STRATEGY, strategy_calculation)
```

### 4. **Duplicate Code in Tests**
```python
# ❌ WRONG - Duplicate code blocks
if __name__ == "__main__":
    unittest.main()
    # Duplicate code here

# ✅ CORRECT - Single main block
if __name__ == "__main__":
    unittest.main()
```

---

## 📋 SYSTEM STATUS & CAPABILITIES

### ✅ Implemented & Tested
- **Thread pool management with comprehensive testing**
- **Thread-safe singleton patterns for core components**
- **Factory patterns for dynamic component creation**
- **Event-driven architecture with proper thread integration**
- **Console logging support for real-time monitoring**
- **Comprehensive test coverage for all threading scenarios**
- **Graceful shutdown with proper cleanup**

### 🔄 Current Component Types
- **Streamers**: OfflineStreamer, ZerodhaStreamer, BinanceStreamer
- **Executors**: MockExecutor, ZerodhaExecutor, BinanceExecutor
- **Strategies**: VwapStrategy with entry/exit signal generation
- **Core**: EventBus, CandleMaker, OrderManager with thread integration

### 🎯 Architecture Strengths
- **Centralized Threading**: Single ThreadManager controls all concurrency
- **Type Safety**: Strongly typed thread pool selection
- **Performance Monitoring**: Real-time statistics and health checks
- **Fault Tolerance**: Exception handling and recovery mechanisms
- **Scalability**: Configurable pool sizes for different workloads
- **Testing**: Comprehensive coverage including stress and performance tests

---

**🚨 REMEMBER: This system's power comes from the combination of thread-managed concurrency and event-driven architecture. Always use ThreadManager for threading, factories for component creation, and EventBus for communication. Test thoroughly under concurrent load conditions.**
async def async_streamer():
    data = requests.get(url)  # Blocks event loop

# ✅ CORRECT - Use async HTTP client
async def async_streamer():
    async with aiohttp.ClientSession() as session:
        data = await session.get(url)
```

### 4. **Missing Thread Pool Initialization**
```python
# ❌ WRONG - Using ThreadManager without initialization
thread_manager = ThreadManager()
thread_manager.submit_task(ThreadPoolType.SYSTEM, task)  # Will fail

# ✅ CORRECT - Initialize pools first
thread_manager = ThreadManager()
thread_manager.initialize_pools()
thread_manager.submit_task(ThreadPoolType.SYSTEM, task)
```

### 5. **Forgetting Graceful Shutdown**
```python
# ❌ WRONG - Abrupt termination
sys.exit()

# ✅ CORRECT - Graceful shutdown
thread_manager = ThreadManager()
thread_manager.shutdown(wait=True, timeout=30.0)
```

---

## 📋 SYSTEM STATUS & CAPABILITIES (THREAD-ENHANCED)

### ✅ Implemented & Tested
- **Thread pool management with comprehensive testing**
- **Thread-safe singleton pattern for ThreadManager**
- **Segregated thread pools for different component types**
- **Async loop integration for I/O-bound operations**
- **Performance monitoring and statistics**
- **Stress testing under extreme conditions**
- **Graceful shutdown with timeout handling**
- **Memory usage monitoring and leak detection**

### 🔄 Thread Pool Types
- **EVENT_BUS**: Event routing and publishing (2 workers + async loop)
- **STREAMER**: Market data processing (4 workers + async loop)
- **STRATEGY**: Signal generation (2 workers)
- **EXECUTOR**: Order placement (2 workers)
- **SYSTEM**: Health checks and monitoring (2 workers)

### 🎯 Thread Architecture Strengths
- **Centralized Management**: Single point of control for all threading
- **Type Safety**: Strongly typed thread pool selection
- **Performance Monitoring**: Real-time statistics and health checks
- **Fault Tolerance**: Exception handling and recovery mechanisms
- **Scalability**: Configurable pool sizes based on workload
- **Testing**: Comprehensive test coverage for all threading scenarios

---

**🚨 REMEMBER: This system's threading architecture is critical for performance and stability. Always use ThreadManager for concurrent operations, never create threads directly, and ensure proper pool selection for optimal performance. Test thoroughly under load conditions.**

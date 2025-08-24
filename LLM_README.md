# LLM_README - Algorithmic Trading System Architecture

## 🚨 CRITICAL GUIDELINES FOR LLM AGENTS

**ALWAYS READ THIS ENTIRE DOCUMENT BEFORE MAKING ANY CHANGES**

This system follows strict architectural patterns. Violating these patterns will break the system. Follow these rules:

1. **NEVER** create new thread pools without using ThreadManager
2. **ALWAYS** use ThreadManager for all concurrent operations
3. **NEVER** create threads directly - use thread pool submission
4. **ALWAYS** use the EventBus for inter-component communication 
5. **NEVER** use direct callbacks or handler registration between components
6. **ALWAYS** inherit from Publisher/Subscriber mixins for event communication
7. **NEVER** import from the wrong locations - follow the directory structure
8. **ALWAYS** check existing tests before implementing new features
9. **NEVER** modify core architecture without understanding the entire flow

---

## Project Overview

This is a **production-grade algorithmic trading system** implementing VWAP (Volume Weighted Average Price) strategies for Indian markets (NSE F&O) using multiple broker APIs (Zerodha, Binance, Upstox). The system is built on a **thread-managed event-driven architecture** with strict separation of concerns and factory patterns for extensibility.

### Core Philosophy
- **Thread-Managed**: Centralized thread pool management for all concurrent operations
- **Event-Driven**: All communication via EventBus singleton
- **Decoupled Components**: No direct dependencies between modules
- **Publisher-Subscriber Pattern**: Components publish/subscribe to typed events
- **Factory Pattern**: Dynamic component creation based on configuration
- **Thread-Safe**: Concurrent access handled properly through ThreadManager
- **Testable**: Each component tested in isolation with comprehensive thread safety tests

---

## 🏗️ SYSTEM ARCHITECTURE

### Thread Management Foundation

The **ThreadManager** is the concurrency backbone of the system. ALL threading operations go through centralized thread pools.

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
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   Strategy      │    │   Executor      │
│   Pool (2)      │    │   Pool (2)      │
└─────────────────┘    └─────────────────┘
```

### Thread Pool Architecture

```
ThreadManager (Singleton)
├── EVENT_BUS Pool (2 workers) + Async Loop
│   └── Handles event publishing/routing
├── STREAMER Pool (4 workers) + Async Loop  
│   └── Market data collection and processing
├── STRATEGY Pool (2 workers)
│   └── Trading signal generation
├── EXECUTOR Pool (2 workers)
│   └── Order placement and management
└── SYSTEM Pool (2 workers)
    └── Health checks, logging, monitoring
```

### Event Bus Integration with Thread Pools

```
BaseStreamer ──┐
              ├──► ThreadManager.submit_task(STREAMER, quote_processing)
              │       │
              │       ▼
              │   ┌─────────────────┐
              └──►│   EventBus      │──┐
                  │   (EVENT_BUS    │  │
                  │    Thread Pool) │  │
                  └─────────────────┘  │
                           │           │
                           ▼           ▼
                  VwapStrategy     OrderManager
                  (STRATEGY Pool)  (EXECUTOR Pool)
```

---

## 📁 DIRECTORY STRUCTURE (WITH THREAD MANAGEMENT)

```
src/
├── main.py                          # 🎯 ENTRY POINT - ThreadManager initialization
├── config_manager.py                # Hot-reload trading config
├── system_config_manager.py         # System-wide configuration
├── logger_factory.py               # Centralized logging with console output
│
├── core/
│   ├── thread_manager.py            # 🚨 THREAD POOL MANAGEMENT (Singleton)
│   │                               # - Centralized thread pool creation
│   │                               # - Async loop management
│   │                               # - Task submission and monitoring
│   │                               # - Graceful shutdown handling
│   │
│   ├── event_bus/                   # 🚨 CORE ARCHITECTURE
│   │   ├── __init__.py             # Event exports
│   │   ├── event_bus.py            # EventBus singleton (Uses EVENT_BUS pool)
│   │   ├── events.py               # All event definitions
│   │   └── mixins.py               # Publisher/Subscriber mixins
│   │
│   ├── executors/                   # 🎯 EXECUTION LAYER (Uses EXECUTOR pool)
│   │   ├── base_executor.py        # Abstract base (Thread-safe)
│   │   ├── executor_factory.py     # Factory for creating executors
│   │   ├── mock_executor.py        # Paper trading executor
│   │   └── zerodha_executor.py     # Zerodha Kite executor
│   │
│   ├── streamer/                    # 🎯 STREAMING LAYER (Uses STREAMER pool)
│   │   ├── base_streamer.py        # Abstract base with ThreadManager integration
│   │   ├── streamer_factory.py     # Factory for creating streamers
│   │   ├── offline_streamer.py     # Demo data generator
│   │   └── quote_normalizer.py     # Standardizes quote formats
│   │
│   ├── candle_maker.py             # 🎯 OHLCV + VWAP (Uses EVENT_BUS pool)
│   ├── order_manager.py            # Order management (Uses EXECUTOR pool)
│   └── order_object.py             # Order state encapsulation
│
├── strategies/
│   ├── vwap_strategy.py            # 🎯 TRADING LOGIC (Uses STRATEGY pool)
│   └── exit_manager.py             # Exit conditions (Uses STRATEGY pool)
│
└── market/                          # 🎯 BROKER-SPECIFIC IMPLEMENTATIONS
    ├── zerodha/
    │   └── zerodha_streamer.py     # Live Kite streaming (Uses STREAMER pool)
    └── binance/
        └── binance_streamer.py     # Crypto streaming (Uses STREAMER pool)

tests/
├── test_thread_manager.py          # 🧪 Core ThreadManager tests
├── test_thread_manager_performance.py # Performance under load
├── test_thread_manager_stress.py   # Stress and edge cases
├── test_event_bus.py               # EventBus with thread pools
└── test_integration.py             # End-to-end threading tests

system_config.json                  # 🔧 SYSTEM + THREAD CONFIGURATION
trading_config.json                 # 🔧 TRADING CONFIGURATION
CONFIG_OPTIONS.md                   # 🔧 COMPLETE CONFIGURATION REFERENCE
```

---

## 🔄 THREAD-MANAGED EVENT FLOW

### 1. **Market Data Flow with Thread Pools**
```
BaseStreamer (STREAMER Pool)
    │ submit_task(STREAMER, quote_processing)
    │ submit_task(EVENT_BUS, event_publishing)
    ▼
ThreadManager → EventBus (EVENT_BUS Pool)
    │ routes events through thread pool
    ▼  
CandleMaker (EVENT_BUS Pool)
    │ submit_task(EVENT_BUS, candle_generation)
    │ publishes CandleGenerated
    ▼
VwapStrategy (STRATEGY Pool)
    │ submit_task(STRATEGY, signal_analysis)
```

### 2. **Trading Signal Flow with Thread Pools**
```
VwapStrategy (STRATEGY Pool)
    │ submit_task(EVENT_BUS, publish_entry_signal)
    ▼
EventBus (EVENT_BUS Pool)
    │ routes to subscribers through thread pool
    ▼
OrderManager (EXECUTOR Pool)
    │ submit_task(EXECUTOR, order_processing)
    │ calls ExecutorFactory → BaseExecutor
```

---

## 🚨 CRITICAL IMPLEMENTATION RULES (UPDATED)

### Rule 1: Thread Pool Usage (MANDATORY)
```python
# ✅ CORRECT - Use ThreadManager for all threading
from src.core.thread_manager import ThreadManager, ThreadPoolType

thread_manager = ThreadManager()
thread_manager.initialize_pools()  # CRITICAL - Must initialize first

# Submit CPU-bound task
future = thread_manager.submit_task(
    ThreadPoolType.STRATEGY,
    self.calculate_signals,
    market_data
)

# Submit async I/O task
async_future = thread_manager.submit_async_task(
    ThreadPoolType.STREAMER,
    self.fetch_market_data_async()
)

# ❌ WRONG - Direct thread creation
import threading
thread = threading.Thread(target=some_function)  # DON'T DO THIS
thread.start()
```

### Rule 2: Logger Usage with Console Output
```python
# ✅ CORRECT - Use logger with console output for important components
from src.logger_factory import get_logger

# For main components (console + file logging)
logger = get_logger("MainComponent", console_output=True)

# For utility components (file logging only)
logger = get_logger("UtilityComponent", console_output=False)

# ❌ WRONG - Standard print statements
print("Something happened")  # Use logger instead
```

### Rule 3: Factory Pattern for Component Creation
```python
# ✅ CORRECT - Use factories for component creation
from src.core.streamer.streamer_factory import StreamerFactory
from src.core.executors.executor_factory import ExecutorFactory

streamer = StreamerFactory.create_streamer(
    streamer_type='offline',
    symbols=['NIFTY'],
    config={'base_price': 18500.0}
)

executor = ExecutorFactory.create_executor(
    broker='mock',
    config={'slippage_factor': 0.01}
)

# ❌ WRONG - Direct instantiation
from src.core.streamer.offline_streamer import OfflineStreamer
streamer = OfflineStreamer()  # Bypasses factory pattern
```

### Rule 4: Event Publishing Through Thread Pools
```python
# ✅ CORRECT - Publish events through EVENT_BUS pool
class MarketDataProcessor(Publisher):
    def __init__(self):
        super().__init__()
        self.thread_manager = ThreadManager()
        
    def publish_quote(self, quote_data):
        def _publish_task():
            event = QuoteReceived(...)
            self.publish_event(event)
        
        self.thread_manager.submit_task(ThreadPoolType.EVENT_BUS, _publish_task)

# ❌ WRONG - Direct event publishing without thread pool
class BadProcessor(Publisher):
    def publish_quote(self, quote_data):
        event = QuoteReceived(...)
        self.publish_event(event)  # Blocks calling thread
```

---

## 🧪 TESTING ARCHITECTURE (COMPREHENSIVE)

### Test File Structure
```
tests/
├── test_thread_manager.py           # Core ThreadManager functionality
│   ├── Singleton pattern tests
│   ├── Thread pool initialization
│   ├── Task submission and completion
│   ├── Error handling and statistics
│   └── Graceful shutdown tests
│
├── test_thread_manager_performance.py # Performance under load
│   ├── High-volume task submission
│   ├── Concurrent pool usage
│   ├── Memory usage monitoring
│   └── Latency distribution analysis
│
├── test_thread_manager_stress.py    # Stress and edge cases
│   ├── Exception handling under load
│   ├── Thread pool saturation
│   ├── Mixed chaotic workloads
│   └── Shutdown with pending tasks
│
└── test_event_bus.py                # EventBus integration tests
    ├── Event publishing and subscription
    ├── Thread-safe event handling
    ├── Publisher/Subscriber mixins
    └── Trading workflow simulation
```

### Thread-Safe Testing Pattern
```python
# Standard test pattern for thread-safe components
class TestThreadSafeComponent(unittest.TestCase):
    def setUp(self):
        ThreadManager._instance = None  # Reset singleton
        EventBus._instance = None       # Reset EventBus
        self.thread_manager = ThreadManager()
        self.thread_manager.initialize_pools()
    
    def tearDown(self):
        self.thread_manager.shutdown(wait=True, timeout=5.0)
        ThreadManager._instance = None
        EventBus._instance = None
    
    def test_concurrent_operations(self):
        # Test component under concurrent access
        futures = []
        for i in range(10):
            future = self.thread_manager.submit_task(
                ThreadPoolType.STRATEGY,
                component.process_data,
                test_data[i]
            )
            futures.append(future)
        
        # Verify all tasks complete successfully
        results = [f.result(timeout=10.0) for f in futures]
        self.assertEqual(len(results), 10)
```

---

## 🎯 RUNNING TESTS (COMMAND REFERENCE)

### Core Thread Manager Tests
```bash
# Basic functionality tests
python3 -m unittest tests.test_thread_manager -v

# Performance tests under load
python3 -m unittest tests.test_thread_manager_performance -v

# Stress tests and edge cases  
python3 -m unittest tests.test_thread_manager_stress -v

# Specific test methods
python3 -m unittest tests.test_thread_manager.TestThreadManager.test_singleton_pattern -v
python3 -m unittest tests.test_thread_manager.TestThreadManager.test_concurrent_task_submission -v
```

### Event Bus Tests
```bash
# Event bus functionality
python3 -m unittest tests.test_event_bus -v

# Specific event bus tests
python3 -m unittest tests.test_event_bus.TestEventBus.test_thread_safety -v
python3 -m unittest tests.test_event_bus.TestEventIntegration.test_trading_workflow -v
```

### Performance & Stress Testing
```bash
# High-volume task processing
python3 -m unittest tests.test_thread_manager_performance.TestThreadManagerPerformance.test_high_volume_task_submission -v

# Memory usage monitoring
python3 -m unittest tests.test_thread_manager_performance.TestThreadManagerPerformance.test_memory_usage_under_load -v

# Chaos testing
python3 -m unittest tests.test_thread_manager_stress.TestThreadManagerStress.test_mixed_workload_chaos -v
```

### Run All Tests
```bash
# Complete test suite
python3 -m unittest discover -s tests -v

# With coverage reporting
python3 -m coverage run -m unittest discover -s tests
python3 -m coverage report -m
```

---

## 🔧 CONFIGURATION SYSTEM (COMPLETE REFERENCE)

### Key Configuration Files
- **`system_config.json`**: Thread pools, component types, logging, performance
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

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
├── logger_factory.py               # Centralized logging
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
│   │   ├── quote_normalizer.py     # Standardizes quote formats
│   │   ├── events.py               # Streamer-specific events
│   │   └── offline_streamer.py     # Mock data generator
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

### 3. **Thread Pool Task Submission Pattern**
```
Component (Any Pool)
    │
    ├── For CPU-bound tasks:
    │   ThreadManager.submit_task(APPROPRIATE_POOL, sync_function)
    │
    ├── For I/O-bound tasks:
    │   ThreadManager.submit_async_task(ASYNC_POOL, async_coroutine)
    │
    └── For event publishing:
        ThreadManager.submit_task(EVENT_BUS, publish_event_function)
```

---

## 🚨 CRITICAL IMPLEMENTATION RULES (UPDATED)

### Rule 1: Thread Pool Usage (NEW)
```python
# ✅ CORRECT - Use ThreadManager for all threading
from src.core.thread_manager import ThreadManager, ThreadPoolType

thread_manager = ThreadManager()

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

### Rule 2: Component Thread Pool Assignment
```python
# ✅ CORRECT - Use appropriate pool for component type
class StreamerComponent(BaseStreamer):
    def process_quotes(self):
        # Use STREAMER pool for market data processing
        self._thread_manager.submit_task(
            ThreadPoolType.STREAMER,
            self._process_quote_batch
        )

class StrategyComponent(Publisher):
    def generate_signals(self):
        # Use STRATEGY pool for signal generation
        thread_manager = ThreadManager()
        thread_manager.submit_task(
            ThreadPoolType.STRATEGY,
            self._analyze_market_conditions
        )

# ❌ WRONG - Using wrong pool type
class StrategyComponent:
    def generate_signals(self):
        # Wrong pool for strategy work
        thread_manager.submit_task(ThreadPoolType.EXECUTOR, strategy_work)
```

### Rule 3: Event Publishing Through Thread Pools
```python
# ✅ CORRECT - Publish events through EVENT_BUS pool
class MarketDataProcessor(Publisher):
    def publish_quote(self, quote_data):
        def _publish_task():
            event = QuoteReceived(...)
            self.publish_event(event)
        
        thread_manager = ThreadManager()
        thread_manager.submit_task(ThreadPoolType.EVENT_BUS, _publish_task)

# ❌ WRONG - Direct event publishing without thread pool
class BadProcessor(Publisher):
    def publish_quote(self, quote_data):
        event = QuoteReceived(...)
        self.publish_event(event)  # Blocks calling thread
```

### Rule 4: Async Operations in Thread Pools
```python
# ✅ CORRECT - Use async loops for I/O-bound operations
class AsyncStreamer(BaseStreamer):
    async def stream_data_async(self):
        while self.is_running:
            data = await self.fetch_market_data()
            await self.process_data_async(data)
    
    def start_streaming(self):
        thread_manager = ThreadManager()
        future = thread_manager.submit_async_task(
            ThreadPoolType.STREAMER,
            self.stream_data_async()
        )

# ❌ WRONG - Blocking operations in async context
class BadAsyncStreamer:
    async def stream_data_async(self):
        data = requests.get(url)  # Blocking call in async context
```

---

## 🧪 TESTING ARCHITECTURE (THREAD-FOCUSED)

### Thread Manager Test Categories
```
tests/test_thread_manager.py
├── Singleton pattern validation
├── Thread-safe singleton creation
├── Pool initialization and configuration
├── Task submission (sync/async)
├── Error handling and propagation
├── Statistics and monitoring
└── Graceful shutdown

tests/test_thread_manager_performance.py  
├── High-volume task submission
├── Concurrent pool usage
├── Async task performance
├── Memory usage under load
└── Latency distribution analysis

tests/test_thread_manager_stress.py
├── Exception handling under load
├── Thread pool saturation
├── Rapid start/stop cycles
├── Mixed chaotic workloads
└── Shutdown with pending tasks
```

### Thread-Safe Component Testing Pattern
```python
# Thread-safe component test pattern
class TestThreadSafeComponent(unittest.TestCase):
    def setUp(self):
        ThreadManager._instance = None  # Reset singleton
        self.thread_manager = ThreadManager()
        self.thread_manager.initialize_pools()
    
    def tearDown(self):
        self.thread_manager.shutdown(wait=True, timeout=5.0)
        ThreadManager._instance = None
    
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

## 🔧 CONFIGURATION SYSTEM (THREAD-ENHANCED)

### system_config.json Structure (Thread Configuration)
```json
{
  "threading": {
    "event_bus_workers": 2,
    "streamer_workers": 4,
    "strategy_workers": 2,
    "executor_workers": 2,
    "system_workers": 2,
    "max_worker_threads": 8,
    "thread_timeout_seconds": 60,
    "daemon_threads": true
  },
  "streamer": {
    "type": "offline",
    "async_enabled": true,
    "config": {
      "offline": {
        "tick_interval": 1.0,
        "async_mode": true
      }
    }
  },
  "performance": {
    "enable_profiling": false,
    "memory_monitoring": true,
    "gc_collection_interval": 600
  }
}
```

---

## 🎯 RUNNING TESTS (COMPREHENSIVE)

### Core Thread Manager Tests
```bash
# Basic functionality
python3 -m unittest tests.test_thread_manager -v

# Performance under load
python3 -m unittest tests.test_thread_manager_performance -v

# Stress and edge cases  
python3 -m unittest tests.test_thread_manager_stress -v

# Specific test methods
python3 -m unittest tests.test_thread_manager.TestThreadManager.test_singleton_pattern
python3 -m unittest tests.test_thread_manager.TestThreadManager.test_concurrent_task_submission
```

### Performance Testing
```bash
# High-volume task processing
python3 -m unittest tests.test_thread_manager_performance.TestThreadManagerPerformance.test_high_volume_task_submission -v

# Memory usage monitoring
python3 -m unittest tests.test_thread_manager_performance.TestThreadManagerPerformance.test_memory_usage_under_load -v

# Latency distribution
python3 -m unittest tests.test_thread_manager_performance.TestThreadManagerPerformance.test_latency_distribution -v
```

### Stress Testing
```bash
# Exception handling under load
python3 -m unittest tests.test_thread_manager_stress.TestThreadManagerStress.test_exception_handling_stress -v

# Thread pool saturation
python3 -m unittest tests.test_thread_manager_stress.TestThreadManagerStress.test_thread_pool_saturation -v

# Chaos testing
python3 -m unittest tests.test_thread_manager_stress.TestThreadManagerStress.test_mixed_workload_chaos -v
```

### Integration Testing
```bash
# Full system with thread pools
python3 -m unittest tests.test_integration_threading -v

# Event bus with thread pools
python3 -m unittest tests.test_event_bus_threading -v
```

---

## 🎯 EXTENDING THE SYSTEM (THREAD-AWARE)

### Adding Thread-Safe Components
1. **Inherit from appropriate base class**
```python
class NewComponent(Publisher, Subscriber):
    def __init__(self):
        super().__init__()
        self.thread_manager = ThreadManager()
```

2. **Use appropriate thread pool**
```python
def process_data(self, data):
    # Submit to appropriate pool based on component type
    future = self.thread_manager.submit_task(
        ThreadPoolType.STRATEGY,  # or STREAMER, EXECUTOR, etc.
        self._process_data_impl,
        data
    )
    return future.result(timeout=30.0)
```

3. **Handle async operations properly**
```python
async def async_operation(self):
    # Use async pools for I/O-bound work
    future = self.thread_manager.submit_async_task(
        ThreadPoolType.STREAMER,
        self._fetch_data_async()
    )
    return await future
```

---

## ⚠️ COMMON PITFALLS FOR LLM AGENTS (THREAD-FOCUSED)

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
    future = thread_manager.submit_task(ThreadPoolType.SYSTEM, work_function)
```

### 2. **Wrong Thread Pool Selection**
```python
# ❌ WRONG - Using executor pool for strategy work
thread_manager.submit_task(ThreadPoolType.EXECUTOR, strategy_calculation)

# ✅ CORRECT - Use strategy pool for strategy work  
thread_manager.submit_task(ThreadPoolType.STRATEGY, strategy_calculation)
```

### 3. **Blocking Async Operations**
```python
# ❌ WRONG - Blocking call in async context
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

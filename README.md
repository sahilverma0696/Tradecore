# Tradecore

Event-driven algorithmic trading engine. Streams live market data, aggregates ticks into OHLCV candles, fires entry signals from a pluggable strategy, manages positions with a peak-retrace exit algorithm, and logs all trade activity to CSV + SQLite.

The entry strategy is swappable — VWAP cross is the default, but any signal generator that publishes `EntrySignal` integrates without touching the rest of the system.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Event Flow](#event-flow)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running](#running)
6. [CLI Tools](#cli-tools)
7. [Strategy](#strategy)
8. [Exit Algorithm](#exit-algorithm)
9. [Data Storage](#data-storage)
10. [Broker Support](#broker-support)
11. [Testing](#testing)
12. [Project Structure](#project-structure)

---

## Architecture

Components are loosely coupled via a pub-sub `EventBus`. No component holds a reference to another — they communicate only through typed events.

```
MarketData (Streamer)
        │  QuoteEvent
        ▼
   CandleMaker  ──── CandleGenerated ──▶  Strategy (e.g. VwapStrategy)
        │                                       │ EntrySignal
        │ QuoteEvent                            ▼
        └──────────────────────────────▶  OrderManager
                                               │  OrderEvent
                                               ▼
                                           Executor
                                         (paper / live)
```

**Core components:**

| Component | Role |
|---|---|
| `Streamer` | Connects to market data feed, publishes `QuoteEvent` |
| `CandleMaker` | Aggregates ticks into OHLCV candles, publishes `CandleGenerated` |
| `Strategy` | Detects entry conditions, publishes `EntrySignal` |
| `OrderManager` | Manages open positions, calls `ExitManager` on every tick |
| `ExitManager` | Peak-retrace exit logic, publishes `OrderEvent(type=FULL)` |
| `Executor` | Sends orders to broker (or simulates in paper mode) |
| `OrderLogger` | Archives closed orders to CSV + JSON |

**Infrastructure:**

| Component | Role |
|---|---|
| `EventBus` | Thread-safe singleton pub-sub broker |
| `ThreadManager` | Named thread pools (event_bus, streamer, strategy, executor, system) |
| `ConfigManager` | Singleton wrapper around `trading_config.json` |
| `SystemConfigManager` | Singleton wrapper around `system_config.json` |

---

## Event Flow

```
QuoteEvent
  └─▶ CandleMaker._on_quote          → emits CandleGenerated
  └─▶ OrderManager._on_ltp_update    → calls ExitManager.check() per open position
  └─▶ QuoteEventDBSubscriber         → writes tick to SQLite

CandleGenerated
  └─▶ VwapStrategy._on_candle        → emits EntrySignal (if VWAP cross)
  └─▶ OrderManager._on_candle        → updates current candle reference on orders

EntrySignal
  └─▶ OrderManager._on_entry_signal  → creates OrderObject, emits OrderEvent(type=ENTRY)

OrderEvent
  └─▶ Executor._on_order_event       → sends order to broker
```

---

## Installation

```bash
git clone <repo-url>
cd tradecore
pip install -r requirements.txt
```

**Copy the config template and fill in your credentials:**
```bash
cp trading_config.example.json trading_config.json
# then edit trading_config.json with your API keys
```

**macOS — SSL certificates (required for Binance WebSocket):**
```bash
/Applications/Python\ 3.x/Install\ Certificates.command
# or:
pip install certifi
```

---

## Configuration

### `system_config.json`

Controls infrastructure — streamer, executor, thread pools, logging.

```jsonc
{
  "system": {
    "mode": "offline"          // "live" | "offline" — informational only
  },
  "logging": {
    "level": "INFO",           // DEBUG | INFO | WARNING | ERROR
    "file_logging": true,
    "log_directory": "logs",
    "console_logging": true
  },
  "threading": {
    "event_bus_workers": 2,
    "streamer_workers":  4,
    "strategy_workers":  2,
    "executor_workers":  2,
    "system_workers":    2
  },
  "streamer": {
    "active": "binance",       // "binance" | "zerodha" | "upstox" | "offline"
    "async_enabled": true,
    "configs": {
      "offline":  { "tick_interval": 1.0, "base_price": 18500.0 },
      "binance":  { "reconnect_attempts": 5, "reconnect_delay": 2.0, "stream_timeout": 60, "testnet": false },
      "zerodha":  { "reconnect_attempts": 5, "reconnect_delay": 2.0 },
      "upstox":   { "reconnect_attempts": 5, "reconnect_delay": 2.0 }
    }
  },
  "executor": {
    "active": "paper",         // "paper" | "binance" | "zerodha" | "upstox"
    "configs": {
      "paper":    { "slippage_factor": 0.0001, "execution_delay": 0.1, "initial_cash": 100000.0 },
      "binance":  { "order_type": "MARKET", "time_in_force": "GTC", "test_mode": true, "max_retries": 3 },
      "zerodha":  { "exchange": "NFO", "product": "MIS", "variety": "regular", "max_retries": 3 },
      "upstox":   { "exchange": "NSE_FO", "product": "I", "validity": "DAY", "max_retries": 3 }
    }
  },
  "candle_maker": {
    "default_timeframe":  3,   // minutes per candle
    "calculate_vwap":     true,
    "persist_candles":    true
  },
  "trading_session": {
    "start_time": "09:15",     // IST
    "end_time":   "15:30",
    "timezone":   "Asia/Kolkata"
  }
}
```

### `trading_config.json`

Controls strategy parameters, symbols, quantities, and credentials. **This file is gitignored** — copy from `trading_config.example.json`.

```jsonc
{
  "symbols": ["btcusdt"],      // instruments to stream and trade

  "market_close_time": "15:30",

  // Exit algorithm parameters
  "step_pct":      2.0,        // profit level step % (levels: 2, 4, 6, 8, 10)
  "max_level_pct": 10.0,       // immediate exit when move reaches this %
  "stoploss_pct":  2.0,        // hard stop distance from entry %

  // Legacy stop parameters (used by OrderObject)
  "trail":          0.03,
  "loss_stop_low":  0.96,
  "loss_stop_high": 1.06,

  "default_quantity": 75,
  "quantities": {
    "btcusdt":    1,
    "NIFTY":     75,
    "BANKNIFTY": 25
  },

  "execution": {
    "delta_sell": 0.02,
    "delta_buy":  0.04,
    "max_retries": 3,
    "retry_delay_seconds": 1
  },

  "credentials": {
    "zerodha":  { "api_key": "", "api_secret": "", "access_token": "" },
    "binance":  { "api_key": "", "api_secret": "" },
    "upstox":   { "api_key": "", "access_token": "" }
  }
}
```

**Paper trading:** leave credential fields empty and set `executor.active = "paper"`.

---

## Running

```bash
make run          # start the trading engine
make cli          # open curses trading dashboard (live orders, P&L, stops)
make cli-simple   # same dashboard without curses (plain text, pipe-friendly)
make sys          # open curses system monitor (event wiring + live event stream)
make clean        # wipe logs and IPC files
```

**Typical workflow:**
```bash
# Terminal 1
make run

# Terminal 2 — order/trade view
make cli

# Terminal 3 — system events view
make sys
```

---

## CLI Tools

### Trading Dashboard (`make cli`)

Curses dashboard showing active positions.

Per-order display:
```
BUY  btcusdt  entry=65000.00  ltp=66300.00  P&L=+2.00%  peak=2.10%  retreat=0.10%  qty=1
     stops → loss=63700.00  zero=65000.00  | trigger=2.00%  min_move=0.00%
```

Keys: `q` to quit.

### Simple Dashboard (`make cli-simple`)

Same information, plain text output.

### System Monitor (`make sys`)

Shows infrastructure state — event wiring map and live event stream.

```
EVENT WIRING
  QuoteEvent          →  CandleMaker  +  OrderManager  +  QuoteEventDBSubscriber
  CandleGenerated     →  VwapStrategy  +  OrderManager
  EntrySignal         →  OrderManager
  OrderEvent          →  Executor

LIVE EVENT STREAM
  Time          Type                  Source                Details
  09:15:03.01   CandleGenerated       CandleMaker           btcusdt  tf=3  O=65000  C=65200  VWAP=65100
  09:15:03.02   EntrySignal           VwapStrategy          btcusdt  BUY  @ 65200.0000  strat=VWAPCross
```

Keys: `q` to quit.

---

## Strategy

**Default: VWAP Cross** — entry triggered when price crosses VWAP at candle close.

| Candle | Condition | Signal |
|---|---|---|
| `open < VWAP` and `close > VWAP` | Price crossed above VWAP | BUY |
| `open > VWAP` and `close < VWAP` | Price crossed below VWAP | SELL |

- One position per instrument — duplicate signals suppressed.
- Position cleared on `OrderEvent(type=FULL)` (exit) or `type=SWITCH` (direction flip).
- VWAP calculated cumulatively: `sum(price × volume) / sum(volume)`.

**Adding a custom strategy:** subclass `Subscriber` + `Publisher`, subscribe to `CandleGenerated` (or `QuoteEvent`), publish `EntrySignal`. No other changes needed.

---

## Exit Algorithm

**Peak-retrace-to-last-cleared-level** — mirrors backtest logic exactly.

### Levels

With default config (`step_pct=2, max_level_pct=10`):
```
Levels: [2%, 4%, 6%, 8%, 10%]
```

A level is "cleared" when peak move from entry has exceeded it.

### Exit priority (checked on every tick):

**1. HARD_STOP** — price moves `stoploss_pct`% against entry
```
BUY:  exit if ltp <= entry × (1 − stoploss_pct/100)
SELL: exit if ltp >= entry × (1 + stoploss_pct/100)
```

**2. MAX_LEVEL** — price reaches `max_level_pct`% in-the-money
```
Exit immediately at the max level price (not LTP)
```

**3. RETRACE** — price clears level N, then retraces back through it
```
Find highest cleared level → compute exact price → if LTP crosses back → exit at level price
```

**4. MARKET_CLOSE** — current IST time ≥ `market_close_time`
```
Exit at LTP
```

### Example (BUY at 65000, step=2%, max=10%, stop=2%)

```
entry = 65000
stop  = 63700  (−2%)
L1    = 66300  (+2%)
L2    = 67600  (+4%)
...
L5    = 71500  (+10%)

Scenario A — HARD_STOP:   ltp drops to 63700 → exit at 63700
Scenario B — MAX_LEVEL:   ltp reaches 71500 → exit at 71500
Scenario C — RETRACE:     ltp peaks at 67800 (cleared L2), retraces to 67600 → exit at 67600
Scenario D — MARKET_CLOSE: 15:30 IST → exit at current LTP
```

Exit price is always the **level price**, not LTP.

---

## Data Storage

### Tick Database (SQLite)

Path: `data/{streamer}/{YYYY}/{MM}/ticks_{YYYYMMDD}.db`

```sql
CREATE TABLE ticks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    symbol_id TEXT NOT NULL,
    ltp       REAL NOT NULL,
    ltq       REAL
);
CREATE INDEX idx_ticks_symbol_ts ON ticks (symbol_id, ts);
```

WAL mode enabled — safe for concurrent reads by backtest scripts.

### Order Archive

`data/order_archive.json` — rolling buffer of last 500 closed orders, survives restarts.

```json
[
  {
    "exit_time":   "2025-01-15T10:23:45",
    "entry_time":  "2025-01-15T09:15:03",
    "duration_s":  4122,
    "symbol":      "btcusdt",
    "side":        "BUY",
    "quantity":    1,
    "entry_price": 65000.0,
    "exit_price":  66300.0,
    "pnl":         1300.0,
    "pnl_pct":     2.0,
    "peak_pct":    2.1,
    "min_pct":     -0.3,
    "exit_reason": "RETRACE_L2pct"
  }
]
```

### Order CSV Log

`logs/orders.csv` — append-only, one row per closed order.

Columns: `exit_time, entry_time, duration_s, symbol, instrument, side, quantity, entry_price, exit_price, pnl, pnl_pct, peak_pct, min_pct, exit_reason`

### IPC Files (live state for dashboards)

Written atomically via `tmp → rename`.

| File | Content |
|---|---|
| `data/live_quotes.json` | Latest LTP per symbol |
| `data/live_candles.json` | Latest completed candle per symbol |
| `data/live_events_log.json` | Rolling buffer of last 200 events |
| `data/live_system.json` | Event wiring map + session metadata |
| `data/live_order.json` | All open positions |

All IPC files are deleted on system startup.

---

## Broker Support

| Broker | Streamer | Executor | Notes |
|---|---|---|---|
| **Binance** | `binance` | `binance` | WebSocket streams; certifi SSL fix for macOS |
| **Zerodha** | `zerodha` | `zerodha` | Kite Connect (`pip install kiteconnect`) |
| **Upstox** | `upstox` | `upstox` | Upstox SDK v2 |
| **Offline** | `offline` | — | Simulated price walk, no network |
| **Paper** | any | `paper` | Simulated execution, real market data |

**Switch broker:** change `streamer.active` and `executor.active` in `system_config.json`.

**Paper trading with live data (most common for testing):**
```json
"streamer": { "active": "binance" },
"executor": { "active": "paper" }
```

**Fully offline:**
```json
"streamer": { "active": "offline" },
"executor": { "active": "paper" }
```

---

## Testing

```bash
make test              # all tests
make test-streamer     # streamer factory + lifecycle tests
make test-executor     # executor factory + paper trading tests
make test-eventbus     # event bus pub-sub tests
```

---

## Project Structure

```
tradecore/
├── src/
│   ├── main.py                        # engine entry point
│   ├── config_manager.py              # trading_config.json singleton
│   ├── system_config_manager.py       # system_config.json singleton
│   ├── logger_factory.py              # named logger with file + console
│   ├── time_control.py                # IST time utilities
│   ├── global_enum.py                 # ORDERSTATE enum
│   ├── core/
│   │   ├── event_bus/
│   │   │   ├── event_bus.py           # pub-sub broker singleton
│   │   │   ├── events.py              # event dataclasses
│   │   │   └── mixins.py              # Publisher / Subscriber base classes
│   │   ├── thread_manager.py          # named thread pools
│   │   ├── candle/
│   │   │   └── candle_maker.py        # tick → OHLCV + VWAP
│   │   ├── streamer/
│   │   │   ├── streamer_factory.py
│   │   │   ├── base_streamer.py
│   │   │   ├── binance_streamer.py
│   │   │   ├── zerodha_streamer.py
│   │   │   ├── upstox_streamer.py
│   │   │   └── offline_streamer.py
│   │   ├── executors/
│   │   │   ├── executor_factory.py
│   │   │   ├── base_executor.py
│   │   │   ├── binance_executor.py
│   │   │   ├── zerodha_executor.py
│   │   │   └── upstox_executor.py
│   │   ├── order_object.py            # position state + stop tracking
│   │   ├── order_manager.py           # position lifecycle
│   │   ├── order_logger.py            # CSV + archive writer
│   │   └── exit_manager.py            # peak-retrace exit logic
│   ├── strategies/
│   │   └── vwap_strategy.py           # VWAP cross signal generator
│   ├── data_store/
│   │   └── quote_event_db_subscriber.py  # tick → SQLite
│   └── cli/
│       ├── cli_main.py                # dashboard entry point
│       ├── dashboard.py               # curses order/P&L view
│       ├── sys_cli.py                 # curses system events view
│       └── demo_data.py               # IPC-based demo data generator
├── tests/
│   ├── test_event_bus.py
│   ├── test_config_manager.py
│   ├── test_streamer.py
│   ├── test_executor.py
│   ├── test_candle_maker.py
│   ├── test_order_manager.py
│   ├── test_vwap_flow.py
│   └── test_thread_manager.py
├── trading_config.example.json        # copy to trading_config.json and add credentials
├── system_config.json
├── Makefile
└── requirements.txt
```

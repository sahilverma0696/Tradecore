# LLM_README

## Project Overview

This is an algorithmic trading system implementing a VWAP (Volume Weighted Average Price) strategy for Indian markets (NSE F&O), using Zerodha Kite APIs for live data and order execution. The system is modular, event-driven, and designed for both live and paper trading. It now includes a real-time CLI dashboard for monitoring trades.

---

## Directory Structure

- `src/`
  - `main.py` — Entry point, wires together all components using EventBus.
  - `logger_factory.py` — Logger utility.
  - `config_manager.py` — Loads and hot-reloads JSON config.
  - `core/`
    - `event_bus/` — Event-driven communication system with pub-sub pattern.
    - `order_object.py` — Order object, encapsulates order state.
    - `order_manager.py` — Manages active orders, subscribes to entry/exit signals.
    - `order_logger.py` — CSV logger for order entries/exits.
    - `candle_maker.py` — Aggregates tick data into 5-min candles, computes VWAP.
    - `executioner.py` — Places orders via KiteConnect or simulates (paper trade).
  - `cli/`
    - `dashboard.py` — Real-time CLI dashboard with curses or simple text interface.
    - `cli_main.py` — CLI entry point with argument parsing.
    - `demo_data.py` — Demo data generator for testing dashboard.
  - `market/`
    - `zerodha_streamer.py` — Handles live tick streaming, publishes QuoteReceived events.
    - `quote_database.py` — Persists tick data to SQLite, provides historical access.
  - `strategies/`
    - `vwap_strategy.py` — Main trading logic, publishes EntrySignal/ExitSignal events.

- `trading_config.json` — Main config file: symbols, credentials, instrument settings, execution params.
- `logs/` — Log files and CSVs for orders/candles.
- `requirements.txt` — Python dependencies.
- `tests/` — Unit tests for all major modules including event bus.

---

## Event-Driven Architecture

The system now uses a centralized EventBus for decoupled communication:

### Key Events:
- `QuoteReceived` — Market data from streamers
- `CandleGenerated` — 5-minute candles with VWAP
- `EntrySignal` — Strategy entry decisions
- `ExitSignal` — Exit conditions met
- `OrderExecuted` — Successful order placement

### Data Flow:
1. **Streamers** (Zerodha/Binance) publish `QuoteReceived` events
2. **CandleMaker** subscribes to quotes, publishes `CandleGenerated` events
3. **VwapStrategy** subscribes to candles, publishes `EntrySignal`/`ExitSignal` events
4. **OrderManager** subscribes to signals, manages orders, calls executioner
5. **CLI Dashboard** subscribes to all events for real-time monitoring

---

## CLI Dashboard

### Features:
- **Real-time monitoring** of active positions with live P&L
- **Recent quotes** with price changes and volume
- **Signal history** showing entry/exit decisions
- **System statistics** (uptime, event counts, total P&L)
- **Color coding** for profits/losses
- **Two interfaces**: Curses (full-featured) or simple text

### Usage:
```bash
# Main trading system
python3 -m src.main

# CLI Dashboard (separate terminal)
python3 -m src.cli.cli_main

# Demo mode (generates fake data)
python3 -m src.cli.cli_main --standalone

# Simple text interface
python3 -m src.cli.cli_main --no-curses
```

---

## Key Design Patterns

- **Event-driven Architecture**: EventBus singleton with pub-sub pattern for decoupled communication
- **Strategy-centric**: All trading logic in `vwap_strategy.py`
- **Order Abstraction**: `OrderObject` encapsulates all state for a trade
- **Real-time Monitoring**: CLI dashboard provides live trade monitoring
- **Persistence**: Orders/candles logged to CSV, ticks stored in SQLite

---

## Configuration

- `trading_config.json` contains:
  - `symbols`: List of instrument tokens
  - `name_symbol`: Mapping for display
  - `api_key`, `api_secret`, `access_token`: Kite credentials
  - `paper_trade`: Bool, if true, no live orders
  - `instrument_config`: Per-symbol step/trail settings
  - `execution`: Per-symbol order quantities, deltas, retry settings

---

## Testing

### Run Tests:
```bash
# All tests
python3 -m unittest discover -s tests

# Specific test files
python3 -m unittest tests/test_vwap_flow.py
python3 -m unittest tests/test_event_bus.py
```

### Test Coverage:
- Event bus functionality and thread safety
- VWAP strategy entry/exit logic
- Order management and execution
- Mock client integration
- Dashboard event handling

---

## CLI Dashboard Implementation

### Components:
- **TradingDashboard**: Main dashboard class, subscribes to all trading events
- **Event Handlers**: Process quotes, candles, signals, and orders in real-time
- **Display Logic**: Curses-based interface with color coding and auto-refresh
- **Demo Data**: Generates realistic trading data for testing

### Real-time Features:
- Live P&L calculation as prices change
- Position tracking with entry/exit times
- Signal history with timestamps
- System performance metrics
- Auto-refresh every 1-2 seconds

---

## Extending/Modifying

- **To change trading logic**: Edit `src/strategies/vwap_strategy.py`
- **To add new events**: Add to `src/core/event_bus/events.py`
- **To customize dashboard**: Modify `src/cli/dashboard.py`
- **To add new data sources**: Implement new streamer in `src/market/`

---

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`
- Optional: `windows-curses` for Windows users
- Terminal with color support for best dashboard experience

---

## Notes for LLM/AI Assistants

- **Event-driven**: All communication now goes through EventBus instead of direct callbacks
- **Decoupled**: Components communicate via events, making system more modular
- **Real-time**: CLI dashboard provides live monitoring without affecting trading logic
- **Testable**: Event system makes it easy to test components in isolation
- **Extensible**: Easy to add new event types and subscribers
- **Thread-safe**: EventBus handles concurrent access from multiple threads

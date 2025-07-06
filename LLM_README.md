# LLM_README

## Project Overview

This is an algorithmic trading system implementing a VWAP (Volume Weighted Average Price) strategy for Indian markets (NSE F&O), using Zerodha Kite APIs for live data and order execution. The system is modular, event-driven, and designed for both live and paper trading.

---

## Directory Structure

- `src/`
  - `main.py` — Entry point, wires together all components.
  - `logger_factory.py` — Logger utility.
  - `config_manager.py` — Loads and hot-reloads JSON config.
  - `core/`
    - `order_object.py` — Order object, encapsulates order state.
    - `order_manager.py` — Manages active orders, delegates logging.
    - `order_logger.py` — CSV logger for order entries/exits.
    - `candle_maker.py` — Aggregates tick data into 5-min candles, computes VWAP.
    - `executioner.py` — Places orders via KiteConnect or simulates (paper trade).
  - `market/`
    - `zerodha_streamer.py` — Handles live tick streaming from KiteTicker.
    - `quote_database.py` — Persists tick data to SQLite, provides historical access.
  - `strategies/`
    - `vwap_strategy.py` — Main trading logic: entry/exit, position/risk management.

- `trading_config.json` — Main config file: symbols, credentials, instrument settings, execution params.
- `logs/` — Log files and CSVs for orders/candles.
- `requirements.txt` — Python dependencies.
- `tests/` — Unit tests for all major modules.

---

## Main Components and Data Flow

1. **Config Loading**:  
   `ConfigManager` loads `trading_config.json` and hot-reloads on changes.

2. **Streaming**:  
   `ZerodhaStreamer` connects to KiteTicker, streams live ticks, and calls registered handlers.

3. **Candle Aggregation**:  
   `CandleMaker` receives ticks, aggregates into 5-min candles, computes VWAP, and notifies handlers.

4. **Strategy**:  
   `VwapStrategy` receives candles and tick data, manages all entry/exit logic, and tracks positions.

5. **Order Management**:  
   `OrderManager` creates and tracks `OrderObject` instances for each symbol, logs entries/exits.

6. **Execution**:  
   `Executioner` places orders via KiteConnect or simulates them (paper trade).

7. **Quote Database**:  
   `QuoteDatabase` persists all tick data to SQLite for later analysis/backtesting.

---

## Key Design Patterns

- **Event-driven**:  
  Components register handlers (callbacks) for new data/events.

- **Strategy-centric**:  
  All trading logic (entry/exit) is in `vwap_strategy.py`.  
  `signal_manager.py` and `exit_manager.py` are deprecated.

- **Order Abstraction**:  
  `OrderObject` encapsulates all state for a trade, including step/trail logic.

- **Persistence**:  
  Orders and candles are logged to CSV. Ticks are stored in SQLite.

---

## Configuration

- `trading_config.json` contains:
  - `symbols`: List of instrument tokens.
  - `name_symbol`: Mapping for display.
  - `api_key`, `api_secret`, `access_token`: Kite credentials.
  - `paper_trade`: Bool, if true, no live orders.
  - `instrument_config`: Per-symbol step/trail settings.
  - `execution`: Per-symbol order quantities, deltas, retry settings.

---

## Main Entry Point

To run the trading system from the `vwap` directory:
```bash
python3 -m src.main
```

---

## Running Tests

To run all tests:
```bash
python3 -m unittest discover -s tests
```

Or run a specific test file, for example:
```bash
python3 -m unittest tests/test_vwap_flow.py
```

---

## Extending/Modifying

- **To change trading logic**:  
  Edit `src/strategies/vwap_strategy.py`.

- **To add new data sources**:  
  Implement a new streamer in `src/market/`.

- **To change order handling**:  
  Edit `src/core/order_manager.py` and `src/core/order_object.py`.

---

## Deprecated

- `src/core/signal_manager.py` and `src/core/exit_manager.py` are not used; all logic is in `vwap_strategy.py`.

---

## Requirements

- Python 3.10+
- See `requirements.txt` for dependencies.

---

## Notes for LLM/AI Assistants

- All trading logic is centralized in `vwap_strategy.py`.
- Orders are created/managed via `OrderManager` and `OrderObject`.
- Streaming and candle aggregation are decoupled via handler registration.
- All stateful objects (orders, trades, quotes) are persisted for reproducibility.
- System is designed for easy extension and modularity.

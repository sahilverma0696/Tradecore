# LLM_README

## Project Overview

This is an algorithmic trading system implementing a VWAP (Volume Weighted Average Price) strategy for Indian markets (NSE F&O) via Zerodha Kite APIs, and for crypto markets via Binance APIs. The system is modular, event-driven, and supports live and paper trading for both exchanges.

---

## Directory Structure

- `src/`
  - `main.py` — Entry point, wires together all components and selects market (Zerodha/Binance).
  - `logger_factory.py` — Logger utility.
  - `config_manager.py` — Loads and hot-reloads JSON config.
  - `system_config.py` — Selects and initializes streamer based on config.
  - `core/`
    - `order_object.py` — Order object, encapsulates order state.
    - `order_manager.py` — Manages active orders, delegates logging.
    - `order_logger.py` — CSV logger for order entries/exits.
    - `candle_maker.py` — Aggregates Zerodha tick data into candles, computes VWAP.
    - `candle_binance.py` — Aggregates Binance tick data into candles, computes VWAP.
    - `candle_factory.py` — Returns correct candle maker for Zerodha or Binance.
  - `market/`
    - `zerodha/`
      - `zerodha_streamer.py` — Handles live tick streaming from KiteTicker.
      - `executioner.py` — Places orders via KiteConnect or simulates (paper trade).
    - `binance/`
      - `binance_streamer.py` — Handles live tick streaming from Binance WebSocket.
      - `binance_executioner.py` — Places orders via Binance API or simulates (paper trade).
    - `quote_database.py` — Persists tick data to SQLite.
  - `strategies/`
    - `vwap_strategy.py` — Main trading logic: entry/exit, position/risk management.
    - `exit_manager.py` — Manages exit logic for trades.

- `trading_config.json` — Main config file: symbols, credentials, instrument settings, execution params for both Zerodha and Binance.
- `logs/` — Log files and CSVs for orders/candles.
- `requirements.txt` — Python dependencies.
- `tests/` — Unit tests for all major modules.

---

## Main Components and Data Flow

1. **Config Loading**:  
   `ConfigManager` loads `trading_config.json` and hot-reloads on changes.  
   The config contains separate sections for Zerodha and Binance, and a top-level `"market"` key to select the active market.

2. **Streaming**:  
   `system_config.get_streamer(cfg)` selects and initializes the correct streamer (`ZerodhaStreamer` or `BinanceStreamer`) based on config.

3. **Candle Aggregation**:  
   `CandleFactory` selects the correct candle maker (`CandleMaker` for Zerodha, `CandleBinance` for Binance) based on config.  
   The candle maker receives ticks, aggregates into candles, computes VWAP, and notifies handlers.

4. **Strategy**:  
   `VwapStrategy` receives candles and tick data, manages all entry/exit logic, and tracks positions.

5. **Order Management**:  
   `OrderManager` creates and tracks `OrderObject` instances for each symbol, logs entries/exits.

6. **Execution**:  
   - For Zerodha: `ZerodhaExecute` places orders via KiteConnect or simulates them.
   - For Binance: `BinanceExecute` places orders via Binance API or simulates them.
   All order placement is routed through these classes.

7. **Quote Database**:  
   (Optional) `QuoteDatabase` can persist tick data to SQLite for analysis/backtesting.

---

## Key Design Patterns

- **Event-driven**:  
  Components register handlers (callbacks) for new data/events.

- **Strategy-centric**:  
  All trading logic (entry/exit) is in `vwap_strategy.py`.

- **Order Abstraction**:  
  `OrderObject` encapsulates all state for a trade, including step/trail logic.

- **Persistence**:  
  Orders and candles are logged to CSV. Ticks can be stored in SQLite.

---

## Configuration

- `trading_config.json` contains:
  - Separate sections for `zerodha` and `binance`, each with:
    - `symbols`: List of instrument tokens or symbol strings.
    - `name_symbol`: Display name for the instrument.
    - `api_key`, `api_secret`, etc.: Exchange credentials.
    - `paper_trade`: Bool, if true, no live orders.
    - `execution`: Per-symbol order quantities, deltas, retry settings.
    - `exit_steps`, `reterival_exit`, `market_close_time`, etc.
  - Top-level `"market"` key selects which config to use.

---

## Main Entry Point

To run the trading system from the `vwap` directory:
```bash
python3 -m src.main
```
- The system will select Zerodha or Binance based on `"market"` in `trading_config.json`.

**To run with Binance as the market using the Makefile:**
```bash
make run MARKET=binance
```
This will start the system with Binance as the selected market (ensure `"market": "binance"` is set in `trading_config.json`).

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
  Implement a new streamer in `src/market/` and update `system_config.py`.

- **To change order handling**:  
  Edit `src/core/order_manager.py` and `src/core/order_object.py`.

---

## Deprecated

- `src/core/signal_manager.py` is not used; all logic is in `vwap_strategy.py` and order placement is routed through the executioner classes.

---

## Requirements

- Python 3.10+
- See `requirements.txt` for dependencies.

---

## Notes for LLM/AI Assistants

- Trading logic is centralized in `vwap_strategy.py`.
- Orders are created/managed via `OrderManager` and `OrderObject`.
- Streaming and candle aggregation are decoupled via handler registration.
- All stateful objects (orders, trades, quotes) are persisted for reproducibility.
- System is designed for easy extension and modularity.

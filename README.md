# VWAP Trading Bot

This project implements a VWAP (Volume Weighted Average Price) trading strategy for Indian markets (NSE F&O), using Zerodha Kite APIs for live and paper trading. The system is modular, event-driven, and designed for both live and paper trading.

## Features

- VWAP-based entry and exit logic
- Centralized order decision-making in `vwap_strategy.py`
- Modular order management via `order_manager.py` and `order_object.py`
- Event-driven architecture with handler registration
- Hot-reloadable configuration
- Logging and CSV/SQLite persistence
- Comprehensive test suite

## Project Structure

```
vwap/
├── src/
│   ├── main.py                # Main execution loop
│   ├── logger_factory.py      # Logger utility
│   ├── config_manager.py      # Loads and hot-reloads JSON config
│   ├── core/
│   │   ├── order_object.py    # Order object, encapsulates order state
│   │   ├── order_manager.py   # Manages active orders, delegates logging
│   │   ├── order_logger.py    # CSV logger for order entries/exits
│   │   ├── candle_maker.py    # Aggregates tick data into candles, computes VWAP
│   │   ├── executioner.py     # Places orders via KiteConnect or simulates
│   ├── market/
│   │   ├── zerodha_streamer.py # Handles live tick streaming from KiteTicker
│   │   ├── quote_database.py   # Persists tick data to SQLite
│   ├── strategies/
│   │   ├── vwap_strategy.py   # Main trading logic: entry/exit, position/risk management
├── trading_config.json        # Main config file: symbols, credentials, instrument settings, execution params
├── logs/                      # Log files and CSVs for orders/candles
├── requirements.txt           # Python dependencies
├── tests/
│   ├── test_vwap_flow.py
│   ├── test_order_manager.py
│   ├── test_config_manager.py
│   ├── test_candle_maker.py
```

## Setup

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your trading environment and data sources as needed in `trading_config.json`.

## Usage

To run the main trading bot from the `vwap` directory:
```bash
make run
```

To run all tests:
```bash
make test
```

To clean all logs and Excel files (except those in `./reports`):
```bash
make clean
```

## Running Tests

To run all tests:
```bash
python3 -m unittest discover -s tests
```

Or run a specific test file, for example:
```bash
python3 -m unittest tests/test_vwap_flow.py
```

## Architecture

- **VWAPStrategy**: Contains all logic for when to enter or exit trades. Use `on_candle()` and internal methods for order decisions.
- **OrderManager**: Submits and manages orders.
- **OrderObject**: Represents an order.
- **main.py**: Orchestrates data flow and trading loop.
- **CandleMaker**: Aggregates ticks into candles and computes VWAP.
- **Executioner**: Handles order placement (live or paper).
- **ConfigManager**: Loads and hot-reloads configuration.

## Customization

- Modify `src/strategies/vwap_strategy.py` to adjust entry/exit logic.
- Extend `src/core/order_manager.py` for integration with different brokers or exchanges.

## Makefile Commands

- `make run` — Start the trading bot.
- `make test` — Run all unit tests.
- `make clean` — Remove all `.log` and `.xlsx` files (except in `./reports`), and empty directories.

## License

MIT License
# VWAP Trading Bot

This project implements a VWAP (Volume Weighted Average Price) trading strategy for Indian markets (NSE F&O) via Zerodha Kite APIs, and for crypto markets via Binance APIs. The system is modular, event-driven, and designed for both live and paper trading.

## Features

- VWAP-based entry and exit logic
- Centralized order decision-making in `vwap_strategy.py`
- Modular order management via `order_manager.py` and `order_object.py`
- Event-driven architecture with handler registration
- Hot-reloadable configuration via `ConfigManager`
- Logging and CSV/SQLite persistence
- Supports both Zerodha and Binance exchanges

## Project Structure

```
vwap/
├── src/
│   ├── main.py
│   ├── logger_factory.py      # Logger utility
│   ├── config_manager.py      # Loads and hot-reloads JSON config
│   ├── system_config.py       # Selects and initializes streamer based on config
│   ├── core/
│   │   ├── order_object.py    # Order object, encapsulates order state
│   │   ├── order_manager.py   # Manages active orders, delegates logging
│   │   ├── order_logger.py    # CSV logger for order entries/exits
│   │   ├── candle_maker.py        # Zerodha candle aggregation
│   │   ├── candle_binance.py      # Binance candle aggregation
│   │   ├── candle_factory.py      # Selects correct candle maker for market
│   ├── market/
│   │   ├── zerodha/
│   │   │   ├── zerodha_streamer.py # Handles live tick streaming from KiteTicker
│   │   │   ├── executioner.py      # Places orders via KiteConnect or simulates
│   │   ├── binance/
│   │   │   ├── binance_streamer.py # Handles live tick streaming from Binance WebSocket
│   │   │   ├── binance_executioner.py # Places orders via Binance API or simulates
│   │   ├── quote_database.py   # Persists tick data to SQLite
│   ├── strategies/
│   │   ├── vwap_strategy.py   # Main trading logic: entry/exit, position/risk management
│   │   ├── exit_manager.py    # Manages exit logic for trades
├── trading_config.json        # Main config file: symbols, credentials, instrument settings, execution params
├── logs/                      # Log files and CSVs for orders/candles
├── requirements.txt           # Python dependencies
├── tests/
│   ├── test_vwap_flow.py
│   ├── test_order_manager.py
│   ├── test_config_manager.py
│   ├── test_candle_maker.py
```

## Configuration

All configuration is managed via `trading_config.json`.  
This file contains separate sections for Zerodha and Binance, each with their own settings.  
The top-level `"market"` key selects which exchange to use.

Example:
```json
{
  "zerodha": { ... },
  "binance": { ... },
  "market": "binance" // or "zerodha"
}
```

To switch between Zerodha and Binance, change the `"market"` value in `trading_config.json`.

- For Zerodha, set `"market": "zerodha"`
- For Binance, set `"market": "binance"`

Each section contains:
- `symbols`: List of instrument tokens (Zerodha) or symbol strings (Binance)
- `name_symbol`: Display name for the instrument
- `api_key`, `api_secret`: Exchange credentials (if required)
- `paper_trade`: If true, no live orders are placed
- `execution`: Order quantities, deltas, retry settings
- `exit_steps`, `reterival_exit`, `market_close_time`, etc.

## Setup

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Edit `trading_config.json` to set your desired market and instrument settings.

## Usage

To run the main trading bot from the `vwap` directory:
```bash
python3 -m src.main
```
or
```bash
python -m src.main
```

- The system will select Zerodha or Binance based on `"market"` in `trading_config.json`.
- All order entries and exits are routed through the appropriate executioner class (`ZerodhaExecute` for Zerodha, `BinanceExecute` for Binance).

**To run with Binance as the market:**
1. Edit `trading_config.json` and set:
   ```json
   {
     "market": "binance",
     "binance": { ... }
   }
   ```
2. Run:
   ```bash
   python3 -m src.main
   ```
   or, if using the Makefile:
   ```bash
   make run MARKET=binance
   ```
- The system will automatically use Binance streamer, candle maker, executioner, and quote database.

## Running Tests

To run all tests:
```bash
make test
```
or
```bash
python3 -m unittest discover -s tests
```

To run a specific test file, for example:
```bash
python3 -m unittest tests/test_vwap_flow.py
```

## Cleaning Logs

To clean all logs and Excel files (except those in `./reports`):
```bash
make clean
```

## Architecture

- **VWAPStrategy**: Contains all logic for when to enter or exit trades. Use `on_candle()` and internal methods for order decisions.
- **OrderManager**: Submits and manages orders.
- **OrderObject**: Represents an order.
- **main.py**: Orchestrates data flow and trading loop.
- **CandleFactory**: Returns the correct candle maker (Zerodha or Binance) based on config.
- **CandleMaker**: Aggregates Zerodha ticks into candles and computes VWAP.
- **CandleBinance**: Aggregates Binance ticks into candles and computes VWAP.
- **Executioner**: Handles order placement (live or paper) for Zerodha or Binance.
- **ConfigManager**: Loads and hot-reloads configuration.

## Customization

- Modify `src/strategies/vwap_strategy.py` to adjust entry/exit logic.
- Extend `src/core/order_manager.py` for integration with different brokers or exchanges.
- Add new streamers in `src/market/` and update `system_config.py` to support more exchanges.

## Makefile Commands

- `make run` — Start the trading bot.
- `make test` — Run all unit tests.
- `make clean` — Remove all `.log` and `.xlsx` files (except in `./reports`), and empty directories.

## Troubleshooting Binance Data Flow

If you do not see data coming in when using Binance:
- Ensure `"market": "binance"` is set in `trading_config.json`.
- Check that your symbols are Binance symbol strings (e.g., `"btcusdt"`, `"ethusdt"`).
- Run with logging enabled and look for messages like `Received message:` and `Compat quote:` in the logs.
- If no messages appear, check your internet connection and firewall settings.
- If you see messages but no candles, verify that the quote handler and candle maker are registered and receiving data.
- **If you want to switch back to Zerodha, set `"market": "zerodha"` in config and rerun.**

## License

MIT License
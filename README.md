# VWAP Trading Bot

This project implements a VWAP (Volume Weighted Average Price) trading strategy for Indian markets (NSE F&O), using Zerodha Kite APIs for live and paper trading. The system is modular, event-driven, and designed for both live and paper trading.

## Features

- VWAP-based entry and exit logic
- Event-driven architecture with EventBus for decoupled communication
- Real-time CLI dashboard for monitoring trades
- Modular order management via `order_manager.py` and `order_object.py`
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
│   │   ├── event_bus/         # Event-driven communication system
│   │   ├── order_object.py    # Order object, encapsulates order state
│   │   ├── order_manager.py   # Manages active orders, delegates logging
│   │   ├── order_logger.py    # CSV logger for order entries/exits
│   │   ├── candle_maker.py    # Aggregates tick data into candles, computes VWAP
│   │   ├── executioner.py     # Places orders via KiteConnect or simulates
│   ├── cli/
│   │   ├── dashboard.py       # Real-time CLI dashboard
│   │   ├── cli_main.py        # CLI entry point
│   │   ├── demo_data.py       # Demo data for testing dashboard
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
│   ├── test_event_bus.py      # Event bus tests
```

## Setup

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your trading environment and data sources as needed in `trading_config.json`.

## Usage

### Main Trading System
To run the main trading bot from the `vwap` directory:
```bash
python3 -m src.main
```

### CLI Dashboard
To run the real-time CLI dashboard:
```bash
# With curses interface (recommended)
python3 -m src.cli.cli_main

# Simple text interface (if curses not available)
python3 -m src.cli.cli_main --no-curses

# Standalone mode with demo data
python3 -m src.cli.cli_main --standalone
```

The dashboard shows:
- Active positions with real-time P&L
- Recent quotes with price changes
- Entry/exit signals as they occur
- System statistics (uptime, event counts, total P&L)

### Dashboard Controls
- Press 'q' to quit the curses dashboard
- Press Ctrl+C to exit simple dashboard or demo mode

## Running Tests

To run all tests:
```bash
python3 -m unittest discover -s tests
```

Or run a specific test file, for example:
```bash
python3 -m unittest tests/test_vwap_flow.py
python3 -m unittest tests/test_event_bus.py
```

## Architecture

The system uses an event-driven architecture with the following key components:

- **EventBus**: Central communication hub using pub-sub pattern
- **VWAPStrategy**: Contains all logic for when to enter or exit trades
- **OrderManager**: Submits and manages orders
- **OrderObject**: Represents an order with state tracking
- **CandleMaker**: Aggregates ticks into candles and computes VWAP
- **Executioner**: Handles order placement (live or paper)
- **CLI Dashboard**: Real-time monitoring interface

### Event Flow
1. **Market Data**: Streamers publish `QuoteReceived` events
2. **Candle Generation**: CandleMaker publishes `CandleGenerated` events  
3. **Strategy Signals**: VWAPStrategy publishes `EntrySignal`/`ExitSignal` events
4. **Order Execution**: OrderManager subscribes to signals and executes trades
5. **Monitoring**: CLI Dashboard subscribes to all events for real-time display

## Customization

- Modify `src/strategies/vwap_strategy.py` to adjust entry/exit logic
- Extend `src/core/order_manager.py` for integration with different brokers
- Add new event types in `src/core/event_bus/events.py` for custom functionality

## CLI Dashboard Features

The CLI dashboard provides real-time monitoring with:

- **Active Positions**: Shows current trades with live P&L calculations
- **Recent Quotes**: Latest price data with change indicators
- **Signal History**: Recent entry/exit signals with timestamps
- **System Stats**: Uptime, event counts, and performance metrics
- **Auto-refresh**: Updates every 1-2 seconds
- **Color coding**: Green for profits, red for losses

## License

MIT License
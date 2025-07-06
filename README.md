# VWAP Trading Bot

This project implements a VWAP (Volume Weighted Average Price) trading strategy. The bot makes order creation and exit decisions based on the VWAP strategy logic.

## Features

- VWAP-based entry and exit logic
- Centralized order decision-making in `vwap_strategy.py`
- Modular order management via `order_manager.py` and `order_object.py`
- No use of separate signal or exit managers

## Project Structure

```
vwap/
├── main.py              # Main execution loop
├── vwap_strategy.py     # VWAP strategy and order decision logic
├── order_manager.py     # Handles order submission and tracking
├── order_object.py      # Defines the order object structure
├── README.md            # Project documentation
```

## Setup

1. Clone the repository.
2. Install dependencies (if any).
3. Configure your trading environment and data sources as needed.

## Usage

Run the main script:

```bash
python main.py
```

The bot will:
- Continuously fetch market data
- Use `VWAPStrategy` to decide when to enter or exit positions
- Create orders using `OrderObject`
- Submit orders via `OrderManager`

## Architecture

- **VWAPStrategy**: Contains all logic for when to enter or exit trades. Use `create_order()` to get an order decision.
- **OrderManager**: Submits and manages orders.
- **OrderObject**: Represents an order.
- **main.py**: Orchestrates data flow and trading loop.

## Customization

- Modify `vwap_strategy.py` to adjust entry/exit logic.
- Extend `order_manager.py` for integration with different brokers or exchanges.

## License

MIT License

## How to Run the Project

Navigate to the `vwap` directory and use the `-m` flag to run the main module from the `src` folder:

```bash
python -m src.main
```

Ensure all dependencies are installed and your environment is properly configured.
# VWAP Trading System Debugging Guide

## Common Issues and Solutions

### 1. No Candle Data Being Generated

**Symptoms:**
- LiveChartServer logs show "No candle data available for chart"
- Real-time prices are updating but no candles appear
- Strategy is not executing any trades

**Debug Steps:**

1. **Check Candle Maker Configuration:**
   ```bash
   grep -A 5 "candle_interval" trading_config.json
   ```
   Ensure candle_interval is set appropriately (e.g., 60 for 1-minute candles)

2. **Enable Debug Logging:**
   Set log level to DEBUG in your configuration to see detailed quote processing

3. **Check Quote Processing:**
   Look for logs like:
   ```
   DEBUG - Candle maker processing quote: BTCUSDT - 113662.94
   DEBUG - Candle maker processed quote successfully
   ```

4. **Verify Quote Format:**
   Ensure quotes have required fields:
   - `name` or `inst`: symbol identifier
   - `ltp`: last traded price
   - `ts` or `timestamp`: timestamp
   - `volume`: trading volume

5. **Check Candle Maker Implementation:**
   Verify the candle maker factory returns the correct implementation for your market

### 2. Troubleshooting Commands

**View Recent Logs:**
```bash
tail -f logs/trading_system.log | grep -E "(candle|quote|VWAP)"
```

**Check Configuration:**
```bash
python -c "from src.config_manager import ConfigManager; print(ConfigManager().get())"
```

**Test Candle Generation:**
```bash
python -c "
from src.core.candle.candle_factory import get_candle_maker
from src.config_manager import ConfigManager
cfg = ConfigManager().get()
cm = get_candle_maker(cfg)
print(f'Candle maker type: {type(cm)}')
print(f'Candle interval: {cfg.get(\"candle_interval\", \"NOT_SET\")}')
"
```

### 3. Manual Testing

Create a test script to manually feed quotes and verify candle generation:

```python
# test_candle_generation.py
from datetime import datetime
from src.core.candle.candle_factory import get_candle_maker
from src.config_manager import ConfigManager

cfg = ConfigManager().get()
candle_maker = get_candle_maker(cfg)

# Register a test handler
def test_candle_handler(name, candle):
    print(f"Generated candle for {name}: {candle}")

candle_maker.register_handler(test_candle_handler)

# Send test quotes
test_quotes = [
    {'name': 'BTCUSDT', 'ltp': 100000, 'volume': 1000, 'ts': datetime.now()},
    {'name': 'BTCUSDT', 'ltp': 100100, 'volume': 1100, 'ts': datetime.now()},
    # Add more quotes...
]

for quote in test_quotes:
    candle_maker.handle_quote_to_candle(quote)
```

### 4. Alternative Visualization

If the LiveChartServer is not showing data, you can use the backup CandlePlotter:

```python
# In your main.py, add after candle processing:
if len(candle_plotter.candles) > 0:
    candle_plotter.plot()  # Shows static plot
    # or
    candle_plotter.start_live_plot()  # Shows live plot on port 8080
```

# Configuration Options for VWAP Trading System

This document describes the configuration options available for the VWAP Trading System. Configuration is done via JSON files, allowing for easy modification and version control.

## Configuration Files

1. **system_config.json**: System-wide settings, including thread pool sizes and component types.
2. **trading_config.json**: Trading-specific settings, such as symbols, order sizes, and VWAP parameters.
3. **CONFIG_OPTIONS.md**: This document, describing all available configuration options.

## System Configuration (system_config.json)

### Thread Pool Configuration
```json
{
  "threading": {
    "event_bus_workers": 2,
    "streamer_workers": 4,
    "strategy_workers": 2,
    "executor_workers": 2,
    "system_workers": 2
  }
}
```

### Component Configuration
```json
{
  "streamer": {
    "type": "offline",
    "async_enabled": true
  },
  "executor": {
    "type": "mock"
  }
}
```

## Trading Configuration (trading_config.json)

### Basic Trading Settings
```json
{
  "symbols": ["260105"],
  "name_symbol": "NIFTY_50",
  "paper_trade": true,
  "default_quantity": 75
}
```

### VWAP Parameters
```json
{
  "exit_steps": [                         // Profit-taking steps [profit%, quantity%]
    [0.02, 0.3],                         // Take 30% profit at 2% gain
    [0.04, 0.3],                         // Take 30% profit at 4% gain
    [0.05, 0.3],                         // Take 30% profit at 5% gain
    [0.07, 0.3],                         // Take 30% profit at 7% gain
    [0.1, 0.3],                          // Take 30% profit at 10% gain
    [0.15, 0.3],                         // Take 30% profit at 15% gain
    [0.2, 0.3],                          // Take 30% profit at 20% gain
    [0.3, 0.3]                           // Take remaining at 30% gain
  ],
  "reterival_exit": 0.01,                // Trailing stop loss threshold (1%)
  "stop_loss": 0.05,                     // Hard stop loss (5%)
  "take_profit": 0.3,                    // Take profit target (30%)
  "exit_on_signal_reversal": true,       // Exit on opposite VWAP signal
  "time_based_exit": true,               // Enable time-based exits
  "max_holding_time": 3600               // Maximum holding time (seconds)
}
```

### Risk Management
```json
{
  "risk_management": {
    "max_daily_loss": 50000,             // Maximum daily loss (₹)
    "max_daily_trades": 50,              // Maximum trades per day
    "max_position_size": 100000,         // Maximum position size (₹)
    "max_open_positions": 5,             // Maximum concurrent positions
    "risk_per_trade": 0.02,              // Risk per trade (2% of capital)
    "position_sizing_method": "fixed",    // "fixed" | "kelly" | "percentage"
    "leverage_limit": 2.0,               // Maximum leverage allowed
    "drawdown_limit": 0.1,               // Maximum drawdown (10%)
    "correlation_limit": 0.7,            // Max correlation between positions
    "sector_exposure_limit": 0.3         // Max exposure per sector (30%)
  }
}
```

### Timing & Schedule
```json
{
  "market_close_time": "15:30",          // Market close time (HH:MM)
  "square_off_time": "15:25",            // Square off time before close
  "no_new_trades_after": "15:00",       // Stop new trades after time
  "trading_days": ["Mon", "Tue", "Wed", "Thu", "Fri"], // Active trading days
  "holiday_list": [                      // Market holidays
    "2024-01-26",                        // Republic Day
    "2024-03-08",                        // Holi
    "2024-08-15"                         // Independence Day
  ],
  "session_start": "09:15",              // Trading session start
  "pre_market_analysis": "09:00",       // Pre-market analysis time
  "cool_down_period": 300                // Cool down between trades (seconds)
}
```

### Logging & Monitoring
```json
{
  "logging": {
    "trade_log_enabled": true,           // Enable trade logging
    "trade_log_file": "logs/trades.csv", // Trade log file path
    "performance_log": true,             // Log performance metrics
    "error_alerts": true,                // Send error alerts
    "daily_summary": true,               // Generate daily summary
    "log_level": "INFO",                 // Logging level
    "log_rotation": true,                // Enable log rotation
    "max_log_size": "100MB"              // Maximum log file size
  }
}
```

### Broker-Specific Settings

#### Zerodha Configuration
```json
{
  "zerodha": {
    "user_id": "your_user_id",           // Zerodha client ID
    "password": "your_password",          // Trading password
    "twofa": "your_totp_secret",         // 2FA TOTP secret key
    "api_key": "your_api_key",           // Kite Connect API key
    "api_secret": "your_api_secret",     // Kite Connect secret
    "redirect_url": "http://localhost",   // OAuth redirect URL
    "session_timeout": 7200,             // Session timeout (seconds)
    "rate_limit": 3,                     // API calls per second
    "retry_count": 3,                    // Request retry count
    "request_timeout": 30                // Request timeout (seconds)
  }
}
```

#### Binance Configuration
```json
{
  "binance": {
    "api_key": "your_binance_api_key",   // Binance API key
    "api_secret": "your_binance_secret", // Binance API secret
    "testnet": false,                    // Use testnet environment
    "base_url": "https://api.binance.com", // API base URL
    "ws_url": "wss://stream.binance.com:9443", // WebSocket URL
    "recv_window": 5000,                 // Request receive window
    "timestamp_offset": 0,               // Timestamp offset (ms)
    "rate_limit_orders": 10,             // Orders per second limit
    "rate_limit_requests": 1200          // Requests per minute limit
  }
}
```

### Notification Settings
```json
{
  "notifications": {
    "enabled": true,                     // Enable notifications
    "email": {
      "enabled": false,                  // Enable email notifications
      "smtp_server": "smtp.gmail.com",   // SMTP server
      "smtp_port": 587,                  // SMTP port
      "username": "your_email@gmail.com", // Email username
      "password": "your_app_password",   // Email password
      "recipients": ["trader@example.com"] // Notification recipients
    },
    "telegram": {
      "enabled": false,                  // Enable Telegram notifications
      "bot_token": "your_bot_token",     // Telegram bot token
      "chat_id": "your_chat_id",         // Telegram chat ID
      "parse_mode": "HTML"               // Message parse mode
    },
    "webhook": {
      "enabled": false,                  // Enable webhook notifications
      "url": "https://your-webhook.com", // Webhook URL
      "timeout": 10,                     // Request timeout
      "retry_count": 3                   // Retry attempts
    },
    "events": {
      "trade_executed": true,            // Notify on trade execution
      "position_opened": true,           // Notify on position open
      "position_closed": true,           // Notify on position close
      "daily_summary": true,             // Daily P&L summary
      "error_occurred": true,            // Error notifications
      "system_start": true,              // System start notification
      "system_stop": true                // System stop notification
    }
  }
}
```

### Database Configuration
```json
{
  "database": {
    "enabled": true,                     // Enable database logging
    "type": "sqlite",                    // "sqlite" | "mysql" | "postgresql"
    "path": "data/trading_data.db",     // SQLite database path
    "host": "localhost",                 // Database host (for MySQL/PostgreSQL)
    "port": 3306,                       // Database port
    "username": "trader",               // Database username
    "password": "password",             // Database password
    "database_name": "trading_db",      // Database name
    "connection_pool_size": 5,          // Connection pool size
    "timeout": 30,                      // Connection timeout
    "backup_enabled": true,             // Enable automatic backups
    "backup_interval": 24,              // Backup interval (hours)
    "retention_days": 90                // Data retention period
  }
}
```

### Advanced Features
```json
{
  "advanced": {
    "ml_signals": {
      "enabled": false,                  // Enable ML-based signals
      "model_path": "models/vwap_model.pkl", // ML model file path
      "retrain_interval": 7,             // Retrain interval (days)
      "confidence_threshold": 0.7       // Minimum confidence for signals
    },
    "portfolio_optimization": {
      "enabled": false,                  // Enable portfolio optimization
      "rebalance_frequency": "weekly",   // "daily" | "weekly" | "monthly"
      "max_allocation_per_symbol": 0.2, // Max allocation per symbol (20%)
      "min_correlation": -0.5,          // Minimum correlation for diversification
      "optimization_method": "markowitz" // "markowitz" | "black_litterman"
    },
    "market_regime_detection": {
      "enabled": false,                  // Enable regime detection
      "lookback_period": 50,             // Lookback period for regime analysis
      "volatility_threshold": 0.02,     // Volatility threshold for regime change
      "trend_threshold": 0.05            // Trend strength threshold
    }
  }
}
```

---

## 📝 Configuration Examples

### Example 1: Conservative Live Trading Setup
```json
{
  "symbols": [260105],
  "name_symbol": "NIFTY_50",
  "paper_trade": false,
  "broker": "zerodha",
  "default_quantity": 50,
  "risk_management": {
    "max_daily_loss": 25000,
    "max_daily_trades": 10,
    "risk_per_trade": 0.01
  },
  "exit_steps": [
    [0.015, 0.5],
    [0.03, 0.5]
  ],
  "reterival_exit": 0.008,
  "stop_loss": 0.03
}
```

### Example 2: Aggressive Paper Trading Setup
```json
{
  "symbols": [260105, 256265],
  "name_symbol": "MULTI_INDEX",
  "paper_trade": true,
  "broker": "zerodha",
  "default_quantity": 100,
  "risk_management": {
    "max_daily_loss": 100000,
    "max_daily_trades": 50,
    "risk_per_trade": 0.05
  },
  "exit_steps": [
    [0.02, 0.25],
    [0.04, 0.25],
    [0.06, 0.25],
    [0.1, 0.25]
  ],
  "reterival_exit": 0.015
}
```

### Example 3: Crypto Trading Setup
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "name_symbol": "CRYPTO_MAJOR",
  "paper_trade": true,
  "broker": "binance",
  "quantities": {
    "default": 0.01,
    "BTCUSDT": 0.01,
    "ETHUSDT": 0.1
  },
  "execution": {
    "exchange": "BINANCE",
    "order_type": "MARKET",
    "time_in_force": "GTC"
  }
}
```

---

## 🔍 Configuration Validation

The system validates all configuration options at startup. Here are common validation rules:

### Required Fields
- `symbols`: Must contain at least one valid symbol
- `name_symbol`: Must be a non-empty string
- `broker`: Must be one of supported brokers

### Value Ranges
- `quantities`: Must be positive numbers
- `exit_steps`: Profit percentages must be between 0 and 1
- `reterival_exit`: Must be between 0 and 0.5
- Thread pool workers: Must be between 1 and 32

### File Paths
- All file paths are relative to project root
- Log directories are created automatically
- Database files are created if they don't exist

### API Credentials
- API keys and secrets are validated for format
- Missing credentials trigger paper trading mode
- Invalid credentials log warnings but don't stop system

---

## 📚 Configuration Best Practices

1. **Start with Paper Trading**: Always test with `paper_trade: true` first
2. **Conservative Risk Settings**: Use low risk per trade initially
3. **Monitor Logs**: Enable comprehensive logging for debugging
4. **Backup Configurations**: Keep copies of working configurations
5. **Environment Separation**: Use different configs for dev/prod
6. **Credential Security**: Store API credentials securely, consider environment variables
7. **Performance Tuning**: Adjust thread pool sizes based on system resources
8. **Regular Updates**: Review and update configurations periodically

---

**Note**: This configuration system is designed to be comprehensive yet flexible. Start with basic settings and gradually add advanced features as you become familiar with the system's behavior.
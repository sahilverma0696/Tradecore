from kiteconnect import KiteConnect, KiteTicker
from datetime import datetime
import threading
import time
from executioner import Execute
from trailing_stop_loss import TrailingStopLoss


class ZerodhaDataStreamer:
    def __init__(self, symbols, strategy, candles, logger, excel_logger, expiry, name_symbol, api_key, api_secret):
        self.symbols = list(map(int, symbols.split(',')))  # Ensure symbols are integers
        self.strategy = strategy
        self.logger = logger
        self.candles = candles
        self.api_key = api_key
        self.api_secret = api_secret
        self.kite = None
        self.ticker = None
        self.name_symbol = name_symbol
        self.last_data_time = time.time()
        self.last_ts_map = {symbol: None for symbol in self.symbols}
        self.execute = None
        self.expiry = expiry
        self.excel_logger = excel_logger
        self.kite_initialized_event = threading.Event()
        self.trailing_stop_loss = TrailingStopLoss(logger=logger,excel_logger=excel_logger)  # Pass logger to TrailingStopLoss

        print("Initialized ZerodhaDataStreamer")

    # Inside ZerodhaDataStreamer

    def initialize_kite(self, access_token=None):
        """
        Initializes the Kite Connect session.
        """
        self.kite = KiteConnect(api_key=self.api_key)

        if access_token:
            try:
                self.kite.set_access_token(access_token)
                profile = self.kite.profile()
                print("Access token is valid. Logged in as:", profile['user_name'])
                self.kite_initialized_event.set()  # Signal that kite is initialized
                return
            except Exception as e:
                print(f"Invalid or expired access token: {e}. Recreating session...")

        print(f"Login URL: {self.kite.login_url()}")
        request_token = input("Enter the request token: ")
        try:
            session_data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.kite.set_access_token(session_data["access_token"])
            print("Kite Connect session initialized.")
            self.store_access_token(session_data["access_token"])
            self.kite_initialized_event.set()  # Signal that kite is initialized
        except Exception as e:
            print(f"Failed to initialize session: {e}")
            raise    


    def store_access_token(self, token):
        """
        Saves the access token to a file for reuse.
        """
        with open("access_token.txt", "w") as f:
            f.write(token)

    def start_ticker(self):
        """
        Starts the WebSocket ticker for live data streaming.
        """
        self.kite_initialized_event.wait()  # Wait until kite is initialized

        # Now it's safe to initialize self.execute
        self.execute = Execute(self.logger, self.excel_logger, self.expiry, self.kite)
        
        
        self.ticker = KiteTicker(self.api_key, self.kite.access_token)
        

        def on_ticks(ws, ticks):
            self.last_data_time = time.time()
            for tick in ticks:
                symbol = tick['instrument_token']
                if symbol in self.symbols:
                    self.process_tick(symbol, tick)

        def on_connect(ws, response):
            ws.subscribe(self.symbols)
            ws.set_mode(ws.MODE_FULL, self.symbols)
            print("Subscribed to symbols for live data.")

        def on_close(ws, code, reason):
            print(f"WebSocket closed: {code}, {reason}. Reconnecting...")
            self.start_ticker()

        def on_error(ws, code, reason):
            print(f"WebSocket error: {code}, {reason}. Reconnecting...")
            self.start_ticker()

        self.ticker.on_ticks = on_ticks
        self.ticker.on_connect = on_connect
        self.ticker.on_close = on_close
        self.ticker.on_error = on_error

        threading.Thread(target=self.ticker.connect, daemon=True).start()

    def process_tick(self, symbol, tick):
        """
        Processes a single tick and updates candles with precision up to seconds for comparison.
        """
        try:
            current_price = float(tick.get('last_price'))
            tick_timestamp = tick.get('exchange_timestamp')  # Extract timestamp from the tick data
    
            if not current_price or not tick_timestamp:
                print(f"Invalid tick data for symbol {symbol}: {tick}")
                return
    
            # Check trailing stop loss
            stop_loss_signal = self.trailing_stop_loss.update(current_price)
            if stop_loss_signal:
                if stop_loss_signal == 'close_long':
                    self.execute.close_positions(tick_timestamp, direction_side='long')
                    self.strategy.last_decision = 'close long'
                    self.strategy.last_decision_candle = self.candles.candle_data[symbol]['1m']['historicalcandles'][-1]
                    self.logger.log("Trailing stop loss triggered: Closing long position")
                elif stop_loss_signal == 'close_short':
                    self.execute.close_positions(tick_timestamp, direction_side='short')
                    self.strategy.last_decision = 'close short'
                    self.strategy.last_decision_candle = self.candles.candle_data[symbol]['1m']['historicalcandles'][-1]
                    self.logger.log("Trailing stop loss triggered: Closing short position")

            # Check for reopen conditions on each tick's last price
            reopen_signal = self.strategy.check_reopen_position(current_price)
            if reopen_signal:
                if reopen_signal == 'reopen long':
                    self.logger.log("Reopening last long positions on tick")
                    self.execute.reopen_positions(tick_timestamp, num_positions=2)
                    self.trailing_stop_loss.start_trailing('long', current_price)
                elif reopen_signal == 'reopen short':
                    self.logger.log("Reopening last short positions on tick")
                    self.execute.reopen_positions(tick_timestamp, num_positions=2)
                    self.trailing_stop_loss.start_trailing('short', current_price)

            # Extract the current second from the timestamp
            current_second = tick_timestamp.strftime('%Y-%m-%d %H:%M:%S')  # Full timestamp with seconds
            current_minute = tick_timestamp.strftime('%Y-%m-%d %H:%M')      # Minute precision
    
            # If no previous second recorded or a new second has started
            if self.last_ts_map.get(symbol) != current_minute:
                # New minute detected
                self.last_ts_map[symbol] = current_minute
    
                # Consolidate the previous minute's candle if applicable
                if self.last_ts_map.get(symbol) is not None:
                    self.process_consolidated_candle(symbol, current_price, tick_timestamp)
    
                # Start a new candle for the new minute
                self.candles.append(symbol, '1m', {
                    'open': current_price,
                    'high': current_price,
                    'low': current_price,
                    'close': current_price,
                    'ts': tick_timestamp.strftime('%Y-%m-%d %H:%M:%S')  # Full timestamp
                })
            else:
                # Still in the same minute, update the ongoing candle
                self.candles.append(symbol, '1m', {
                    'open': current_price,  # Open remains unchanged
                    'high': current_price,  # Update if the current price is higher
                    'low': current_price,   # Update if the current price is lower
                    'close': current_price,  # Update the close price
                    'ts': tick_timestamp.strftime('%Y-%m-%d %H:%M:%S')  # Full timestamp
                })
    
        except ValueError as e:
            print(f"ValueError for symbol {symbol}: {e}")
        except Exception as e:
            print(f"Unexpected error while processing tick for symbol {symbol}: {e}")


    def process_consolidated_candle(self, symbol, current_price, timestamp):
        self.candles.consolidate(symbol, '1m')
        decision = self.strategy.generate_signal(self.candles, symbol, timestamp)
        if decision == 'short':
            self.execute.execute_short(self.name_symbol, current_price, timestamp)
            self.trailing_stop_loss.start_trailing('short', current_price)
        elif decision == 'long':
            self.execute.execute_long(self.name_symbol, current_price, timestamp)
            self.trailing_stop_loss.start_trailing('long', current_price)
        elif decision == 'close short':
            self.logger.log("Direction change signal: close short")
            self.execute.close_positions(timestamp, direction_side='short')
            self.trailing_stop_loss.reset()
        elif decision == 'close long':
            self.logger.log("Direction change signal: close long")
            self.execute.close_positions(timestamp, direction_side='long')
            self.trailing_stop_loss.reset()


    def stop_stream(self):
        """
        Stops the WebSocket ticker.
        """
        if self.ticker:
            self.ticker.close()
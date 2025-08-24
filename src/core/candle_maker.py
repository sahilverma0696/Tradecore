"""CandleMaker component for VWAP trading system."""
from typing import List
from datetime import datetime, timedelta

from src.core.event_bus import Subscriber, Publisher, QuoteEvent, CandleGenerated
from src.logger_factory import get_logger

class CandleMaker(Subscriber, Publisher):
    """
    Converts real-time quotes into OHLCV candles with VWAP calculation.
    Subscribes to QuoteEvent events and publishes CandleGenerated events.
    """
    
    def __init__(self, timeframe: str = "5min"):
        super().__init__()  # Initialize both Subscriber and Publisher mixins
        self.timeframe = timeframe
        self.logger = get_logger("CandleMaker", console_output=True)
        
        # Internal state
        self.symbol_candles = {}  # type: ignore
        self.last_quote_time = {}  # type: ignore
        self.vwap_data = {}  # type: ignore
        
        # Timeframe settings
        self.timeframe_delta = self._parse_timeframe(timeframe)
        
        # Subscribe to QuoteEvent events - CRITICAL for receiving market data
        self.subscribe_to_event(QuoteEvent, self.on_quote_received)
        self.logger.info(f"✅ CandleMaker subscribed to QuoteEvent events")
        
    def _parse_timeframe(self, timeframe: str) -> timedelta:
        """Parse the timeframe string and return a timedelta object."""
        try:
            unit = timeframe[-1]
            value = int(timeframe[:-1])
            
            if unit == 's':
                return timedelta(seconds=value)
            elif unit == 'm':
                return timedelta(minutes=value)
            elif unit == 'h':
                return timedelta(hours=value)
            elif unit == 'd':
                return timedelta(days=value)
            else:
                raise ValueError(f"Invalid timeframe unit: {unit}")
        except Exception as e:
            self.logger.error(f"Error parsing timeframe '{timeframe}': {e}")
            raise
    
    def on_quote_received(self, event: QuoteEvent):
        """Handle incoming quote events and build candles."""
        try:
            self.logger.info(f"📊 Received quote for {event.symbol}: LTP={event.ltp}, Volume={event.volume}")
            
            # Process the quote and potentially generate candle
            self.process_quote(event.symbol, event.ltp, event.volume, event.timestamp)
            
        except Exception as e:
            self.logger.error(f"Error processing quote for {event.symbol}: {e}")
    
    def process_quote(self, symbol: str, ltp: float, volume: int, timestamp: datetime):
        """
        Process an incoming quote, updating the candle state and emitting
        CandleGenerated events if a candle is completed.
        """
        # Initialize symbol state if not present
        if symbol not in self.symbol_candles:
            self.symbol_candles[symbol] = {
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': volume,
                'start_time': timestamp,
                'vwap': ltp,
                'trade_count': 1
            }
            self.last_quote_time[symbol] = timestamp
            self.vwap_data[symbol] = {'cumulative_price': 0, 'cumulative_volume': 0}
            return
        
        candle = self.symbol_candles[symbol]
        last_time = self.last_quote_time[symbol]
        
        # Update the candle with the new quote data
        candle['close'] = ltp
        candle['volume'] += volume
        candle['trade_count'] += 1
        
        # VWAP calculation
        self.vwap_data[symbol]['cumulative_price'] += ltp * volume
        self.vwap_data[symbol]['cumulative_volume'] += volume
        candle['vwap'] = self.vwap_data[symbol]['cumulative_price'] / self.vwap_data[symbol]['cumulative_volume']
        
        # Check if the candle is complete based on the timeframe
        if timestamp >= last_time + self.timeframe_delta:
            # Candle is complete, publish the CandleGenerated event
            self.publish_candle(symbol, candle)
            
            # Reset the candle state for the next candle
            self.symbol_candles[symbol] = {
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': volume,
                'start_time': timestamp,
                'vwap': ltp,
                'trade_count': 1
            }
            self.last_quote_time[symbol] = timestamp
            self.vwap_data[symbol] = {'cumulative_price': 0, 'cumulative_volume': 0}
    
    def publish_candle(self, symbol: str, candle_data: dict):
        """Publish a generated candle as a CandleGenerated event."""
        event = CandleGenerated(
            timestamp=datetime.now(),
            source="CandleMaker",
            symbol=symbol,
            open=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close'],
            volume=candle_data['volume'],
            vwap=candle_data['vwap'],
            trade_count=candle_data['trade_count']
        )
        
        self.publish_event(event)
        self.logger.info(f"Generated candle for {symbol}: {candle_data}")
    
    def get_candle(self, symbol: str):
        """Get the latest candle data for a symbol."""
        return self.symbol_candles.get(symbol)
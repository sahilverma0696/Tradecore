from datetime import datetime
from typing import Dict, Any, Optional
from .events import QuoteEvent


class QuoteNormalizer:
    """Normalizes quotes from different exchanges into standardized QuoteEvent."""
    
    @staticmethod
    def normalize_zerodha_tick(tick: Dict[str, Any], symbol: str, source: str) -> QuoteEvent:
        """Normalize Zerodha/Kite tick data to QuoteEvent."""
        timestamp = tick.get('timestamp') or tick.get('exchange_timestamp') or datetime.now()
        
        return QuoteEvent(
            timestamp=timestamp,
            source=source,
            symbol=symbol,
            instrument_token=str(tick.get('instrument_token', '')),
            ltp=float(tick.get('last_price', 0)),
            ltq=int(tick.get('last_quantity', 0)),
            volume=int(tick.get('volume_traded', tick.get('volume', 0))),
            change=float(tick.get('change', 0)),
            change_percent=float(tick.get('change_percent', 0)) if tick.get('change_percent') else None,
            bid=float(tick.get('buy_price', 0)) if tick.get('buy_price') else None,
            ask=float(tick.get('sell_price', 0)) if tick.get('sell_price') else None,
            bid_quantity=int(tick.get('buy_quantity', 0)) if tick.get('buy_quantity') else None,
            ask_quantity=int(tick.get('sell_quantity', 0)) if tick.get('sell_quantity') else None,
            high=float(tick.get('high', 0)) if tick.get('high') else None,
            low=float(tick.get('low', 0)) if tick.get('low') else None,
            open=float(tick.get('open', 0)) if tick.get('open') else None,
            previous_close=float(tick.get('previous_close', 0)) if tick.get('previous_close') else None,
            exchange="NSE",  # Default for Zerodha
            raw_data=tick
        )
    
    @staticmethod
    def normalize_binance_tick(tick: Dict[str, Any], symbol: str, source: str) -> QuoteEvent:
        """Normalize Binance ticker data to QuoteEvent."""
        timestamp_ms = tick.get('E')
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms else datetime.now()
        
        return QuoteEvent(
            timestamp=timestamp,
            source=source,
            symbol=symbol,
            instrument_token=tick.get('s', ''),
            ltp=float(tick.get('c', 0)),  # Current price
            ltq=int(float(tick.get('q', 0))),  # Last quantity (from 'q' field)
            volume=int(float(tick.get('v', 0))),  # 24hr volume
            change=float(tick.get('p', 0)),  # Price change
            change_percent=float(tick.get('P', 0)),  # Price change percent
            bid=float(tick.get('b', 0)) if tick.get('b') else None,
            ask=float(tick.get('a', 0)) if tick.get('a') else None,
            bid_quantity=int(float(tick.get('B', 0))) if tick.get('B') else None,
            ask_quantity=int(float(tick.get('A', 0))) if tick.get('A') else None,
            high=float(tick.get('h', 0)) if tick.get('h') else None,
            low=float(tick.get('l', 0)) if tick.get('l') else None,
            open=float(tick.get('o', 0)) if tick.get('o') else None,
            previous_close=float(tick.get('x', 0)) if tick.get('x') else None,
            exchange="BINANCE",
            raw_data=tick
        )
    
    @staticmethod
    def normalize_upstox_tick(tick: Dict[str, Any], symbol: str, source: str) -> QuoteEvent:
        """Normalize Upstox tick data to QuoteEvent."""
        timestamp = tick.get('timestamp', datetime.now())
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp / 1000)
        
        return QuoteEvent(
            timestamp=timestamp,
            source=source,
            symbol=symbol,
            instrument_token=str(tick.get('instrument_key', '')),
            ltp=float(tick.get('ltp', 0)),
            ltq=int(tick.get('ltq', 0)),
            volume=int(tick.get('volume', 0)),
            change=float(tick.get('net_change', 0)),
            change_percent=float(tick.get('percent_change', 0)) if tick.get('percent_change') else None,
            bid=float(tick.get('bid_price', 0)) if tick.get('bid_price') else None,
            ask=float(tick.get('ask_price', 0)) if tick.get('ask_price') else None,
            bid_quantity=int(tick.get('bid_qty', 0)) if tick.get('bid_qty') else None,
            ask_quantity=int(tick.get('ask_qty', 0)) if tick.get('ask_qty') else None,
            high=float(tick.get('high', 0)) if tick.get('high') else None,
            low=float(tick.get('low', 0)) if tick.get('low') else None,
            open=float(tick.get('open', 0)) if tick.get('open') else None,
            previous_close=float(tick.get('prev_close', 0)) if tick.get('prev_close') else None,
            exchange="NSE",  # Default for Upstox
            raw_data=tick
        )
    
    @staticmethod
    def normalize_generic_tick(tick: Dict[str, Any], symbol: str, source: str, 
                             ltp_field: str = 'ltp', ltq_field: str = 'ltq',
                             volume_field: str = 'volume', **field_mapping) -> QuoteEvent:
        """Normalize generic tick data using field mapping."""
        timestamp = tick.get('timestamp', datetime.now())
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp / 1000)
        
        return QuoteEvent(
            timestamp=timestamp,
            source=source,
            symbol=symbol,
            instrument_token=str(tick.get(field_mapping.get('instrument_token', 'instrument_token'), '')),
            ltp=float(tick.get(ltp_field, 0)),
            ltq=int(tick.get(ltq_field, 0)),
            volume=int(tick.get(volume_field, 0)),
            change=float(tick.get(field_mapping.get('change', 'change'), 0)),
            change_percent=float(tick.get(field_mapping.get('change_percent', 'change_percent'), 0)) if tick.get(field_mapping.get('change_percent', 'change_percent')) else None,
            bid=float(tick.get(field_mapping.get('bid', 'bid'), 0)) if tick.get(field_mapping.get('bid', 'bid')) else None,
            ask=float(tick.get(field_mapping.get('ask', 'ask'), 0)) if tick.get(field_mapping.get('ask', 'ask')) else None,
            high=float(tick.get(field_mapping.get('high', 'high'), 0)) if tick.get(field_mapping.get('high', 'high')) else None,
            low=float(tick.get(field_mapping.get('low', 'low'), 0)) if tick.get(field_mapping.get('low', 'low')) else None,
            open=float(tick.get(field_mapping.get('open', 'open'), 0)) if tick.get(field_mapping.get('open', 'open')) else None,
            exchange=field_mapping.get('exchange', 'UNKNOWN'),
            raw_data=tick
        )

import sqlite3
import pytz
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.logger_factory import get_logger
from src.core.event_bus import Subscriber, FullQuoteEvent


def get_ist_date_string() -> str:
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)
    return now_ist.strftime('%Y%m%d')


DATA_DIR = Path("data/db")
DATA_DIR.mkdir(exist_ok=True)


class FullQuoteDatabase(Subscriber):
    """Database handler for storing complete raw quote data from FullQuoteEvent."""
    
    def __init__(self, db_dir: str = DATA_DIR, date: str = get_ist_date_string(), symbol: str = "FULL_QUOTES"):
        super().__init__()
        self.table_name = f"full_quotes_{symbol}_{date}"
        self.db_path = str(db_dir / self.table_name) + ".db"
        self._logger = get_logger("FullQuoteDatabase")
        self._cx = None
        self._ensure_table_exists()
        
        # Subscribe to FullQuoteEvent
        self.subscribe_to_event(FullQuoteEvent, self._on_full_quote_event)
        
        self._logger.info(f"Initialized FullQuoteDatabase at {self.db_path} for symbol {symbol} on date {date} with table {self.table_name}")
    
    def _on_full_quote_event(self, event: FullQuoteEvent):
        """Handle FullQuoteEvent and save to database."""
        self.save_full_quote(event)
    
    def _get_connection(self) -> sqlite3.Connection:
        if self._cx is None:
            self._cx = sqlite3.connect(self.db_path, isolation_level=None)
        return self._cx
    
    def _ensure_table_exists(self) -> None:
        table_name = self.table_name
        self._logger.debug(f"Ensuring table exists: {table_name}")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                instrument TEXT NOT NULL,
                name TEXT NOT NULL,
                raw_data TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp 
            ON {table_name} (timestamp)
            """)
            
            cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_instrument 
            ON {table_name} (instrument, timestamp)
            """)
            
            conn.commit()
        self._logger.debug(f"Ensured table exists: {table_name}")
    
    def save_full_quote(self, event: FullQuoteEvent) -> bool:
        """Save FullQuoteEvent to database."""
        self._ensure_table_exists()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(f"""
                INSERT INTO {self.table_name} 
                (timestamp, source, instrument, name, raw_data)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    event.timestamp.isoformat(),
                    event.source,
                    event.instrument,
                    event.name,
                    json.dumps(event.raw_data)
                ))
                
                conn.commit()
                self._logger.debug(f"Saved full quote for {event.instrument} at {event.timestamp}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error saving full quote: {e}")
            return False
    
    def get_latest_full_quote(self, instrument: str) -> Optional[Dict[str, Any]]:
        """Get the latest full quote for an instrument."""
        table_name = self.table_name
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
            """, (table_name,))
            
            if not cursor.fetchone():
                return None
            
            cursor.execute(f"""
            SELECT * FROM {table_name} 
            WHERE instrument = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
            """, (instrument,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            columns = [desc[0] for desc in cursor.description]
            quote = dict(zip(columns, row))
            
            # Parse raw_data JSON
            if quote.get('raw_data'):
                quote['raw_data'] = json.loads(quote['raw_data'])
                
            self._logger.debug(f"Fetched latest full quote for {instrument}")
            return quote
    
    def get_full_quotes_in_range(self, instrument: str, 
                                start_time: datetime, 
                                end_time: datetime) -> List[Dict[str, Any]]:
        """Get full quotes for an instrument within a time range."""
        table_name = self.table_name
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
            """, (table_name,))
            
            if not cursor.fetchone():
                return []
            
            cursor.execute(f"""
            SELECT * FROM {table_name}
            WHERE instrument = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp
            """, (instrument, start_time.isoformat(), end_time.isoformat()))
            
            columns = [desc[0] for desc in cursor.description]
            quotes = []
            
            for row in cursor.fetchall():
                quote = dict(zip(columns, row))
                if quote.get('raw_data'):
                    quote['raw_data'] = json.loads(quote['raw_data'])
                quotes.append(quote)
        
        self._logger.debug(f"Fetched {len(quotes)} full quotes for {instrument} between {start_time} and {end_time}")
        return quotes
    
    def get_quote_count(self, instrument: str = None) -> int:
        """Get count of quotes in database."""
        table_name = self.table_name
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if instrument:
                cursor.execute(f"""
                SELECT COUNT(*) FROM {table_name} WHERE instrument = ?
                """, (instrument,))
            else:
                cursor.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                """)
            
            return cursor.fetchone()[0]
    
    def cleanup_old_quotes(self, days_to_keep: int = 7) -> int:
        """Remove quotes older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        table_name = self.table_name
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(f"""
            DELETE FROM {table_name} WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
        
        self._logger.info(f"Cleaned up {deleted_count} old quotes older than {days_to_keep} days")
        return deleted_count

import sqlite3
import pytz
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import json
from src.logger_factory import get_logger
import traceback


def get_ist_date_string() -> str:
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)
    return now_ist.strftime('%Y%m%d')

DATA_DIR = Path("data/db")
DATA_DIR.mkdir(exist_ok=True)


class QuoteDatabase:
    def __init__(self, db_dir: str = DATA_DIR,date: str = get_ist_date_string(),symbol: str = "NSE_OPTIONS",):
        self.table_name = f"quotes_{symbol}_{date}"
        self.db_path = str(db_dir / self.table_name)+".db"
        self._logger = get_logger("QuoteDatabase")
        self._cx = None
        self._ensure_table_exists()
        self._logger.info(f"Initialized QuoteDatabase at {self.db_path} for symbol {symbol} on date {date} with table {self.table_name}")
        
    
    def _get_connection(self) -> sqlite3.Connection:
        if(self._cx is None):
            self._cx = sqlite3.connect(self.db_path, isolation_level=None)
        return self._cx
    
    def _ensure_table_exists(self) -> None:
        table_name = self.table_name
        self._logger.debug(f"Ensuring table exists: {table_name}")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                ts TEXT,
                inst TEXT,
                name TEXT,
                ltp REAL,
                ltq INTEGER,
                volume INTEGER,
                change REAL,
                average_price REAL,
                buy_quantity INTEGER,
                sell_quantity INTEGER,
                ohlc TEXT,
                depth TEXT,
                last_trade_time TEXT,
                PRIMARY KEY(ts, inst)
            )
            """)
            
            cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_inst 
            ON {table_name} (inst, ts)
            """)
            
            conn.commit()
        self._logger.debug(f"Ensured table exists: {table_name}")
    
    def save_quote(self, quote: Dict[str, Any]) -> bool:
        self._ensure_table_exists()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                data = {
                    'ts': quote.get('timestamp', datetime.now()).isoformat(),
                    'inst': str(quote.get('instrument_token', '')),
                    'name': quote.get('name', ''),
                    'ltp': quote.get('last_price'),
                    'ltq': quote.get('last_quantity'),
                    'volume': quote.get('volume'),
                    'change': quote.get('change'),
                    'average_price': quote.get('average_price'),
                    'buy_quantity': quote.get('buy_quantity'),
                    'sell_quantity': quote.get('sell_quantity'),
                    'ohlc': json.dumps(quote.get('ohlc', {})) if quote.get('ohlc') else None,
                    'depth': json.dumps(quote.get('depth', {})) if quote.get('depth') else None
                }
                
                table_name = self.table_name
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['?'] * len(data))
                updates = ', '.join([f"{k} = excluded.{k}" for k in data.keys()])
                
                query = f"""
                INSERT INTO {table_name} ({columns})
                VALUES ({placeholders})
                ON CONFLICT(ts, inst) DO UPDATE SET {updates}
                """
                
                cursor.execute(query, list(data.values()))
                conn.commit()
                self._logger.debug(f"Saved quote for inst={data['inst']} at {data['ts']}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error saving quote: {e}\n{traceback.format_exc()}")
            return False
    
    def get_latest_quote(self, instrument_token: int) -> Optional[Dict[str, Any]]:
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
            WHERE inst = ? 
            ORDER BY ts DESC 
            LIMIT 1
            """, (str(instrument_token),))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            columns = [desc[0] for desc in cursor.description]
            quote = dict(zip(columns, row))
            
            if quote.get('ohlc'):
                quote['ohlc'] = json.loads(quote['ohlc'])
            if quote.get('depth'):
                quote['depth'] = json.loads(quote['depth'])
                
            self._logger.debug(f"Fetched latest quote for {instrument_token}: {quote if row else 'None'}")
            return quote
    
    def get_quotes_in_range(self, instrument_token: int, 
                           start_time: datetime, 
                           end_time: datetime) -> List[Dict[str, Any]]:
        ist = pytz.timezone("Asia/Kolkata")
        if start_time.tzinfo is None:
            start_time = pytz.utc.localize(start_time)
        if end_time.tzinfo is None:
            end_time = pytz.utc.localize(end_time)
            
        start_time_ist = start_time.astimezone(ist)
        end_time_ist = end_time.astimezone(ist)
        
        current_date = start_time_ist.date()
        end_date = end_time_ist.date()
        date_strings = []
        
        while current_date <= end_date:
            date_strings.append(current_date.strftime('%Y%m%d'))
            current_date = current_date.replace(day=current_date.day + 1)
        
        all_quotes = []
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for date_str in date_strings:
                table_name = f"quotes_{date_str}"
                
                cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
                """, (table_name,))
                
                if not cursor.fetchone():
                    continue
                
                query_start = start_time_ist.isoformat() if date_str == date_strings[0] else None
                query_end = end_time_ist.isoformat() if date_str == date_strings[-1] else None
                
                query = f"""
                SELECT * FROM {table_name}
                WHERE inst = ?
                """
                
                params = [str(instrument_token)]
                
                if query_start and query_end:
                    query += " AND ts BETWEEN ? AND ?"
                    params.extend([query_start, query_end])
                elif query_start:
                    query += " AND ts >= ?"
                    params.append(query_start)
                elif query_end:
                    query += " AND ts <= ?"
                    params.append(query_end)
                    
                query += " ORDER BY ts"
                
                cursor.execute(query, params)
                
                columns = [desc[0] for desc in cursor.description]
                
                for row in cursor.fetchall():
                    quote = dict(zip(columns, row))
                    if quote.get('ohlc'):
                        quote['ohlc'] = json.loads(quote['ohlc'])
                    if quote.get('depth'):
                        quote['depth'] = json.loads(quote['depth'])
                    all_quotes.append(quote)
        
        self._logger.debug(f"Fetched {len(all_quotes)} quotes for {instrument_token} between {start_time} and {end_time}")
        return all_quotes
# # Example usage:
# if __name__ == "__main__":
#     # Example of how to use the QuoteDatabase
#     db = QuoteDatabase("example_quotes.db")
    
#     # Example quote data
#     example_quote = {
#         'instrument_token': 53490439,
#         'mode': 'full',
#         'volume': 12510,
#         'last_price': 4084.0,
#         'average_price': 4086.55,
#         'last_quantity': 1,
#         'buy_quantity': 2356,
#         'sell_quantity': 2440,
#         'change': 0.46740467404674046,
#         'last_trade_time': datetime.now(),
#         'timestamp': datetime.now(),
#         'ohlc': {
#             'high': 4093.0,
#             'close': 4065.0,
#             'open': 4088.0,
#             'low': 4080.0
#         },
#         'depth': {
#             'buy': [
#                 {'price': 4084.0, 'quantity': 53, 'orders': 10},
#                 {'price': 4083.0, 'quantity': 145, 'orders': 12}
#             ],
#             'sell': [
#                 {'price': 4085.0, 'quantity': 43, 'orders': 8},
#                 {'price': 4086.0, 'quantity': 134, 'orders': 15}
#             ]
#         }
#     }
    
#     # Save the quote
#     quote_id = db.save_quote(example_quote)
#     print(f"Saved quote with ID: {quote_id}")
    
#     # Retrieve the latest quote
#     latest = db.get_latest_quote(53490439)
#     print(f"Latest quote: {latest}")

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import json
from src.logger_factory import get_logger
import traceback
import threading
import queue

DATA_DIR = Path("data/db")
DATA_DIR.mkdir(exist_ok=True)

class QuoteDatabaseBinance:
    def __init__(self, db_dir: str = DATA_DIR, date: str = datetime.now().strftime('%Y%m%d'), symbol: str = "BINANCE"):
        self.table_name = f"quotes_{symbol}_{date}"
        self.db_path = str(db_dir / self.table_name) + ".db"
        self._logger = get_logger("QuoteDatabaseBinance")
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._db_writer, daemon=True)
        self._thread.start()
        self._logger.info(f"Initialized QuoteDatabaseBinance at {self.db_path} for symbol {symbol} on date {date}")

    def _get_connection(self) -> sqlite3.Connection:
        # Always create a new connection in the DB thread
        return sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)

    def _ensure_table_exists(self, conn=None) -> None:
        table_name = self.table_name
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            ts TEXT,
            inst TEXT,
            name TEXT,
            ltp REAL,
            volume REAL,
            change REAL,
            PRIMARY KEY(ts, inst)
        )
        """)
        cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{table_name}_inst 
        ON {table_name} (inst, ts)
        """)
        conn.commit()

    def _db_writer(self):
        conn = self._get_connection()
        self._ensure_table_exists(conn)
        while not self._stop_event.is_set():
            try:
                quote = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                cursor = conn.cursor()
                data = {
                    'ts': quote.get('ts', datetime.now()).isoformat() if isinstance(quote.get('ts'), datetime) else str(quote.get('ts')),
                    'inst': str(quote.get('inst', '')),
                    'name': quote.get('name', ''),
                    'ltp': quote.get('ltp'),
                    'volume': quote.get('volume'),
                    'change': quote.get('change'),
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
                self._logger.debug(f"Saved Binance quote for inst={data['inst']} at {data['ts']}")
            except Exception as e:
                self._logger.error(f"Error saving Binance quote: {e}\n{traceback.format_exc()}")

    def save_quote(self, quote: Dict[str, Any]) -> bool:
        # Just enqueue the quote for the DB thread
        try:
            self._queue.put(quote)
            return True
        except Exception as e:
            self._logger.error(f"Error enqueuing Binance quote: {e}\n{traceback.format_exc()}")
            return False

    def get_latest_quote(self, inst: str) -> Optional[Dict[str, Any]]:
        # This method is called from main thread, so use a new connection
        table_name = self.table_name
        conn = self._get_connection()
        self._ensure_table_exists(conn)
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
        """, (str(inst),))
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        quote = dict(zip(columns, row))
        return quote

    def get_quotes_in_range(self, inst: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        # For brevity, not implemented here. Similar to QuoteDatabase.
        return []

    def stop(self):
        self._stop_event.set()
        self._thread.join()

import os
import sqlite3
from datetime import datetime
from src.core.event_bus.mixins import Subscriber
from src.core.event_bus.events import QuoteEvent

class QuoteEventDBSubscriber(Subscriber):
    def __init__(self, db_dir="./quote_event_dbs"):
        super().__init__()
        self.db_dir = db_dir
        os.makedirs(self.db_dir, exist_ok=True)
        # No connection cache
        self.subscribe_to_event(QuoteEvent, self._on_quote_event)

    def _get_db_path(self, instrument, date):
        filename = f"{instrument}_{date}.db"
        return os.path.join(self.db_dir, filename)

    def _on_quote_event(self, event: QuoteEvent):
        if not isinstance(event, QuoteEvent):
            return
        date_str = event.timestamp.strftime("%Y%m%d")
        db_path = self._get_db_path(event.instrument, date_str)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quote_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instrument TEXT,
                    name TEXT,
                    ltp REAL,
                    ltq REAL,
                    timestamp TEXT,
                    source TEXT
                )
            """)
            conn.execute(
                "INSERT INTO quote_events (instrument, name, ltp, ltq, timestamp, source) VALUES (?, ?, ?, ?, ?, ?)",
                (event.instrument, event.name, event.ltp, event.ltq, event.timestamp.isoformat(), event.source)
            )
            conn.commit()
        finally:
            conn.close()

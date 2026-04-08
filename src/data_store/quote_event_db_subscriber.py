import os
import sqlite3
from datetime import datetime, date
from typing import Dict, Tuple
from src.core.event_bus.mixins import Subscriber
from src.core.event_bus.events import QuoteEvent
from src.system_config_manager import SystemConfigManager
from src.logger_factory import get_logger


class QuoteEventDBSubscriber(Subscriber):
    """
    Persists QuoteEvents to SQLite in the same layout the backtest expects:

        data/{streamer}/{YYYY}/{MM}/ticks_{YYYYMMDD}.db
            table: ticks (ts, symbol_id, ltp, ltq)

    One connection is kept open per db file and reused across events.
    Connections are refreshed when the calendar date rolls over.
    WAL mode is enabled for safe concurrent reads by the backtest.
    """

    def __init__(self):
        super().__init__()
        self._logger = get_logger("QuoteEventDBSubscriber")
        streamer = SystemConfigManager().get_active_streamer()
        self._base_dir = os.path.join("data", streamer)
        # Cache: db_path -> (connection, date)
        self._conns: Dict[str, Tuple[sqlite3.Connection, date]] = {}
        self.subscribe_to_event(QuoteEvent, self._on_quote_event)
        self._logger.info(f"QuoteEventDBSubscriber ready — writing to {self._base_dir}/")

    # ── Path helpers ──────────────────────────────────────────────────────────

    def _db_path(self, ts: datetime) -> str:
        return os.path.join(
            self._base_dir,
            str(ts.year),
            f"{ts.month:02d}",
            f"ticks_{ts.strftime('%Y%m%d')}.db",
        )

    # ── Connection management ─────────────────────────────────────────────────

    def _get_conn(self, db_path: str, today: date) -> sqlite3.Connection:
        cached = self._conns.get(db_path)
        if cached:
            conn, cached_date = cached
            if cached_date == today:
                return conn
            # Date rolled — close old connection
            try:
                conn.close()
            except Exception:
                pass

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticks (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT    NOT NULL,
                symbol_id TEXT    NOT NULL,
                ltp       REAL    NOT NULL,
                ltq       REAL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks (symbol_id, ts)"
        )
        conn.commit()
        self._conns[db_path] = (conn, today)
        self._logger.info(f"Opened DB: {db_path}")
        return conn

    # ── Event handler ─────────────────────────────────────────────────────────

    def _on_quote_event(self, event: QuoteEvent):
        ts      = event.timestamp
        db_path = self._db_path(ts)
        try:
            conn = self._get_conn(db_path, ts.date())
            conn.execute(
                "INSERT INTO ticks (ts, symbol_id, ltp, ltq) VALUES (?, ?, ?, ?)",
                (ts.isoformat(), event.instrument, event.ltp, event.ltq),
            )
            conn.commit()
        except Exception as e:
            self._logger.error(f"DB write error [{db_path}]: {e}")

    def close(self):
        for conn, _ in self._conns.values():
            try:
                conn.close()
            except Exception:
                pass
        self._conns.clear()

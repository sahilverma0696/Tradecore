import sqlite3
from datetime import datetime
from logger_factory import get_logger  # Import the logger factory

class QuoteStreamer:
    def __init__(self, db_file, table_name, date_filter, name_filter):
        """
        Stream quotes from SQLite database based on table, date, and name filter.
        """
        self.db_file = db_file
        self.table_name = table_name
        self.date_filter = date_filter
        self.name_filter = name_filter
        self.quote_handlers = []
        self.logger = get_logger("quotes")  # Logger for QuoteStreamer

        self.logger.info(f"Initialized QuoteStreamer for {self.name_filter} on {self.date_filter}")

    def register_handler(self, handler_func):
        """
        Register a handler that will be called with each quote.
        """
        if callable(handler_func):
            self.quote_handlers.append(handler_func)
            self.logger.debug("Registered a new quote handler")

    def stream_quotes(self):
        """
        Stream quotes row-by-row from SQLite and dispatch to handlers.
        """
        self.logger.info(f"Starting quote stream from {self.table_name}")
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        query = f"SELECT ts, inst, name, ltp, ltq, cp FROM {self.table_name} ORDER BY ts ASC"
        cursor.execute(query)

        row_count = 0
        for ts, inst, name, ltp, ltq, cp in cursor.fetchall():
            ts_dt = datetime.fromisoformat(ts)

            # Apply date and name filter
            if ts_dt.date().isoformat() != self.date_filter:
                continue
            if name != self.name_filter:
                continue

            quote = {
                'ts': ts_dt,
                'inst': inst,
                'name': name,
                'ltp': ltp,
                'ltq': ltq,
                'cp': cp,
            }

            self.logger.debug(f"Streaming quote: {quote}")
            row_count += 1

            for handler in self.quote_handlers:
                handler(quote)

        conn.close()
        self.logger.info(f"Finished streaming {row_count} quotes")


# def example_handler(quote):
#     print(f"Got quote at {quote['ts']} for {quote['name']}: LTP = {quote['ltp']}")

# streamer = QuoteStreamer(
#     db_file="../../data/upstox/upstox_ltp.db",
#     table_name="quotes_20250625",
#     date_filter="2025-06-25",
#     name_filter="NIFTY 25000 CE 26 JUN 25"
# )

# # streamer.register_handler(example_handler)
# streamer.stream_quotes()

import os
import sqlite3
from datetime import datetime, time as dt_time
from kiteconnect import KiteTicker
import threading
import queue
import time
import logging

logging.basicConfig(level=logging.DEBUG)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def setup_database():
    current_time = datetime.now().strftime("%Y_%m_%d")
    db_file = os.path.join(DATA_DIR, f'stock_feed_{current_time}.db')
    conn = sqlite3.connect(db_file, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_token INTEGER,
            last_price REAL,
            volume INTEGER,
            timestamp TEXT
        )
    ''')
    conn.commit()
    return conn

def insert_data(conn, data):
    cursor = conn.cursor()
    try:
        cursor.executemany('''
            INSERT INTO stock_feed (instrument_token, last_price, volume, timestamp)
            VALUES (?, ?, ?, ?)
        ''', data)
        conn.commit()
        logging.debug(f"{len(data)} rows inserted into the database.")
    except Exception as e:
        logging.error(f"Failed to insert data into the database: {e}")

def db_worker(conn, q):
    while True:
        data_batch = q.get()
        if data_batch is None:
            break
        insert_data(conn, data_batch)
        q.task_done()

def on_ticks(ws, ticks):
    global last_data_time
    last_data_time = time.time()
    logging.debug("Ticks: {}".format(ticks))
    data = [
        (
            tick['instrument_token'],
            tick['last_price'],
            tick.get('volume', 0),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        for tick in ticks
    ]
    data_queue.put(data)

def on_connect(ws, response):
    logging.info("WebSocket connected successfully.")
    ws.subscribe(inst_tokens)
    ws.set_mode(ws.MODE_FULL, inst_tokens)

def on_close(ws, code, reason):
    logging.warning(f"WebSocket closed: {reason}. Attempting to reconnect...")
    attempt_reconnect()

def attempt_reconnect():
    time.sleep(1)
    logging.info("Attempting to reconnect...")
    connect_and_subscribe()

def connect_and_subscribe():
    global kws
    try:
        kws.connect(threaded=True)
    except Exception as e:
        logging.error(f"Exception while reconnecting: {e}")
        time.sleep(1)
        attempt_reconnect()

def check_data_flow():
    global last_data_time
    market_close_time = dt_time(15, 30)
    while True:
        current_time = datetime.now().time()
        if current_time >= market_close_time:
            logging.info("Market closed. Stopping reconnection attempts.")
            break
        if time.time() - last_data_time > 1:
            logging.warning("Data delay detected. Attempting to reconnect.")
            attempt_reconnect()
        time.sleep(1)

def wait_until_market_start():
    now = datetime.now()
    start_time = now.replace(hour=9, minute=14, second=55, microsecond=0)
    if now >= start_time:
        logging.info("⏰ Already past 09:14:55 AM. Starting immediately.")
        return
    wait_seconds = (start_time - now).total_seconds()
    logging.info(f"😴 Sleeping for {int(wait_seconds)} seconds until 09:14 AM...")
    try:
        time.sleep(wait_seconds)
    except Exception as e:
        logging.error(f"💥 Error during sleep before market start: {e}")
    logging.info("🌞 Waking up! Starting WebSocket stream...")

def main():
    global kws, last_data_time, data_queue, inst_tokens

    # Calculate and sleep until market start
    wait_until_market_start()

    # After waking up, create the instance and connect
    try:
        db_connection = setup_database()
        data_queue = queue.Queue(maxsize=1000)

        db_thread = threading.Thread(target=db_worker, args=(db_connection, data_queue), daemon=True)
        db_thread.start()

        api_key = "zy7p41049ggnphlu"
        access_token = "your_access_token_here"  # Replace with your actual access token
        kws = KiteTicker(api_key, access_token)

        kws.on_ticks = on_ticks
        kws.on_connect = on_connect
        kws.on_close = on_close

        inst_tokens = [10250754,10251778,10252546,10252802,10254850,10255106]

        last_data_time = time.time()
        connect_and_subscribe()

        data_flow_thread = threading.Thread(target=check_data_flow, daemon=True)
        data_flow_thread.start()

        logging.info("🚀 Stock feed streamer started successfully!")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("🛑 Keyboard interrupt received. Exiting gracefully.")
            kws.unsubscribe(inst_tokens)
            kws.stop()
            data_queue.put(None)
            db_thread.join()
            db_connection.close()
    except Exception as e:
        logging.error(f"❌ Failed to initialize after sleep: {e}")

if __name__ == "__main__":
    main()

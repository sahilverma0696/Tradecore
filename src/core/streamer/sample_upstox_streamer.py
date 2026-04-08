import asyncio
import json
import ssl
import websockets
import requests
import sqlite3
import datetime
import pytz
import time
from google.protobuf.json_format import MessageToDict

import fetcher.MarketDataFeedV3_pb2 as pb


def get_ist_date_string():
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.datetime.now(ist)
    return now_ist.strftime('%Y%m%d')  # e.g., '20250620'


# --- Configuration ---
MODE = "full"  # 'ltp', 'ltpc', or 'full'
DB_FILE = "data/upstox/upstox_ltp.db"
TIMEZONE = "Asia/Kolkata"
START_HOUR = 9
START_MINUTE = 14
END_HOUR = 15
END_MINUTE = 31
DAILY_TABLE_NAME = f"quotes_{get_ist_date_string()}"
# -----------------------



def get_market_data_feed_authorize(access_token):
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    url = 'https://api.upstox.com/v3/feed/market-data-feed/authorize'
    api_response = requests.get(url=url, headers=headers)
    return api_response.json()


def decode_protobuf(buffer):
    feed_response = pb.FeedResponse()
    feed_response.ParseFromString(buffer)
    return feed_response


def get_ist_now():
    return datetime.datetime.now(pytz.utc).astimezone(pytz.timezone(TIMEZONE)).isoformat()


def setup_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {DAILY_TABLE_NAME} (
            ts TEXT,
            inst TEXT,
            name TEXT,
            ltp REAL,
            ltq INTEGER,
            cp REAL,
            PRIMARY KEY(ts, inst)
        )
    ''')
    return conn

def save_ltp(conn, ts, inst, name, ltp, ltq, cp):
    try:
        conn.execute(f'''
            REPLACE INTO {DAILY_TABLE_NAME}
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ts, inst, name, ltp, ltq, cp))
        conn.commit()
        print(f"{ts} | {inst} | {name} | LTP={ltp}, LTQ={ltq}, CP={cp}")
    except Exception as e:
        print("DB Error:", e)


def wait_until_market_start():
    """Sleep until 09:14 AM IST"""
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    start_time = now.replace(hour=START_HOUR, minute=START_MINUTE, second=0, microsecond=0)
    
    if now >= start_time:
        print("⏱ Already past 09:14 AM IST. Starting immediately.")
        return
    
    wait_seconds = (start_time - now).total_seconds()
    print(f"🛌 Sleeping for {int(wait_seconds)} seconds until 09:14 AM IST...")
    time.sleep(wait_seconds)
    print("🔔 Waking up! Starting WebSocket stream...")


def is_market_closed():
    """Check if current time is past 15:31 IST"""
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    return now.hour > END_HOUR or (now.hour == END_HOUR and now.minute >= END_MINUTE)


async def fetch_market_data(access_token: str, keys: list, symbol_to_name: dict):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    conn = setup_db()
    wait_until_market_start()

    response = get_market_data_feed_authorize(access_token)
    ws_url = response["data"]["authorized_redirect_uri"]

    async with websockets.connect(ws_url, ssl=ssl_context) as websocket:
        print("✅ WebSocket connection established.")
        await asyncio.sleep(1)

        data = {
            "guid": "someguid",
            "method": "sub",
            "data": {
                "mode": MODE,
                "instrumentKeys": keys
            }
        }

        await websocket.send(json.dumps(data).encode('utf-8'))
        print("📡 Subscribed to instruments.")

        while True:
            if is_market_closed():
                print("🛑 Market closed at 15:31 IST. Exiting...")
                break

            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                decoded = decode_protobuf(message)
                feed_dict = MessageToDict(decoded)

                for inst, data in feed_dict.get("feeds", {}).items():
                    market_ff = data.get("fullFeed", {}).get("marketFF", {})
                    ltpc_data = market_ff.get("ltpc", {})

                    if ltpc_data:
                        try:
                            ltp = float(ltpc_data.get("ltp", 0))
                            ltq = int(ltpc_data.get("ltq", "0"))
                            cp = float(ltpc_data.get("cp", 0))
                            ts = get_ist_now()
                            name = symbol_to_name.get(inst, "UNKNOWN")
                            save_ltp(conn, ts, inst, name, ltp, ltq, cp)
                        except Exception as e:
                            print("❌ Error parsing LTP data:", e)

            except asyncio.TimeoutError:
                print("⚠️ No data received in 10 seconds. Still listening...")
            except Exception as e:
                print("❌ Error receiving/parsing data:", e)

    conn.close()
    print("💾 Database connection closed.")
    

# if __name__ == "__main__":
    
#     asyncio.run(fetch_market_data('ACCESS_TOKEN', []))
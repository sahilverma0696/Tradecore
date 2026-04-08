#!/usr/bin/env python3
"""
trade_streamer.py

Single-file monolith that:
 - Starts a local Flask server with an endpoint /webhook to receive posted trade updates
 - Runs a generator that simulates LTP and LTQ for a symbol (sample123)
 - Posts 4 updates per second to the webhook (default http://127.0.0.1:5000/webhook)
 - Keeps received messages in-memory and exposes /last?n= to view the last n messages

Usage:
    python trade_streamer.py
    
| Variable         | Meaning                                           | Effect if you **decrease** it         | Effect if you **increase** it |
| ---------------- | ------------------------------------------------- | ------------------------------------- | ----------------------------- |
| `sigma`          | volatility (size of random shocks)                | 🔹 **Smaller jumps** between ticks    | 🔹 Bigger jumps               |
| `theta`          | how strongly price is pulled back toward the mean | 🔹 Slower correction / smoother drift | 🔹 Faster reversion           |
| `momentum_decay` | how long a directional push lasts                 | 🔹 Price changes become more jittery  | 🔹 Price trends more smoothly |

"""

import threading
import time
import math
import random
import json
from datetime import datetime, timezone
from collections import deque
import signal
import sys
import argparse

import requests
from flask import Flask, request, jsonify

# ----------------------
# Config / CLI
# ----------------------
parser = argparse.ArgumentParser(description="Simulate LTP/LTQ stream and post to a local webhook.")
parser.add_argument("--symbol", default="sample123", help="Symbol name to emit")
parser.add_argument("--host", default="127.0.0.1", help="Host to run the receiver server on")
parser.add_argument("--port", type=int, default=5000, help="Port to run the receiver server on")
parser.add_argument("--webhook", default=None, help="Webhook URL to POST updates to. Defaults to local server /webhook.")
parser.add_argument("--rate", type=float, default=4.0, help="Updates per second (default 4)")
parser.add_argument("--seed", type=int, default=None, help="Random seed (optional)")
parser.add_argument("--start-price", type=float, default=250.0, help="Starting LTP (within 0-500)")
parser.add_argument("--min-price", type=float, default=0.0, help="Minimum price allowed")
parser.add_argument("--max-price", type=float, default=500.0, help="Maximum price allowed")
args = parser.parse_args()

if args.seed is not None:
    random.seed(args.seed)

WEBHOOK_URL = args.webhook or f"http://{args.host}:{args.port}/webhook"
SYMBOL = args.symbol
RATE_PER_SEC = float(args.rate)
INTERVAL = 1.0 / RATE_PER_SEC
START_PRICE = float(args.start_price)
MIN_PRICE = float(args.min_price)
MAX_PRICE = float(args.max_price)

# ----------------------
# Flask app (receiver)
# ----------------------
app = Flask(__name__)
# store last 2000 messages in-memory for quick inspection
RECEIVED_MESSAGES = deque(maxlen=2000)
RECEIVED_LOCK = threading.Lock()

@app.route("/webhook", methods=["POST"])
def webhook_receiver():
    try:
        payload = request.get_json(force=True)
    except Exception:
        return "Bad JSON", 400

    with RECEIVED_LOCK:
        RECEIVED_MESSAGES.append({
            "received_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload
        })
    # simple ack
    return jsonify({"status": "ok", "received": True}), 200

@app.route("/last", methods=["GET"])
def last_messages():
    # returns last n messages (default 20)
    try:
        n = int(request.args.get("n", 20))
    except Exception:
        n = 20
    with RECEIVED_LOCK:
        msgs = list(RECEIVED_MESSAGES)[-n:]
    return jsonify({"count": len(msgs), "messages": msgs}), 200

@app.route("/", methods=["GET"])
def index():
    return (
        "<h3>Trade Stream Receiver</h3>"
        f"<p>Posting to <code>{WEBHOOK_URL}</code></p>"
        "<p>POST JSON trade updates to <code>/webhook</code>. See <code>/last?n=</code> to retrieve recent messages.</p>"
    )

# ----------------------
# Price/Trade generator
# ----------------------
class PriceSimulator:
    """
    Ornstein-Uhlenbeck style mean-reverting price simulator bounded by min/max.
    Produces ltp (price) and ltq (last traded quantity) and trade volume.
    """

    def __init__(self, start_price=50.0, min_price=0.0, max_price=500.0):
        self.price = float(start_price)
        self.min_price = min_price
        self.max_price = max_price
        # target / long-run mean near current center (allow drift)
        self.mean = (min_price + max_price) / 2.0
        # momentum for small persistence
        self.momentum = 0.0
        # cumulative volume
        self.cum_vol = 0

    def step(self):
        # mean reversion strength
        theta = 0.05
        # volatility scale
        sigma = 0.5  # tune to make realistic tick size
        # momentum persistence
        momentum_decay = 0.85

        # noise
        noise = random.gauss(0, sigma)

        # push towards mean plus small random drift based on current momentum
        reversion = theta * (self.mean - self.price)
        # slowly change the mean a little to create market drift
        self.mean += random.gauss(0, 0.02)

        # update momentum
        self.momentum = self.momentum * momentum_decay + 0.2 * noise

        # new price
        new_price = self.price + reversion + self.momentum + noise * 0.1

        # reflect / clamp inside bounds
        if new_price < self.min_price:
            new_price = self.min_price + (self.min_price - new_price) * 0.5
        if new_price > self.max_price:
            new_price = self.max_price - (new_price - self.max_price) * 0.5

        # tiny rounding to mimic tick increments (e.g. 0.05 or 0.1)
        tick = 0.05
        new_price = round(new_price / tick) * tick
        # make sure in bounds after rounding
        new_price = max(self.min_price, min(self.max_price, new_price))

        # last traded quantity (ltq) -- number of contracts/shares in last trade
        # small trades more common; occasional larger trades
        r = random.random()
        if r < 0.85:
            ltq = random.randint(1, 10)  # small trade
        elif r < 0.98:
            ltq = random.randint(11, 100)  # medium trade
        else:
            ltq = random.randint(101, 1000)  # large trade (rare)

        # per-trade volume (last_traded_volume) — we map ltq to volume scaled by random multiplier
        last_traded_volume = ltq * random.randint(1, 5)

        self.cum_vol += last_traded_volume

        self.price = new_price
        return {
            "ltp": float(self.price),
            "ltq": int(ltq),
            "last_traded_volume": int(last_traded_volume),
            "cumulative_volume": int(self.cum_vol)
        }

# ----------------------
# Poster worker
# ----------------------
def poster_loop(stop_event: threading.Event):
    sim = PriceSimulator(start_price=START_PRICE, min_price=MIN_PRICE, max_price=MAX_PRICE)
    session = requests.Session()
    headers = {"Content-Type": "application/json"}
    print(f"[poster] Starting poster to {WEBHOOK_URL} at {RATE_PER_SEC} updates/sec (interval {INTERVAL:.3f}s).")
    while not stop_event.is_set():
        tick = sim.step()
        payload = {
            "symbol": SYMBOL,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ltp": tick["ltp"],
            "ltq": tick["ltq"],
            "last_traded_volume": tick["last_traded_volume"],
            "cumulative_volume": tick["cumulative_volume"],
        }
        try:
            resp = session.post(WEBHOOK_URL, json=payload, headers=headers, timeout=1.5)
            if resp.status_code != 200:
                # print once per failure but do not spam
                print(f"[poster] Warning: webhook returned status {resp.status_code}")
        except requests.RequestException as e:
            # If webhook down, keep simulating and print debug occasionally
            print(f"[poster] POST failed: {e}")
        # sleep respecting interval but wake earlier if stop_event set
        stop_event.wait(INTERVAL)
    print("[poster] stop_event set, poster loop ending.")

# ----------------------
# Threading / startup
# ----------------------
def run_flask_in_thread(host, port, stop_event):
    def run_app():
        # Flask.run is blocking; disable reloader and use the given host/port
        # We catch exceptions to allow the thread to exit gracefully
        try:
            app.run(host=host, port=port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"[flask] server stopped with exception: {e}")
        finally:
            stop_event.set()
    t = threading.Thread(target=run_app, daemon=True)
    t.start()
    return t

def main():
    stop_event = threading.Event()

    # gracefully handle CTRL+C
    def handle_sigint(sig, frame):
        print("\n[main] Signal received, shutting down...")
        stop_event.set()
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    # start flask server thread
    flask_thread = run_flask_in_thread(args.host, args.port, stop_event)
    # small wait for server to bind up
    time.sleep(0.5)

    # start poster in its own thread too (so main can do monitoring)
    poster_thread = threading.Thread(target=poster_loop, args=(stop_event,), daemon=True)
    poster_thread.start()

    print("[main] Running. Press Ctrl+C to stop.")
    try:
        # main loop just waits; you can add monitoring or stats here
        while not stop_event.is_set():
            # print stats every 5 seconds
            time.sleep(5)
            with RECEIVED_LOCK:
                received = len(RECEIVED_MESSAGES)
            print(f"[main] Alive. Received messages stored: {received}")
    except KeyboardInterrupt:
        stop_event.set()

    # wait shortly for threads to finish
    poster_thread.join(timeout=2.0)
    # Flask thread will exit when process stops or stop_event set
    print("[main] Exiting. Final stored messages:", len(RECEIVED_MESSAGES))

if __name__ == "__main__":
    main()

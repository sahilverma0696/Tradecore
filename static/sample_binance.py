import websocket
import json
import ssl

def on_message(ws, message):
    data = json.loads(message)
    print(f"Price: {data['p']}, Quantity: {data['q']}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connection opened")

if __name__ == "__main__":
    stream_url = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    ws = websocket.WebSocketApp(
        stream_url,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error
    )
    # Pass sslopt to disable certificate requirements
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

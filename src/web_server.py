from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import json
import os
from datetime import datetime
from typing import Dict, Any

class OrderWebServer:
    def __init__(self, order_manager, port=8081):
        # Get the project root directory (parent of src)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        template_dir = os.path.join(project_root, 'templates')
        
        self.app = Flask(__name__, template_folder=template_dir)
        self.app.config['SECRET_KEY'] = 'your-secret-key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.order_manager = order_manager
        self.port = port
        self.running = False
        
        self._setup_routes()
        self._setup_socketio_events()
    
    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('orders.html')
        
        @self.app.route('/api/orders')
        def get_orders():
            orders_data = {}
            if hasattr(self.order_manager, '_orders'):
                for name, order in self.order_manager._orders.items():
                    orders_data[name] = self._serialize_order(order)
            return jsonify(orders_data)
    
    def _setup_socketio_events(self):
        @self.socketio.on('connect')
        def handle_connect():
            print('Client connected')
            # Send initial order data
            orders_data = {}
            if hasattr(self.order_manager, '_orders'):
                for name, order in self.order_manager._orders.items():
                    orders_data[name] = self._serialize_order(order)
            emit('orders_update', orders_data)
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            print('Client disconnected')
    
    def _serialize_order(self, order):
        """Convert order object to dictionary for JSON serialization."""
        try:
            # Handle datetime objects for timestamp
            timestamp = getattr(order, 'timestamp', datetime.now())
            if hasattr(timestamp, 'strftime'):
                timestamp_str = timestamp.strftime('%H:%M:%S')
            else:
                timestamp_str = str(timestamp)
            
            # Handle different order object types (Zerodha vs others)
            symbol = getattr(order, 'symbol', getattr(order, 'tradingsymbol', 'N/A'))
            side = getattr(order, 'side', getattr(order, 'transaction_type', 'N/A'))
            
            # Calculate PnL if available
            pnl = getattr(order, 'pnl', 0)
            if pnl == 0:
                # Try to calculate PnL from entry_price and ltp
                entry_price = getattr(order, 'entry_price', getattr(order, 'average_price', 0))
                ltp = getattr(order, 'ltp', 0)
                quantity = getattr(order, 'filled_quantity', getattr(order, 'quantity', 0))
                if entry_price and ltp and quantity:
                    if side.upper() in ['BUY', 'LONG']:
                        pnl = (ltp - entry_price) * quantity
                    elif side.upper() in ['SELL', 'SHORT']:
                        pnl = (entry_price - ltp) * quantity
            
            return {
                'symbol': symbol,
                'side': side,
                'quantity': getattr(order, 'quantity', 0),
                'filled_quantity': getattr(order, 'filled_quantity', getattr(order, 'quantity', 0)),
                'price': getattr(order, 'price', getattr(order, 'average_price', 0)),
                'ltp': getattr(order, 'ltp', 0),
                'status': getattr(order, 'status', getattr(order, 'order_status', 'N/A')),
                'pnl': round(pnl, 2),
                'timestamp': timestamp_str,
                'order_type': getattr(order, 'order_type', getattr(order, 'product', 'N/A')),
                'entry_price': getattr(order, 'entry_price', getattr(order, 'average_price', 0)),
                'exit_price': getattr(order, 'exit_price', 0),
                'order_id': getattr(order, 'order_id', getattr(order, 'order_id', 'N/A'))
            }
        except Exception as e:
            self._logger.error(f"Error serializing order: {e}")
            return {
                'error': str(e),
                'symbol': 'Error',
                'side': 'N/A',
                'quantity': 0,
                'filled_quantity': 0,
                'price': 0,
                'ltp': 0,
                'status': 'ERROR',
                'pnl': 0,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'order_type': 'N/A',
                'entry_price': 0,
                'exit_price': 0
            }
    
    def broadcast_order_update(self, order_name, order):
        """Broadcast order update to all connected clients."""
        if self.running:
            order_data = self._serialize_order(order)
            self.socketio.emit('order_update', {
                'name': order_name,
                'data': order_data
            })
    
    def start_background_updates(self):
        """Start background thread for periodic updates."""
        def update_loop():
            while self.running:
                try:
                    orders_data = {}
                    if hasattr(self.order_manager, '_orders'):
                        for name, order in self.order_manager._orders.items():
                            orders_data[name] = self._serialize_order(order)
                    
                    self.socketio.emit('orders_update', orders_data)
                    time.sleep(1)  # Update every second
                except Exception as e:
                    print(f"Error in update loop: {e}")
                    time.sleep(1)
        
        self.running = True
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
    
    def run(self, debug=False):
        """Start the web server."""
        self.start_background_updates()
        print(f"Starting web server on http://localhost:{self.port}")
        self.socketio.run(self.app, host='0.0.0.0', port=self.port, debug=debug)
    
    def stop(self):
        """Stop the web server."""
        self.running = False

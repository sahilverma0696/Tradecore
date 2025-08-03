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
            return {
                'symbol': getattr(order, 'symbol', 'N/A'),
                'side': getattr(order, 'side', 'N/A'),
                'quantity': getattr(order, 'quantity', 0),
                'filled_quantity': getattr(order, 'filled_quantity', 0),
                'price': getattr(order, 'price', 0),
                'ltp': getattr(order, 'ltp', 0),
                'status': getattr(order, 'status', 'N/A'),
                'pnl': getattr(order, 'pnl', 0),
                'timestamp': getattr(order, 'timestamp', datetime.now()).strftime('%H:%M:%S') if hasattr(order, 'timestamp') else 'N/A',
                'order_type': getattr(order, 'order_type', 'N/A'),
                'entry_price': getattr(order, 'entry_price', 0),
                'exit_price': getattr(order, 'exit_price', 0)
            }
        except Exception as e:
            return {'error': str(e)}
    
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

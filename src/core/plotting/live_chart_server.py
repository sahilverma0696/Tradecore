import json
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import deque
from src.logger_factory import get_logger
import webbrowser

class ChartHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html_content = self.server.chart_server.get_html()
            self.wfile.write(html_content.encode())
        elif self.path == '/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = self.server.chart_server.get_chart_data()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default HTTP server logs
        pass

class LiveChartServer:
    def __init__(self, max_candles=100, port=8080):
        self.max_candles = max_candles
        self.port = port
        self.candles = deque(maxlen=max_candles)
        self._logger = get_logger("LiveChartServer")
        self.server = None
        self.server_thread = None
        # Add real-time price tracking
        self.current_price = None
        self.current_timestamp = None
        self.current_volume = 0
        self._logger.info(f"Initialized LiveChartServer with max_candles={max_candles}, port={port}")

    def add_quote(self, quote):
        """Handle real-time quote updates for immediate price display"""
        self.current_price = quote.get('ltp')
        
        # Handle timestamp conversion - could be datetime object, int (ms), or string
        ts = quote.get('ts', datetime.now())
        if isinstance(ts, datetime):
            self.current_timestamp = ts.isoformat()
        elif isinstance(ts, (int, float)):
            # Assume milliseconds timestamp from Binance
            self.current_timestamp = datetime.fromtimestamp(ts / 1000).isoformat()
        else:
            # Fallback to current time
            self.current_timestamp = datetime.now().isoformat()
            
        self.current_volume = quote.get('volume', 0)
        self._logger.debug(f"Real-time price updated: {self.current_price} at {self.current_timestamp}")

    def add_candle(self, name, candle):
        candle_data = {
            'timestamp': candle['timestamp'].isoformat(),
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'vwap': candle.get('vwap'),
            'volume': candle.get('volume', 0),
            'name': name
        }
        self.candles.append(candle_data)
        self._logger.info(f"Chart data updated for {name}: Close={candle['close']:.2f}, VWAP={candle.get('vwap', 'N/A')}, Volume={candle.get('volume', 0)}, Total candles={len(self.candles)}")

    def get_chart_data(self):
        candles_list = list(self.candles)
        if not candles_list:
            self._logger.debug("No candle data available for chart")
            return {
                'labels': [], 
                'ohlc': [], 
                'vwap': [], 
                'volume': [],
                'current_price': self.current_price,
                'current_timestamp': self.current_timestamp,
                'current_volume': self.current_volume
            }
        
        # Add detailed logging about candle data
        self._logger.debug(f"Processing {len(candles_list)} candles for chart data")
        for i, candle in enumerate(candles_list[-3:]):  # Log last 3 candles
            self._logger.debug(f"Candle {len(candles_list)-3+i}: {candle}")
        
        labels = [c['timestamp'] for c in candles_list]
        ohlc = [{
            'x': c['timestamp'],
            'o': c['open'],
            'h': c['high'],
            'l': c['low'],
            'c': c['close']
        } for c in candles_list]
        
        # Filter out None/null VWAP values and create proper line data
        vwap = []
        vwap_count = 0
        for c in candles_list:
            if c['vwap'] is not None:
                vwap.append({'x': c['timestamp'], 'y': c['vwap']})
                vwap_count += 1
        
        volume = [c['volume'] for c in candles_list]
        
        self._logger.debug(f"Chart data prepared: {len(ohlc)} candles, {vwap_count} VWAP points, {len(volume)} volume bars")
        
        return {
            'labels': labels,
            'ohlc': ohlc,
            'vwap': vwap,
            'volume': volume,
            'current_price': self.current_price,
            'current_timestamp': self.current_timestamp,
            'current_volume': self.current_volume
        }

    def get_html(self):
        return '''
<!DOCTYPE html>
<html>
<head>
    <title>VWAP Live Chart</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/date-fns@2.29.3/index.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-chart-financial@0.2.1/dist/chartjs-chart-financial.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        .stats { display: flex; justify-content: space-around; margin-bottom: 20px; }
        .stat-item { text-align: center; padding: 10px; background: #f8f9fa; border-radius: 4px; }
        .stat-value { font-size: 18px; font-weight: bold; color: #007bff; }
        .stat-label { font-size: 12px; color: #666; }
        .vwap-value { color: #000 !important; }
        .live-price { color: #28a745 !important; animation: pulse 1s infinite; }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>VWAP Trading System - Live Chart</h1>
        <div class="stats" id="stats">
            <div class="stat-item">
                <div class="stat-value live-price" id="last-price">-</div>
                <div class="stat-label">Live Price</div>
            </div>
            <div class="stat-item">
                <div class="stat-value vwap-value" id="vwap-price">-</div>
                <div class="stat-label">VWAP</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="volume">-</div>
                <div class="stat-label">Volume</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="candle-count">0</div>
                <div class="stat-label">Candles</div>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="priceChart" width="400" height="300"></canvas>
        </div>
        <div class="chart-container">
            <canvas id="volumeChart" width="400" height="100"></canvas>
        </div>
    </div>

    <script>
        const priceCtx = document.getElementById('priceChart').getContext('2d');
        const volumeCtx = document.getElementById('volumeChart').getContext('2d');
        
        const priceChart = new Chart(priceCtx, {
            type: 'candlestick',
            data: {
                datasets: [{
                    label: 'OHLC',
                    data: [],
                    borderColor: '#333',
                    color: {
                        up: 'rgba(38, 166, 154, 0.8)',
                        down: 'rgba(239, 83, 80, 0.8)',
                        unchanged: 'rgba(153, 153, 153, 0.8)'
                    }
                }, {
                    label: 'VWAP',
                    type: 'line',
                    data: [],
                    borderColor: '#000000',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    yAxisID: 'y'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm',
                                hour: 'HH:mm'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        type: 'linear',
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Price'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Price Chart with VWAP',
                        font: {
                            size: 16
                        }
                    }
                }
            }
        });

        const volumeChart = new Chart(volumeCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Volume',
                    data: [],
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Volume'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Volume Chart',
                        font: {
                            size: 16
                        }
                    }
                }
            }
        });

        function updateCharts() {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    console.log('Chart data received:', data);
                    
                    // Update OHLC data - convert to proper format for chartjs-chart-financial
                    if (data.ohlc && data.ohlc.length > 0) {
                        // Convert to the format expected by chartjs-chart-financial
                        const candlestickData = data.ohlc.map(candle => ({
                            x: new Date(candle.x),
                            o: candle.o,
                            h: candle.h,
                            l: candle.l,
                            c: candle.c
                        }));
                        priceChart.data.datasets[0].data = candlestickData;
                        console.log('OHLC candlestick data updated:', candlestickData.length, 'candles');
                    }
                    
                    // Update VWAP data
                    if (data.vwap && data.vwap.length > 0) {
                        const vwapData = data.vwap.map(point => ({
                            x: new Date(point.x),
                            y: point.y
                        }));
                        priceChart.data.datasets[1].data = vwapData;
                        console.log('VWAP data updated:', vwapData.length, 'points');
                    }
                    
                    // Update volume data
                    if (data.labels && data.volume) {
                        const volumeLabels = data.labels.map(label => new Date(label));
                        const volumeData = data.volume.map((vol, index) => ({
                            x: volumeLabels[index],
                            y: vol
                        }));
                        volumeChart.data.labels = volumeLabels;
                        volumeChart.data.datasets[0].data = volumeData;
                    }
                    
                    // Force chart updates with animation disabled for smoother updates
                    priceChart.update('none');
                    volumeChart.update('none');
                    
                    // Update stats with real-time data
                    if (data.current_price !== null && data.current_price !== undefined) {
                        document.getElementById('last-price').textContent = data.current_price.toFixed(2);
                    } else if (data.ohlc.length > 0) {
                        const lastCandle = data.ohlc[data.ohlc.length - 1];
                        document.getElementById('last-price').textContent = lastCandle.c?.toFixed(2) || '-';
                    }
                    
                    if (data.vwap.length > 0) {
                        const lastVwap = data.vwap[data.vwap.length - 1].y;
                        document.getElementById('vwap-price').textContent = lastVwap?.toFixed(2) || '-';
                    }
                    
                    if (data.current_volume !== null && data.current_volume !== undefined) {
                        document.getElementById('volume').textContent = data.current_volume.toLocaleString();
                    } else if (data.volume.length > 0) {
                        const lastVolume = data.volume[data.volume.length - 1];
                        document.getElementById('volume').textContent = lastVolume?.toLocaleString() || '-';
                    }
                    
                    document.getElementById('candle-count').textContent = data.ohlc.length;
                })
                .catch(error => console.error('Error fetching chart data:', error));
        }

        // Update every 500ms for more responsive live price updates
        setInterval(updateCharts, 500);
        updateCharts(); // Initial load
        
        console.log('Chart initialized with candlestick OHLC and live price updates every 500ms');
    </script>
</body>
</html>'''

    def start_server(self, open_browser=True):
        if self.server_thread and self.server_thread.is_alive():
            self._logger.warning("Server is already running")
            return

        def run_server():
            try:
                self.server = HTTPServer(('localhost', self.port), ChartHandler)
                self.server.chart_server = self
                self._logger.info(f"Starting chart server on http://localhost:{self.port}")
                if open_browser:
                    webbrowser.open(f'http://localhost:{self.port}')
                self.server.serve_forever()
            except Exception as e:
                self._logger.error(f"Error starting server: {e}")

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        time.sleep(1)  # Give server time to start

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self._logger.info("Chart server stopped")

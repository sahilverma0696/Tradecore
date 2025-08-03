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
        self._logger.info(f"Initialized LiveChartServer with max_candles={max_candles}, port={port}")

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
        self._logger.debug(f"Added candle for {name}: OHLC({candle['open']},{candle['high']},{candle['low']},{candle['close']}) VWAP({candle.get('vwap')})")

    def get_chart_data(self):
        candles_list = list(self.candles)
        if not candles_list:
            return {'labels': [], 'ohlc': [], 'vwap': [], 'volume': []}
        
        labels = [c['timestamp'] for c in candles_list]
        ohlc = [{
            'x': c['timestamp'],
            'o': c['open'],
            'h': c['high'],
            'l': c['low'],
            'c': c['close']
        } for c in candles_list]
        vwap = [c['vwap'] for c in candles_list]
        volume = [c['volume'] for c in candles_list]
        
        return {
            'labels': labels,
            'ohlc': ohlc,
            'vwap': vwap,
            'volume': volume
        }

    def get_html(self):
        return '''
<!DOCTYPE html>
<html>
<head>
    <title>VWAP Live Chart</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-chart-financial"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        .stats { display: flex; justify-content: space-around; margin-bottom: 20px; }
        .stat-item { text-align: center; padding: 10px; background: #f8f9fa; border-radius: 4px; }
        .stat-value { font-size: 18px; font-weight: bold; color: #007bff; }
        .stat-label { font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>VWAP Trading System - Live Chart</h1>
        <div class="stats" id="stats">
            <div class="stat-item">
                <div class="stat-value" id="last-price">-</div>
                <div class="stat-label">Last Price</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="vwap-price">-</div>
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
            <canvas id="priceChart" width="400" height="200"></canvas>
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
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                }, {
                    label: 'VWAP',
                    type: 'line',
                    data: [],
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    fill: false,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                interaction: {
                    intersect: false,
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute'
                        }
                    },
                    y: {
                        beginAtZero: false
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Price Chart with VWAP'
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
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute'
                        }
                    },
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: 'Volume Chart'
                    }
                }
            }
        });

        function updateCharts() {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    // Update OHLC data
                    priceChart.data.datasets[0].data = data.ohlc;
                    
                    // Update VWAP data
                    const vwapData = data.labels.map((label, index) => ({
                        x: label,
                        y: data.vwap[index]
                    }));
                    priceChart.data.datasets[1].data = vwapData;
                    
                    // Update volume data
                    volumeChart.data.labels = data.labels;
                    volumeChart.data.datasets[0].data = data.volume;
                    
                    priceChart.update('none');
                    volumeChart.update('none');
                    
                    // Update stats
                    if (data.ohlc.length > 0) {
                        const lastCandle = data.ohlc[data.ohlc.length - 1];
                        const lastVwap = data.vwap[data.vwap.length - 1];
                        const lastVolume = data.volume[data.volume.length - 1];
                        
                        document.getElementById('last-price').textContent = lastCandle.c?.toFixed(2) || '-';
                        document.getElementById('vwap-price').textContent = lastVwap?.toFixed(2) || '-';
                        document.getElementById('volume').textContent = lastVolume || '-';
                        document.getElementById('candle-count').textContent = data.ohlc.length;
                    }
                })
                .catch(error => console.error('Error fetching data:', error));
        }

        // Update every 2 seconds
        setInterval(updateCharts, 2000);
        updateCharts(); // Initial load
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

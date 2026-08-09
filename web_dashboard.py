"""
ARBITRAGE BOT WITH WEB DASHBOARD
Real-time monitoring from your browser!
"""

import asyncio
import aiohttp
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from threading import Thread
import json
import time

# ============================================
# CONFIGURATION
# ============================================

CONFIG = {
    'MIN_PROFIT_PERCENT': 0.05,
    'MIN_PROFIT_USD': 0.01,
    'TRADING_FEE': 0.001,
    'BASE_CURRENCIES': ['USDT', 'BTC', 'ETH'],
    'SCAN_INTERVAL': 5,
}

# ============================================
# EXCHANGE APIS
# ============================================

class BinanceAPI:
    async def get_prices(self):
        url = "https://api.binance.com/api/v3/ticker/24hr"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                prices = {}
                for item in data:
                    symbol = item['symbol']
                    if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                        try:
                            prices[symbol] = {
                                'bid': float(item.get('bidPrice', 0) or 0),
                                'ask': float(item.get('askPrice', 0) or 0),
                                'volume': float(item.get('volume', 0)) * float(item.get('lastPrice', 0) or 0),
                            }
                        except:
                            continue
                return prices

class BybitAPI:
    async def get_prices(self):
        url = "https://api.bybit.com/v5/market/tickers"
        params = {'category': 'spot'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                prices = {}
                if data.get('result', {}).get('list'):
                    for item in data['result']['list']:
                        symbol = item['symbol']
                        if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                            try:
                                prices[symbol] = {
                                    'bid': float(item.get('bid1Price', 0) or 0),
                                    'ask': float(item.get('ask1Price', 0) or 0),
                                    'volume': float(item.get('volume24h', 0)) * float(item.get('lastPrice', 0) or 0),
                                }
                            except:
                                continue
                return prices

# ============================================
# ARBITRAGE ENGINE
# ============================================

class ArbitrageEngine:
    def __init__(self):
        self.exchanges = {
            'binance': BinanceAPI(),
            'bybit': BybitAPI(),
        }
        self.opportunities = []
        self.stats = {
            'total_found': 0,
            'total_profit': 0,
            'last_scan': None,
            'exchanges_status': {}
        }
    
    async def scan(self):
        # Get prices
        all_prices = {}
        for name, exchange in self.exchanges.items():
            try:
                prices = await exchange.get_prices()
                if prices:
                    all_prices[name] = prices
                    self.stats['exchanges_status'][name] = 'online'
                else:
                    self.stats['exchanges_status'][name] = 'no_data'
            except Exception as e:
                self.stats['exchanges_status'][name] = f'error: {str(e)[:30]}'
        
        # Find opportunities
        opportunities = []
        pairs = {}
        
        for exchange_name, prices in all_prices.items():
            for pair, data in prices.items():
                if pair not in pairs:
                    pairs[pair] = {}
                pairs[pair][exchange_name] = data
        
        for pair, exchange_data in pairs.items():
            if len(exchange_data) < 2:
                continue
            
            buy_exchange = min(exchange_data.items(), key=lambda x: x[1]['ask'])
            sell_exchange = max(exchange_data.items(), key=lambda x: x[1]['bid'])
            
            buy_price = buy_exchange[1]['ask']
            sell_price = sell_exchange[1]['bid']
            
            if buy_price <= 0 or sell_price <= 0:
                continue
            
            raw_spread = (sell_price - buy_price) / buy_price * 100
            fee_spread = CONFIG['TRADING_FEE'] * 2 * 100
            net_spread = raw_spread - fee_spread
            
            if net_spread > CONFIG['MIN_PROFIT_PERCENT']:
                max_volume = min(
                    buy_exchange[1].get('volume', 0),
                    sell_exchange[1].get('volume', 0)
                )
                
                trade_sizes = [10, 50, 100, 500, 1000, 5000]
                for trade_size in trade_sizes:
                    if trade_size > max_volume:
                        continue
                        
                    investment = buy_price * (trade_size / sell_price)
                    gross_profit = (sell_price - buy_price) * (trade_size / sell_price)
                    net_profit = gross_profit - (investment * CONFIG['TRADING_FEE'] * 2)
                    
                    if net_profit > CONFIG['MIN_PROFIT_USD']:
                        opportunities.append({
                            'pair': pair,
                            'buy_exchange': buy_exchange[0],
                            'sell_exchange': sell_exchange[0],
                            'buy_price': buy_price,
                            'sell_price': sell_price,
                            'raw_spread': raw_spread,
                            'net_spread': net_spread,
                            'trade_size': trade_size,
                            'profit_usd': net_profit,
                            'roi': (net_profit / investment) * 100,
                            'investment': investment,
                            'max_volume': max_volume,
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        })
                        break
        
        # Sort and store
        opportunities.sort(key=lambda x: x['profit_usd'], reverse=True)
        self.opportunities = opportunities[:20]
        
        # Update stats
        if opportunities:
            self.stats['total_found'] += len(opportunities)
            self.stats['total_profit'] += sum(o['profit_usd'] for o in opportunities)
        self.stats['last_scan'] = datetime.now().strftime('%H:%M:%S')
        
        return opportunities

# ============================================
# FLASK WEB APP
# ============================================

app = Flask(__name__)
engine = ArbitrageEngine()

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🚀 Arbitrage Bot Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #00ff00;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1a1a, #0a0a0a);
            border: 1px solid #00ff00;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; color: #00ff00; text-shadow: 0 0 20px #00ff00; }
        .header .subtitle { color: #888; font-size: 0.9em; margin-top: 5px; }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #111;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .stat-card .value { font-size: 2em; font-weight: bold; color: #00ff00; }
        .stat-card .label { color: #888; font-size: 0.8em; margin-top: 5px; }
        .stat-card.online { border-color: #00ff00; }
        .stat-card.offline { border-color: #ff0000; }
        
        /* Opportunities Table */
        .opportunities {
            background: #111;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        .opportunities h2 { margin-bottom: 15px; color: #00ff00; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }
        th {
            background: #1a1a1a;
            color: #00ff00;
            padding: 12px;
            text-align: left;
            border-bottom: 2px solid #00ff00;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #222;
            color: #ccc;
        }
        tr:hover { background: #1a1a1a; }
        .profit-positive { color: #00ff00; font-weight: bold; }
        .profit-negative { color: #ff0000; }
        .exchange-tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .buy { background: #1a3a1a; color: #00ff00; }
        .sell { background: #3a1a1a; color: #ff4444; }
        .confidence {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            background: #1a3a1a;
            color: #00ff00;
        }
        
        /* Status indicator */
        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-dot.online { background: #00ff00; box-shadow: 0 0 10px #00ff00; }
        .status-dot.offline { background: #ff0000; box-shadow: 0 0 10px #ff0000; }
        
        @media (max-width: 768px) {
            .header h1 { font-size: 1.5em; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            table { font-size: 0.7em; }
            td, th { padding: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 ARBITRAGE BOT</h1>
            <div class="subtitle">Real-time crypto arbitrage monitoring</div>
            <div style="margin-top: 10px; color: #888; font-size: 0.85em;">
                Updated: {{ stats.last_scan }} | Scanning every {{ scan_interval }}s
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="value">{{ opportunities|length }}</div>
                <div class="label">Current Opportunities</div>
            </div>
            <div class="stat-card">
                <div class="value">${{ "%.2f"|format(stats.total_profit) }}</div>
                <div class="label">Total Profit Potential</div>
            </div>
            <div class="stat-card">
                <div class="value">{{ stats.total_found }}</div>
                <div class="label">Total Opportunities Found</div>
            </div>
            <div class="stat-card">
                <div class="value">{{ exchanges_online }}/{{ exchanges_total }}</div>
                <div class="label">Exchanges Online</div>
            </div>
        </div>
        
        <div class="opportunities">
            <h2>📊 Live Opportunities</h2>
            {% if opportunities %}
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Pair</th>
                        <th>Buy</th>
                        <th>Sell</th>
                        <th>Profit</th>
                        <th>ROI</th>
                        <th>Spread</th>
                        <th>Trade Size</th>
                        <th>Available</th>
                        <th>Confidence</th>
                    </tr>
                </thead>
                <tbody>
                    {% for opp in opportunities %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td><strong>{{ opp.pair }}</strong></td>
                        <td><span class="exchange-tag buy">{{ opp.buy_exchange }}</span></td>
                        <td><span class="exchange-tag sell">{{ opp.sell_exchange }}</span></td>
                        <td class="profit-positive">${{ "%.2f"|format(opp.profit_usd) }}</td>
                        <td class="profit-positive">{{ "%.2f"|format(opp.roi) }}%</td>
                        <td>{{ "%.2f"|format(opp.net_spread) }}%</td>
                        <td>${{ opp.trade_size }}</td>
                        <td>${{ "%.0f"|format(opp.max_volume) }}</td>
                        <td><span class="confidence">{{ "%.0f"|format(opp.confidence|default(85)) }}%</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div style="text-align: center; color: #888; padding: 40px;">
                🔍 No opportunities found. Scanning...
            </div>
            {% endif %}
        </div>
        
        <div style="margin-top: 15px; padding: 15px; background: #111; border-radius: 8px; border: 1px solid #333;">
            <div style="color: #888; font-size: 0.8em;">
                <strong>Exchange Status:</strong><br>
                {% for name, status in stats.exchanges_status.items() %}
                <span style="margin-right: 15px;">
                    <span class="status-dot {{ 'online' if status == 'online' else 'offline' }}"></span>
                    {{ name }}: {{ status }}
                </span>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(
        HTML_TEMPLATE,
        opportunities=engine.opportunities,
        stats=engine.stats,
        scan_interval=CONFIG['SCAN_INTERVAL'],
        exchanges_online=sum(1 for s in engine.stats['exchanges_status'].values() if s == 'online'),
        exchanges_total=len(engine.exchanges)
    )

@app.route('/api/opportunities')
def api_opportunities():
    return jsonify(engine.opportunities)

@app.route('/api/stats')
def api_stats():
    return jsonify(engine.stats)

# ============================================
# BACKGROUND SCANNER
# ============================================

async def background_scanner():
    """Runs in background scanning for opportunities"""
    print("🔄 Background scanner started...")
    while True:
        try:
            await engine.scan()
        except Exception as e:
            print(f"Scanner error: {e}")
        await asyncio.sleep(CONFIG['SCAN_INTERVAL'])

# ============================================
# RUN BOTH SCANNER AND WEB SERVER
# ============================================

def run_flask():
    """Run Flask in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

async def main():
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("\n" + "="*60)
    print("🚀 ARBITRAGE BOT WITH WEB DASHBOARD")
    print("="*60)
    print(f"📊 Exchanges: Binance, Bybit")
    print(f"🌐 Dashboard: http://localhost:5000")
    print(f"📡 API: http://localhost:5000/api/opportunities")
    print("="*60 + "\n")
    
    # Run the scanner
    await background_scanner()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Stopping...")

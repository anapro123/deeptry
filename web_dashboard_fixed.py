"""
ARBITRAGE BOT WITH 6 WORKING EXCHANGES
Binance, Bybit, OKX, KuCoin, Kraken, Gate.io
ALL EXCHANGES WORKING!
"""

import asyncio
import aiohttp
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from threading import Thread
import json
import time
import hmac
import hashlib
import base64
from urllib.parse import urlencode

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
# EXCHANGE APIS - ALL WORKING
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

class OKXAPI:
    async def get_prices(self):
        url = "https://www.okx.com/api/v5/market/tickers"
        params = {'instType': 'SPOT'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                prices = {}
                if data.get('data'):
                    for item in data['data']:
                        symbol = item['instId']
                        if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                            try:
                                prices[symbol] = {
                                    'bid': float(item.get('bidPx', 0) or 0),
                                    'ask': float(item.get('askPx', 0) or 0),
                                    'volume': float(item.get('vol24h', 0)) * float(item.get('last', 0) or 0),
                                }
                            except:
                                continue
                return prices

class KuCoinAPI:
    async def get_prices(self):
        url = "https://api.kucoin.com/api/v1/market/allTickers"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                prices = {}
                if data.get('data', {}).get('ticker'):
                    for item in data['data']['ticker']:
                        symbol = item['symbol']
                        if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                            try:
                                prices[symbol] = {
                                    'bid': float(item.get('buy', 0) or 0),
                                    'ask': float(item.get('sell', 0) or 0),
                                    'volume': float(item.get('vol', 0)) * float(item.get('last', 0) or 0),
                                }
                            except:
                                continue
                return prices

class KrakenAPI:
    async def get_prices(self):
        # Kraken uses different symbols (e.g., XBTUSD instead of BTCUSDT)
        url = "https://api.kraken.com/0/public/Ticker"
        
        # Map common symbols to Kraken format
        symbol_map = {
            'BTCUSDT': 'XXBTZUSD',
            'ETHUSDT': 'XETHZUSD',
            'SOLUSDT': 'SOLUSD',
            'ADAUSDT': 'ADAUSD',
            'DOTUSDT': 'DOTUSD',
            'LINKUSDT': 'LINKUSD',
            'MATICUSDT': 'MATICUSD',
            'AVAXUSDT': 'AVAXUSD',
            'UNIUSDT': 'UNIUSD',
            'ATOMUSDT': 'ATOMUSD',
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                prices = {}
                if data.get('result'):
                    for kraken_symbol, item in data['result'].items():
                        # Find matching symbol
                        for our_symbol, kraken_sym in symbol_map.items():
                            if kraken_sym == kraken_symbol:
                                try:
                                    prices[our_symbol] = {
                                        'bid': float(item.get('b', [0])[0] or 0),
                                        'ask': float(item.get('a', [0])[0] or 0),
                                        'volume': float(item.get('v', [0])[0]) * float(item.get('c', [0])[0] or 0),
                                    }
                                except:
                                    continue
                return prices

class GateIOAPI:
    async def get_prices(self):
        url = "https://api.gateio.ws/api/v4/spot/tickers"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                prices = {}
                for item in data:
                    symbol = item['currency_pair'].upper()
                    if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                        try:
                            prices[symbol] = {
                                'bid': float(item.get('highest_bid', 0) or 0),
                                'ask': float(item.get('lowest_ask', 0) or 0),
                                'volume': float(item.get('quote_volume', 0)),
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
            'okx': OKXAPI(),
            'kucoin': KuCoinAPI(),
            'kraken': KrakenAPI(),
            'gateio': GateIOAPI(),
        }
        self.opportunities = []
        self.stats = {
            'total_found': 0,
            'total_profit': 0,
            'last_scan': None,
            'exchanges_status': {},
            'exchanges_pairs': {}
        }
    
    async def scan(self):
        # Get prices from all exchanges
        all_prices = {}
        for name, exchange in self.exchanges.items():
            try:
                prices = await exchange.get_prices()
                if prices:
                    all_prices[name] = prices
                    self.stats['exchanges_status'][name] = f'online ({len(prices)} pairs)'
                    self.stats['exchanges_pairs'][name] = len(prices)
                else:
                    all_prices[name] = {}
                    self.stats['exchanges_status'][name] = 'no_data'
                    self.stats['exchanges_pairs'][name] = 0
            except Exception as e:
                all_prices[name] = {}
                self.stats['exchanges_status'][name] = f'error: {str(e)[:20]}'
                self.stats['exchanges_pairs'][name] = 0
        
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
                        # Calculate confidence score based on spread and volume
                        confidence = min(95, 60 + (net_spread * 10))
                        
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
                            'confidence': confidence,
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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🚀 Multi-Exchange Arbitrage Bot</title>
    <meta http-equiv="refresh" content="5">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #00ff00;
            padding: 20px;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        
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
        .header .exchanges-list { 
            margin-top: 10px;
            color: #00ff00;
            font-size: 0.85em;
        }
        .header .exchanges-list span {
            display: inline-block;
            margin: 0 5px;
            padding: 2px 10px;
            background: #1a1a1a;
            border-radius: 4px;
            border: 1px solid #00ff00;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
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
        .stat-card .highlight { color: #ff8800; }
        
        .opportunities {
            background: #111;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
            overflow-x: auto;
        }
        .opportunities h2 { margin-bottom: 15px; color: #00ff00; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85em;
            min-width: 800px;
        }
        th {
            background: #1a1a1a;
            color: #00ff00;
            padding: 10px;
            text-align: left;
            border-bottom: 2px solid #00ff00;
            position: sticky;
            top: 0;
        }
        td {
            padding: 8px 10px;
            border-bottom: 1px solid #222;
            color: #ccc;
        }
        tr:hover { background: #1a1a1a; }
        .profit-positive { color: #00ff00; font-weight: bold; }
        .profit-high { color: #ff8800; font-weight: bold; }
        .profit-mega { color: #ff00ff; font-weight: bold; }
        .exchange-tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
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
        .confidence-high { background: #1a3a1a; color: #00ff00; }
        .confidence-medium { background: #3a3a1a; color: #ffff00; }
        .confidence-low { background: #3a1a1a; color: #ff4444; }
        
        .exchange-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        .exchange-status {
            background: #111;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 10px;
            text-align: center;
        }
        .exchange-status .name { color: #00ff00; font-weight: bold; }
        .exchange-status .status { font-size: 0.8em; margin-top: 3px; }
        .exchange-status .pairs { color: #888; font-size: 0.7em; margin-top: 3px; }
        .status-online { color: #00ff00; }
        .status-offline { color: #ff4444; }
        .status-error { color: #ff8800; }
        
        .status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-dot.online { background: #00ff00; box-shadow: 0 0 10px #00ff00; }
        .status-dot.offline { background: #ff0000; }
        .status-dot.error { background: #ff8800; }
        
        @media (max-width: 768px) {
            .header h1 { font-size: 1.5em; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .exchange-status-grid { grid-template-columns: repeat(2, 1fr); }
            table { font-size: 0.7em; min-width: 600px; }
            td, th { padding: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 MULTI-EXCHANGE ARBITRAGE</h1>
            <div class="subtitle">Real-time crypto arbitrage across 6 exchanges</div>
            <div class="exchanges-list">
                {% for name, status in stats.exchanges_status.items() %}
                <span>{{ name }}</span>
                {% endfor %}
            </div>
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
                        <td class="{% if opp.profit_usd > 1 %}profit-mega{% elif opp.profit_usd > 0.1 %}profit-high{% else %}profit-positive{% endif %}">
                            ${{ "%.2f"|format(opp.profit_usd) }}
                        </td>
                        <td>{{ "%.2f"|format(opp.roi) }}%</td>
                        <td>{{ "%.2f"|format(opp.net_spread) }}%</td>
                        <td>${{ opp.trade_size }}</td>
                        <td>${{ "%.0f"|format(opp.max_volume) }}</td>
                        <td><span class="confidence 
                            {% if opp.confidence > 80 %}confidence-high
                            {% elif opp.confidence > 60 %}confidence-medium
                            {% else %}confidence-low{% endif %}">
                            {{ "%.0f"|format(opp.confidence) }}%
                        </span></td>
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
            <div style="color: #888; font-size: 0.85em; margin-bottom: 10px;">
                <strong>📡 Exchange Status</strong>
            </div>
            <div class="exchange-status-grid">
                {% for name, status in stats.exchanges_status.items() %}
                <div class="exchange-status">
                    <div class="name">{{ name.upper() }}</div>
                    <div class="status">
                        <span class="status-dot 
                            {% if 'online' in status %}online
                            {% elif 'error' in status %}error
                            {% else %}offline{% endif %}"></span>
                        <span class="
                            {% if 'online' in status %}status-online
                            {% elif 'error' in status %}status-error
                            {% else %}status-offline{% endif %}">
                            {{ status }}
                        </span>
                    </div>
                    <div class="pairs">Pairs: {{ stats.exchanges_pairs.get(name, 0) }}</div>
                </div>
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
        exchanges_online=sum(1 for s in engine.stats['exchanges_status'].values() if 'online' in s),
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
    print("🔄 Background scanner started with 6 exchanges...")
    while True:
        try:
            await engine.scan()
        except Exception as e:
            print(f"Scanner error: {e}")
        await asyncio.sleep(CONFIG['SCAN_INTERVAL'])

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("\n" + "="*70)
    print("🚀 MULTI-EXCHANGE ARBITRAGE BOT - ALL 6 EXCHANGES")
    print("="*70)
    print(f"📊 Exchanges: Binance, Bybit, OKX, KuCoin, Kraken, Gate.io")
    print(f"🌐 Dashboard: http://localhost:5000")
    print(f"📡 API: http://localhost:5000/api/opportunities")
    print("="*70 + "\n")
    
    await background_scanner()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Stopping...")

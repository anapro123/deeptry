"""
ARBITRAGE BOT - CLEAN VERSION
No user list display, working auto-refresh
"""

import asyncio
import aiohttp
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from threading import Thread
import json
import time
import os
import threading
import requests

# ============================================
# CONFIGURATION
# ============================================

CONFIG_FILE = 'bot_config.json'

DEFAULT_CONFIG = {
    'MIN_PROFIT_PERCENT': 0.05,
    'MIN_PROFIT_USD': 0.01,
    'TRADING_FEE': 0.001,
    'BASE_CURRENCIES': ['USDT', 'BTC', 'ETH'],
    'SCAN_INTERVAL': 5,
    'MAX_OPPORTUNITIES_DISPLAY': 50,
    
    'ALERTS': {
        'enabled': True,
        'min_profit_to_alert': 0.10,
        'min_confidence_to_alert': 60,
        'cooldown_seconds': 60,
    },
    
    'TELEGRAM': {
        'enabled': True,
        'bot_token': '6667612277:AAFcTaNO4sjp_1LSgcUMy4UncCS9oMNOncU',
        'users': [],
    },
    
    'DISCORD': {
        'enabled': False,
        'webhooks': [],
    },
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

CONFIG = load_config()

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
        url = "https://api.kraken.com/0/public/Ticker"
        symbol_map = {
            'BTCUSDT': 'XXBTZUSD',
            'ETHUSDT': 'XETHZUSD',
            'SOLUSDT': 'SOLUSD',
            'ADAUSDT': 'ADAUSD',
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                prices = {}
                if data.get('result'):
                    for kraken_symbol, item in data['result'].items():
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
# ALERT SYSTEM
# ============================================

class AlertSystem:
    def __init__(self):
        self.sent_alerts = {}
    
    async def send_telegram(self, message, chat_id=None):
        if not CONFIG['TELEGRAM']['enabled']:
            return
        
        bot_token = CONFIG['TELEGRAM']['bot_token']
        if not bot_token:
            return
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        if chat_id:
            users = [{'chat_id': chat_id}]
        else:
            users = CONFIG['TELEGRAM']['users']
        
        for user in users:
            if user.get('chat_id'):
                data = {
                    'chat_id': user['chat_id'],
                    'text': message,
                    'parse_mode': 'HTML',
                }
                async with aiohttp.ClientSession() as session:
                    try:
                        await session.post(url, json=data)
                        print(f"✅ Telegram sent to {user.get('name', 'user')}")
                    except Exception as e:
                        print(f"❌ Telegram error: {e}")
    
    async def send_alert(self, opportunity):
        if not CONFIG['ALERTS']['enabled']:
            return
        
        if opportunity['profit_usd'] < CONFIG['ALERTS']['min_profit_to_alert']:
            return
        
        if opportunity['confidence'] < CONFIG['ALERTS']['min_confidence_to_alert']:
            return
        
        key = f"{opportunity['pair']}_{opportunity['buy_exchange']}_{opportunity['sell_exchange']}"
        now = time.time()
        cooldown = CONFIG['ALERTS']['cooldown_seconds']
        if key in self.sent_alerts and now - self.sent_alerts[key] < cooldown:
            return
        self.sent_alerts[key] = now
        
        message = self.format_message(opportunity)
        await self.send_telegram(message)
    
    def format_message(self, opp):
        scaled_profit = opp['profit_usd'] * (opp['max_volume'] / opp['trade_size']) if opp['trade_size'] > 0 else 0
        
        return f"""
🚀 <b>ARBITRAGE OPPORTUNITY!</b>

📊 Pair: {opp['pair']}
🔄 Trade: {opp['buy_exchange']} → {opp['sell_exchange']}

💵 Profit: ${opp['profit_usd']:.2f} ({opp['roi']:.2f}%)
📈 Spread: {opp['net_spread']:.2f}%
💰 Trade Size: ${opp['trade_size']}
📊 Available: ${opp['max_volume']:.0f}
⭐ Confidence: {opp['confidence']:.0f}%

📈 Scaled Profit: ${scaled_profit:.2f}
🕐 Time: {opp['timestamp']}
"""

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
        self.alert_system = AlertSystem()
        self.previous_opportunities = []
    
    async def scan(self):
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
                        confidence = min(95, 60 + (net_spread * 10))
                        
                        opp = {
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
                        }
                        opportunities.append(opp)
                        break
        
        opportunities.sort(key=lambda x: x['profit_usd'], reverse=True)
        self.opportunities = opportunities[:CONFIG['MAX_OPPORTUNITIES_DISPLAY']]
        
        # Send alerts for new opportunities
        for opp in self.opportunities[:3]:
            is_new = True
            for prev in self.previous_opportunities[:3]:
                if (prev['pair'] == opp['pair'] and 
                    prev['buy_exchange'] == opp['buy_exchange'] and 
                    prev['sell_exchange'] == opp['sell_exchange']):
                    is_new = False
                    break
            
            if is_new:
                await self.alert_system.send_alert(opp)
        
        self.previous_opportunities = self.opportunities.copy()
        
        if opportunities:
            self.stats['total_found'] += len(opportunities)
            self.stats['total_profit'] += sum(o['profit_usd'] for o in opportunities)
        self.stats['last_scan'] = datetime.now().strftime('%H:%M:%S')
        
        return opportunities

# ============================================
# FLASK WEB APP - CLEAN VERSION
# ============================================

app = Flask(__name__)
engine = ArbitrageEngine()

# HTML Template - No user list, working auto-refresh
MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🚀 Arbitrage Bot</title>
    <meta http-equiv="refresh" content="10">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0a0a0a; color: #00ff00; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        
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
        .header .refresh-info { color: #444; font-size: 0.8em; margin-top: 5px; }
        
        .section {
            background: #111;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .section h2 { color: #00ff00; margin-bottom: 15px; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        .stat-item {
            background: #1a1a1a;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
            border: 1px solid #333;
        }
        .stat-item .value { font-size: 1.8em; color: #00ff00; font-weight: bold; }
        .stat-item .label { color: #888; font-size: 0.8em; }
        
        .opportunities-table {
            overflow-x: auto;
            margin-top: 10px;
        }
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
            position: sticky;
            top: 0;
            z-index: 10;
        }
        td {
            padding: 10px 12px;
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
        
        .exchange-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .exchange-status {
            background: #1a1a1a;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            border: 1px solid #333;
        }
        .exchange-status .name { color: #00ff00; font-weight: bold; }
        .exchange-status .status { font-size: 0.8em; margin-top: 3px; }
        .exchange-status .pairs { color: #888; font-size: 0.7em; margin-top: 3px; }
        .status-online { color: #00ff00; }
        .status-offline { color: #ff4444; }
        .status-error { color: #ff8800; }
        
        .register-box {
            max-width: 500px;
            margin: 0 auto;
            text-align: center;
        }
        .register-box input {
            width: 100%;
            padding: 12px;
            margin: 8px 0;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 5px;
            color: #00ff00;
            font-size: 1em;
        }
        .register-box input:focus {
            border-color: #00ff00;
            outline: none;
        }
        .register-box .btn {
            width: 100%;
            padding: 12px;
            background: #00ff00;
            color: #0a0a0a;
            border: none;
            border-radius: 5px;
            font-weight: bold;
            font-size: 1.1em;
            cursor: pointer;
        }
        .register-box .btn:hover { opacity: 0.8; }
        
        .how-to {
            background: #1a1a1a;
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
            text-align: left;
        }
        .how-to h3 { color: #00ff00; margin-bottom: 10px; }
        .how-to ol { color: #888; padding-left: 20px; }
        .how-to li { margin: 8px 0; }
        .how-to code {
            background: #0a0a0a;
            padding: 2px 8px;
            border-radius: 3px;
            color: #00ff00;
        }
        
        .alert-msg {
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .alert-success { background: #1a3a1a; border: 1px solid #00ff00; color: #00ff00; }
        .alert-error { background: #3a1a1a; border: 1px solid #ff4444; color: #ff4444; }
        
        @media (max-width: 768px) {
            .header h1 { font-size: 1.5em; }
            table { font-size: 0.7em; }
            td, th { padding: 5px; }
        }
    </style>
    <script>
        // Manual refresh with JavaScript (fallback)
        setTimeout(function() {
            location.reload();
        }, 10000);
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 ARBITRAGE BOT</h1>
            <div class="subtitle">Real-time arbitrage opportunities across 6 exchanges</div>
            <div class="refresh-info">Auto-refreshes every 10 seconds</div>
        </div>
        
        {% if message %}
        <div class="alert-msg alert-{{ message_type }}">{{ message }}</div>
        {% endif %}
        
        <div class="section">
            <h2>📱 Register for Telegram Alerts</h2>
            <div class="register-box">
                <form method="POST" action="/register">
                    <input type="text" name="name" placeholder="Your Name" required>
                    <input type="text" name="chat_id" placeholder="Your Telegram Chat ID" required>
                    <button type="submit" class="btn">🔔 Get Alerts</button>
                </form>
                <div class="how-to">
                    <h3>📖 How to get Chat ID:</h3>
                    <ol>
                        <li>Search <code>@userinfobot</code> on Telegram</li>
                        <li>Send <code>/start</code></li>
                        <li>Copy the <strong>Chat ID</strong> number</li>
                    </ol>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Statistics</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="value">{{ stats.total_found }}</div>
                    <div class="label">Total Opportunities</div>
                </div>
                <div class="stat-item">
                    <div class="value">${{ "%.2f"|format(stats.total_profit) }}</div>
                    <div class="label">Total Profit</div>
                </div>
                <div class="stat-item">
                    <div class="value">{{ opportunities|length }}</div>
                    <div class="label">Current Opportunities</div>
                </div>
                <div class="stat-item">
                    <div class="value">{{ stats.last_scan or 'N/A' }}</div>
                    <div class="label">Last Scan</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Live Opportunities ({{ opportunities|length }} found)</h2>
            {% if opportunities %}
            <div class="opportunities-table">
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
                            <td>{{ "%.0f"|format(opp.confidence) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <p style="color: #888; text-align: center; padding: 20px;">🔍 No opportunities found. Scanning...</p>
            {% endif %}
        </div>
        
        <div class="section">
            <h2>📡 Exchange Status</h2>
            <div class="exchange-status-grid">
                {% for name, status in stats.exchanges_status.items() %}
                <div class="exchange-status">
                    <div class="name">{{ name.upper() }}</div>
                    <div class="status">
                        <span class="{% if 'online' in status %}status-online{% elif 'error' in status %}status-error{% else %}status-offline{% endif %}">
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

def send_telegram_sync(message, chat_id):
    bot_token = CONFIG['TELEGRAM']['bot_token']
    if not bot_token:
        return
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print(f"✅ Welcome message sent")
        else:
            print(f"❌ Failed: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def index():
    return render_template_string(
        MAIN_TEMPLATE,
        opportunities=engine.opportunities,
        stats=engine.stats,
        config=CONFIG,
        message=None,
        message_type=None
    )

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    chat_id = request.form.get('chat_id')
    
    if not name or not chat_id:
        return render_template_string(
            MAIN_TEMPLATE,
            opportunities=engine.opportunities,
            stats=engine.stats,
            config=CONFIG,
            message="❌ Please fill in both fields",
            message_type="error"
        )
    
    # Check if user exists
    for user in CONFIG['TELEGRAM']['users']:
        if user['chat_id'] == chat_id:
            return render_template_string(
                MAIN_TEMPLATE,
                opportunities=engine.opportunities,
                stats=engine.stats,
                config=CONFIG,
                message=f"✅ {name}, you're already registered!",
                message_type="success"
            )
    
    # Add new user
    CONFIG['TELEGRAM']['users'].append({'name': name, 'chat_id': chat_id})
    save_config(CONFIG)
    
    # Send welcome message
    welcome_msg = f"""
🎉 <b>Welcome {name}!</b>

You're now registered for arbitrage alerts!

📊 You'll receive notifications when profitable opportunities are found.

🔔 Settings:
• Min Profit: ${CONFIG['ALERTS']['min_profit_to_alert']}
• Confidence: {CONFIG['ALERTS']['min_confidence_to_alert']}%
• Cooldown: {CONFIG['ALERTS']['cooldown_seconds']}s

Stay tuned for opportunities! 🚀
    """
    
    thread = threading.Thread(target=send_telegram_sync, args=(welcome_msg, chat_id))
    thread.daemon = True
    thread.start()
    
    return render_template_string(
        MAIN_TEMPLATE,
        opportunities=engine.opportunities,
        stats=engine.stats,
        config=CONFIG,
        message=f"✅ Welcome {name}! You'll receive alerts on Telegram.",
        message_type="success"
    )

@app.route('/api/opportunities')
def api_opportunities():
    return jsonify(engine.opportunities)

@app.route('/api/stats')
def api_stats():
    return jsonify(engine.stats)

# ============================================
# MAIN
# ============================================

async def background_scanner():
    print("🔄 Scanner started...")
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
    print("🚀 ARBITRAGE BOT - CLEAN VERSION")
    print("="*70)
    print("📊 Exchanges: Binance, Bybit, OKX, KuCoin, Kraken, Gate.io")
    print("📈 Shows ALL opportunities")
    print("🔄 Auto-refreshes every 10 seconds")
    print("🌐 Web: http://localhost:5000")
    print("="*70 + "\n")
    
    await background_scanner()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Stopping...")

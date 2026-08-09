"""
ARBITRAGE BOT - DEBUG VERSION
Shows all data and why opportunities might be filtered
"""

import asyncio
import aiohttp
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, Response, stream_with_context
from threading import Thread
import json
import time
import os
import threading
import requests

# ============================================
# CONFIGURATION - VERY SENSITIVE
# ============================================

CONFIG_FILE = 'bot_config.json'
USERS_FILE = 'users.txt'

DEFAULT_CONFIG = {
    'MIN_PROFIT_PERCENT': 0.001,      # Extremely low - catch everything
    'MIN_PROFIT_USD': 0.0001,          # Almost zero
    'MAX_PROFIT_PERCENT': 5000,        # Allow huge spreads (for debugging)
    'TRADING_FEE': 0.001,
    'BASE_CURRENCIES': ['USDT', 'BTC', 'ETH'],
    'SCAN_INTERVAL': 5,
    'MAX_OPPORTUNITIES_DISPLAY': 100,
    
    'ALERTS': {
        'enabled': True,
        'min_profit_to_alert': 0.0001,
        'min_confidence_to_alert': 0,
        'cooldown_seconds': 2,
        'alert_on_every_scan': True,
        'max_alerts_per_scan': 30,
    },
    
    'TELEGRAM': {
        'enabled': True,
        'bot_token': '6667612277:AAFcTaNO4sjp_1LSgcUMy4UncCS9oMNOncU',
    },
    
    'DISCORD': {
        'enabled': False,
        'webhooks': [],
    },
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            if 'MAX_OPPORTUNITIES_DISPLAY' not in config:
                config['MAX_OPPORTUNITIES_DISPLAY'] = 100
            if 'MAX_PROFIT_PERCENT' not in config:
                config['MAX_PROFIT_PERCENT'] = 5000
            if 'max_alerts_per_scan' not in config.get('ALERTS', {}):
                config['ALERTS']['max_alerts_per_scan'] = 30
            return config
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

CONFIG = load_config()

# ============================================
# USER MANAGEMENT
# ============================================

def load_users():
    users = []
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        name, chat_id = line.split('|')
                        users.append({'name': name, 'chat_id': chat_id})
                    except:
                        continue
    return users

def save_user(name, chat_id):
    with open(USERS_FILE, 'a') as f:
        f.write(f"{name}|{chat_id}\n")

def user_exists(chat_id):
    users = load_users()
    for user in users:
        if user['chat_id'] == chat_id:
            return True
    return False

CONFIG['TELEGRAM']['users'] = load_users()

# ============================================
# EXCHANGE APIS
# ============================================

class BinanceAPI:
    async def get_prices(self):
        url = "https://api.binance.com/api/v3/ticker/24hr"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return {}
                    data = await response.json()
                    prices = {}
                    for item in data:
                        symbol = item['symbol']
                        if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                            try:
                                bid = float(item.get('bidPrice', 0) or 0)
                                ask = float(item.get('askPrice', 0) or 0)
                                if bid > 0 and ask > 0:
                                    prices[symbol] = {
                                        'bid': bid,
                                        'ask': ask,
                                        'volume': float(item.get('volume', 0)) * float(item.get('lastPrice', 0) or 0),
                                    }
                            except:
                                continue
                    return prices
        except Exception as e:
            print(f"Binance error: {e}")
            return {}

class BybitAPI:
    async def get_prices(self):
        url = "https://api.bybit.com/v5/market/tickers"
        params = {'category': 'spot'}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        return {}
                    data = await response.json()
                    prices = {}
                    if data.get('result', {}).get('list'):
                        for item in data['result']['list']:
                            symbol = item['symbol']
                            if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                                try:
                                    bid = float(item.get('bid1Price', 0) or 0)
                                    ask = float(item.get('ask1Price', 0) or 0)
                                    if bid > 0 and ask > 0:
                                        prices[symbol] = {
                                            'bid': bid,
                                            'ask': ask,
                                            'volume': float(item.get('volume24h', 0)) * float(item.get('lastPrice', 0) or 0),
                                        }
                                except:
                                    continue
                    return prices
        except Exception as e:
            print(f"Bybit error: {e}")
            return {}

class OKXAPI:
    async def get_prices(self):
        url = "https://www.okx.com/api/v5/market/tickers"
        params = {'instType': 'SPOT'}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        return {}
                    data = await response.json()
                    prices = {}
                    if data.get('data'):
                        for item in data['data']:
                            symbol = item['instId']
                            if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                                try:
                                    bid = float(item.get('bidPx', 0) or 0)
                                    ask = float(item.get('askPx', 0) or 0)
                                    if bid > 0 and ask > 0:
                                        prices[symbol] = {
                                            'bid': bid,
                                            'ask': ask,
                                            'volume': float(item.get('vol24h', 0)) * float(item.get('last', 0) or 0),
                                        }
                                except:
                                    continue
                    return prices
        except Exception as e:
            print(f"OKX error: {e}")
            return {}

class KuCoinAPI:
    async def get_prices(self):
        url = "https://api.kucoin.com/api/v1/market/allTickers"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return {}
                    data = await response.json()
                    prices = {}
                    if data.get('data', {}).get('ticker'):
                        for item in data['data']['ticker']:
                            symbol = item['symbol']
                            if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                                try:
                                    bid = float(item.get('buy', 0) or 0)
                                    ask = float(item.get('sell', 0) or 0)
                                    if bid > 0 and ask > 0:
                                        prices[symbol] = {
                                            'bid': bid,
                                            'ask': ask,
                                            'volume': float(item.get('vol', 0)) * float(item.get('last', 0) or 0),
                                        }
                                except:
                                    continue
                    return prices
        except Exception as e:
            print(f"KuCoin error: {e}")
            return {}

class KrakenAPI:
    async def get_prices(self):
        url = "https://api.kraken.com/0/public/Ticker"
        symbol_map = {
            'BTCUSDT': 'XXBTZUSD',
            'ETHUSDT': 'XETHZUSD',
            'SOLUSDT': 'SOLUSD',
            'ADAUSDT': 'ADAUSD',
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return {}
                    data = await response.json()
                    prices = {}
                    if data.get('result'):
                        for kraken_symbol, item in data['result'].items():
                            for our_symbol, kraken_sym in symbol_map.items():
                                if kraken_sym == kraken_symbol:
                                    try:
                                        bid = float(item.get('b', [0])[0] or 0)
                                        ask = float(item.get('a', [0])[0] or 0)
                                        if bid > 0 and ask > 0:
                                            prices[our_symbol] = {
                                                'bid': bid,
                                                'ask': ask,
                                                'volume': float(item.get('v', [0])[0]) * float(item.get('c', [0])[0] or 0),
                                            }
                                    except:
                                        continue
                    return prices
        except Exception as e:
            print(f"Kraken error: {e}")
            return {}

class GateIOAPI:
    async def get_prices(self):
        url = "https://api.gateio.ws/api/v4/spot/tickers"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return {}
                    data = await response.json()
                    prices = {}
                    for item in data:
                        symbol = item['currency_pair'].upper()
                        if any(symbol.endswith(base) for base in CONFIG['BASE_CURRENCIES']):
                            try:
                                bid = float(item.get('highest_bid', 0) or 0)
                                ask = float(item.get('lowest_ask', 0) or 0)
                                if bid > 0 and ask > 0:
                                    prices[symbol] = {
                                        'bid': bid,
                                        'ask': ask,
                                        'volume': float(item.get('quote_volume', 0)),
                                    }
                            except:
                                continue
                    return prices
        except Exception as e:
            print(f"GateIO error: {e}")
            return {}

# ============================================
# ALERT SYSTEM
# ============================================

class AlertSystem:
    def __init__(self):
        self.sent_alerts = {}
        self.alert_count = 0
    
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
            users = load_users()
        
        for user in users:
            if user.get('chat_id'):
                data = {
                    'chat_id': user['chat_id'],
                    'text': message,
                    'parse_mode': 'HTML',
                }
                try:
                    async with aiohttp.ClientSession() as session:
                        await session.post(url, json=data)
                        self.alert_count += 1
                        print(f"✅ Alert #{self.alert_count} sent to {user.get('name', 'user')}")
                except Exception as e:
                    print(f"❌ Telegram error: {e}")
    
    async def send_alert(self, opportunity):
        if not CONFIG['ALERTS']['enabled']:
            return
        
        if opportunity['roi'] > CONFIG['MAX_PROFIT_PERCENT']:
            return
        
        if opportunity['profit_usd'] <= 0:
            return
        
        key = f"{opportunity['pair']}_{opportunity['buy_exchange']}_{opportunity['sell_exchange']}"
        now = time.time()
        cooldown = CONFIG['ALERTS']['cooldown_seconds']
        
        if key in self.sent_alerts and now - self.sent_alerts[key] < cooldown:
            return
        self.sent_alerts[key] = now
        
        message = self.format_message(opportunity)
        await self.send_telegram(message)
        print(f"📤 Alert sent: {opportunity['pair']} - ${opportunity['profit_usd']:.4f}")
    
    def format_message(self, opp):
        scaled_profit = opp['profit_usd'] * (opp['max_volume'] / opp['trade_size']) if opp['trade_size'] > 0 else 0
        
        return f"""
🚀 <b>ARBITRAGE OPPORTUNITY!</b>

📊 Pair: {opp['pair']}
🔄 Trade: {opp['buy_exchange']} → {opp['sell_exchange']}

💵 Profit: ${opp['profit_usd']:.4f} ({opp['roi']:.2f}%)
📈 Spread: {opp['net_spread']:.3f}%
💰 Trade Size: ${opp['trade_size']}
📊 Available: ${opp['max_volume']:.0f}
⭐ Confidence: {opp['confidence']:.0f}%

📈 Scaled Profit: ${scaled_profit:.2f}
🕐 Time: {opp['timestamp']}
"""

# ============================================
# ARBITRAGE ENGINE - DEBUG VERSION
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
        self.all_raw_opportunities = []  # Store all found for debugging
        self.stats = {
            'total_found': 0,
            'total_profit': 0,
            'last_scan': None,
            'exchanges_status': {},
            'exchanges_pairs': {},
            'raw_pairs_scanned': 0,
            'opportunities_found_raw': 0,
        }
        self.alert_system = AlertSystem()
        self.scan_count = 0
        self.current_time = datetime.now().strftime('%H:%M:%S')
    
    async def scan(self):
        self.scan_count += 1
        self.current_time = datetime.now().strftime('%H:%M:%S')
        self.all_raw_opportunities = []
        
        print(f"\n🔍 SCAN #{self.scan_count} - {self.current_time}")
        print("="*50)
        
        all_prices = {}
        
        # Fetch prices
        for name, exchange in self.exchanges.items():
            try:
                prices = await exchange.get_prices()
                if prices:
                    all_prices[name] = prices
                    self.stats['exchanges_status'][name] = f'online ({len(prices)} pairs)'
                    self.stats['exchanges_pairs'][name] = len(prices)
                    print(f"  ✅ {name}: {len(prices)} pairs")
                else:
                    all_prices[name] = {}
                    self.stats['exchanges_status'][name] = 'no_data'
                    self.stats['exchanges_pairs'][name] = 0
                    print(f"  ⚠️ {name}: No data")
            except Exception as e:
                all_prices[name] = {}
                self.stats['exchanges_status'][name] = 'error'
                self.stats['exchanges_pairs'][name] = 0
                print(f"  ❌ {name}: Error - {e}")
        
        # Find opportunities
        opportunities = []
        pairs = {}
        
        for exchange_name, prices in all_prices.items():
            for pair, data in prices.items():
                if pair not in pairs:
                    pairs[pair] = {}
                pairs[pair][exchange_name] = data
        
        print(f"\n📊 Checking {len(pairs)} unique pairs for arbitrage...")
        
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
            
            # Log every pair with a spread
            if abs(raw_spread) > 0.001:  # Only log meaningful spreads
                print(f"  {pair}: raw={raw_spread:.3f}%, net={net_spread:.3f}% | {buy_exchange[0]}→{sell_exchange[0]}")
            
            if net_spread > CONFIG['MIN_PROFIT_PERCENT']:
                max_volume = min(
                    buy_exchange[1].get('volume', 0),
                    sell_exchange[1].get('volume', 0)
                )
                
                trade_sizes = [5, 10, 25, 50, 100, 250, 500]
                for trade_size in trade_sizes:
                    if trade_size > max_volume:
                        continue
                        
                    investment = buy_price * (trade_size / sell_price)
                    gross_profit = (sell_price - buy_price) * (trade_size / sell_price)
                    net_profit = gross_profit - (investment * CONFIG['TRADING_FEE'] * 2)
                    
                    if net_profit > CONFIG['MIN_PROFIT_USD']:
                        confidence = min(95, 50 + (net_spread * 20))
                        
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
                            'roi': (net_profit / investment) * 100 if investment > 0 else 0,
                            'investment': investment,
                            'max_volume': max_volume,
                            'confidence': min(95, confidence),
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        }
                        opportunities.append(opp)
                        self.all_raw_opportunities.append(opp)
                        print(f"  ✅ FOUND: {pair} - ${net_profit:.4f} profit ({net_spread:.3f}%)")
                        break
        
        # Sort and filter
        opportunities.sort(key=lambda x: x['profit_usd'], reverse=True)
        
        # Store all opportunities for display
        self.opportunities = opportunities[:CONFIG.get('MAX_OPPORTUNITIES_DISPLAY', 100)]
        
        # Update stats
        raw_opp_count = len(self.all_raw_opportunities)
        self.stats['opportunities_found_raw'] = raw_opp_count
        self.stats['pairs_scanned'] = len(pairs)
        
        print(f"\n📊 SUMMARY: Found {len(self.opportunities)} opportunities (raw: {raw_opp_count})")
        
        # Send alerts
        max_alerts = CONFIG['ALERTS'].get('max_alerts_per_scan', 30)
        alerts_sent = 0
        
        for opp in self.opportunities[:max_alerts]:
            await self.alert_system.send_alert(opp)
            alerts_sent += 1
            if alerts_sent < len(self.opportunities[:max_alerts]):
                await asyncio.sleep(0.2)
        
        if alerts_sent > 0:
            print(f"📤 Sent {alerts_sent} alerts")
        
        if self.opportunities:
            self.stats['total_found'] += len(self.opportunities)
            self.stats['total_profit'] += sum(o['profit_usd'] for o in self.opportunities)
        self.stats['last_scan'] = datetime.now().strftime('%H:%M:%S')
        
        return self.opportunities

# ============================================
# FLASK WEB APP
# ============================================

app = Flask(__name__)
engine = ArbitrageEngine()

latest_data = {
    'opportunities': [],
    'all_raw': [],
    'stats': {},
    'timestamp': '',
    'debug': {}
}

def update_latest_data():
    global latest_data
    latest_data['opportunities'] = engine.opportunities[:30]
    latest_data['all_raw'] = engine.all_raw_opportunities[:30]
    latest_data['stats'] = engine.stats
    latest_data['timestamp'] = datetime.now().strftime('%H:%M:%S')
    latest_data['debug'] = {
        'scan_count': engine.scan_count,
        'pairs_scanned': engine.stats.get('pairs_scanned', 0),
        'raw_opportunities': engine.stats.get('opportunities_found_raw', 0),
        'min_profit_percent': CONFIG['MIN_PROFIT_PERCENT'],
        'min_profit_usd': CONFIG['MIN_PROFIT_USD'],
    }

@app.route('/stream')
def stream():
    def generate():
        while True:
            update_latest_data()
            yield f"data: {json.dumps(latest_data)}\n\n"
            time.sleep(5)
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🚀 Arbitrage Bot - Debug</title>
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
        .header .debug-info { color: #ff8800; font-size: 0.8em; margin-top: 8px; }
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
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
        }
        .stat-item {
            background: #1a1a1a;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            border: 1px solid #333;
        }
        .stat-item .value { font-size: 1.5em; color: #00ff00; font-weight: bold; }
        .stat-item .label { color: #888; font-size: 0.7em; }
        .opportunities-table { overflow-x: auto; margin-top: 10px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.8em; }
        th { background: #1a1a1a; color: #00ff00; padding: 8px; text-align: left; border-bottom: 2px solid #00ff00; }
        td { padding: 6px 8px; border-bottom: 1px solid #222; color: #ccc; }
        tr:hover { background: #1a1a1a; }
        .profit-positive { color: #00ff00; }
        .profit-high { color: #ff8800; font-weight: bold; }
        .profit-mega { color: #ff00ff; font-weight: bold; }
        .exchange-tag { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight: bold; }
        .buy { background: #1a3a1a; color: #00ff00; }
        .sell { background: #3a1a1a; color: #ff4444; }
        .debug-box {
            background: #1a1a1a;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 0.8em;
            color: #888;
            margin-top: 10px;
            white-space: pre-wrap;
        }
        .register-box { max-width: 500px; margin: 0 auto; text-align: center; }
        .register-box input {
            width: 100%; padding: 10px; margin: 5px 0;
            background: #1a1a1a; border: 1px solid #333;
            border-radius: 5px; color: #00ff00; font-size: 1em;
        }
        .register-box .btn {
            width: 100%; padding: 10px;
            background: #00ff00; color: #0a0a0a;
            border: none; border-radius: 5px;
            font-weight: bold; cursor: pointer;
        }
        .register-box .btn:hover { opacity: 0.8; }
        .how-to {
            background: #1a1a1a;
            padding: 15px;
            border-radius: 10px;
            margin-top: 15px;
            text-align: left;
            border: 1px solid #333;
        }
        .how-to h3 { color: #00ff00; margin-bottom: 10px; }
        .how-to .step {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px;
            margin-bottom: 5px;
            background: #0a0a0a;
            border-radius: 6px;
            border-left: 3px solid #00ff00;
        }
        .how-to .step-number {
            background: #00ff00;
            color: #0a0a0a;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.7em;
            flex-shrink: 0;
        }
        .how-to .step-content p { color: #aaa; font-size: 0.85em; }
        .how-to .step-content code {
            background: #0a0a0a;
            color: #00ff00;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }
        .how-to .telegram-btn {
            display: inline-block;
            background: #0088cc;
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.8em;
            margin-top: 2px;
        }
        .filter-badge {
            display: inline-block;
            background: #1a3a1a;
            padding: 2px 10px;
            border-radius: 10px;
            color: #00ff00;
            font-size: 0.7em;
            margin: 2px;
        }
        @media (max-width: 768px) {
            .header h1 { font-size: 1.5em; }
            table { font-size: 0.6em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 ARBITRAGE BOT - DEBUG</h1>
            <div class="subtitle">Shows ALL data - Why are we not finding opportunities?</div>
            <div class="debug-info">
                Min Spread: {{ config.MIN_PROFIT_PERCENT }}% | 
                Min Profit: ${{ config.MIN_PROFIT_USD }} | 
                Fee: {{ config.TRADING_FEE*100 }}%
            </div>
        </div>
        
        <div class="section">
            <h2>📱 Register</h2>
            <div class="register-box">
                <form method="POST" action="/register">
                    <input type="text" name="name" placeholder="Your Name">
                    <input type="text" name="chat_id" placeholder="Your Telegram Chat ID">
                    <button type="submit" class="btn">🔔 Get Alerts</button>
                </form>
                <div class="how-to">
                    <h3>📖 How to get Chat ID:</h3>
                    <div class="step">
                        <div class="step-number">1</div>
                        <div class="step-content">
                            <p>Search <code>@id-bot</code> on Telegram</p>
                            <a href="https://t.me/id-bot" target="_blank" class="telegram-btn">Open</a>
                        </div>
                    </div>
                    <div class="step">
                        <div class="step-number">2</div>
                        <div class="step-content"><p>Send <code>/start</code></p></div>
                    </div>
                    <div class="step">
                        <div class="step-number">3</div>
                        <div class="step-content"><p>Copy your <strong>Chat ID</strong></p></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Debug Info</h2>
            <div class="debug-box" id="debugBox">Loading debug data...</div>
        </div>
        
        <div class="section">
            <h2>📊 Statistics</h2>
            <div class="stats-grid" id="statsGrid">
                <div class="stat-item">
                    <div class="value" id="totalFound">0</div>
                    <div class="label">Total Found</div>
                </div>
                <div class="stat-item">
                    <div class="value" id="totalProfit">$0.00</div>
                    <div class="label">Total Profit</div>
                </div>
                <div class="stat-item">
                    <div class="value" id="currentCount">0</div>
                    <div class="label">Current Opportunities</div>
                </div>
                <div class="stat-item">
                    <div class="value" id="rawCount">0</div>
                    <div class="label">Raw Opportunities</div>
                </div>
                <div class="stat-item">
                    <div class="value" id="pairsScanned">0</div>
                    <div class="label">Pairs Scanned</div>
                </div>
                <div class="stat-item">
                    <div class="value" id="lastScan">N/A</div>
                    <div class="label">Last Scan</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Live Opportunities (<span id="oppCount">0</span>)</h2>
            <div id="opportunitiesContainer">
                <p style="color: #888; text-align: center; padding: 20px;">🔍 Waiting for data...</p>
            </div>
        </div>
        
        <div class="section">
            <h2>📡 Exchange Status</h2>
            <div id="exchangeStatus" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px;">
                <div style="color: #666; text-align: center; padding: 20px;">Loading...</div>
            </div>
        </div>
    </div>
    
    <script>
        const eventSource = new EventSource('/stream');
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            updateUI(data);
        };
        
        eventSource.onerror = function(event) {
            console.log('Reconnecting...');
        };
        
        function updateUI(data) {
            // Debug info
            const debugBox = document.getElementById('debugBox');
            if (data.debug) {
                debugBox.textContent = JSON.stringify(data.debug, null, 2);
            }
            
            // Stats
            if (data.stats) {
                document.getElementById('totalFound').textContent = data.stats.total_found || 0;
                document.getElementById('totalProfit').textContent = '$' + (data.stats.total_profit || 0).toFixed(2);
                document.getElementById('currentCount').textContent = data.opportunities ? data.opportunities.length : 0;
                document.getElementById('rawCount').textContent = data.stats.opportunities_found_raw || 0;
                document.getElementById('pairsScanned').textContent = data.stats.pairs_scanned || 0;
                document.getElementById('lastScan').textContent = data.stats.last_scan || 'N/A';
                document.getElementById('oppCount').textContent = data.opportunities ? data.opportunities.length : 0;
            }
            
            // Opportunities
            const container = document.getElementById('opportunitiesContainer');
            if (data.opportunities && data.opportunities.length > 0) {
                let html = '<div class="opportunities-table"><table><thead><tr>';
                html += '<th>#</th><th>Pair</th><th>Buy</th><th>Sell</th>';
                html += '<th>Profit</th><th>ROI</th><th>Spread</th>';
                html += '<th>Trade</th><th>Available</th><th>Confidence</th>';
                html += '</tr></thead><tbody>';
                
                data.opportunities.forEach((opp, index) => {
                    let profitClass = 'profit-positive';
                    if (opp.profit_usd > 1) profitClass = 'profit-mega';
                    else if (opp.profit_usd > 0.1) profitClass = 'profit-high';
                    
                    html += `<tr>
                        <td>${index + 1}</td>
                        <td><strong>${opp.pair}</strong></td>
                        <td><span class="exchange-tag buy">${opp.buy_exchange}</span></td>
                        <td><span class="exchange-tag sell">${opp.sell_exchange}</span></td>
                        <td class="${profitClass}">$${opp.profit_usd.toFixed(4)}</td>
                        <td>${opp.roi.toFixed(2)}%</td>
                        <td>${opp.net_spread.toFixed(3)}%</td>
                        <td>$${opp.trade_size}</td>
                        <td>$${Math.round(opp.max_volume)}</td>
                        <td>${Math.round(opp.confidence)}%</td>
                    </tr>`;
                });
                
                html += '</tbody></table></div>';
                container.innerHTML = html;
            } else {
                container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">🔍 No opportunities found. Check debug info above.</p>';
            }
            
            // Exchange status
            const statusContainer = document.getElementById('exchangeStatus');
            if (data.stats && data.stats.exchanges_status) {
                let html = '';
                for (const [name, status] of Object.entries(data.stats.exchanges_status)) {
                    const isOnline = status.includes('online');
                    const pairs = data.stats.exchanges_pairs ? data.stats.exchanges_pairs[name] || 0 : 0;
                    html += `<div style="background: #1a1a1a; padding: 10px; border-radius: 5px; text-align: center; border: 1px solid #333;">
                        <div style="color: #00ff00; font-weight: bold;">${name.toUpperCase()}</div>
                        <div style="color: ${isOnline ? '#00ff00' : '#ff4444'}; font-size: 0.8em;">${status}</div>
                        <div style="color: #888; font-size: 0.7em;">${pairs} pairs</div>
                    </div>`;
                }
                statusContainer.innerHTML = html;
            }
        }
    </script>
</body>
</html>
'''

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def index():
    return render_template_string(MAIN_TEMPLATE)

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    chat_id = request.form.get('chat_id')
    
    if not name or not chat_id:
        return "❌ Please fill in both fields", 400
    
    if user_exists(chat_id):
        return f"✅ {name}, you're already registered!", 200
    
    save_user(name, chat_id)
    CONFIG['TELEGRAM']['users'] = load_users()
    
    welcome_msg = f"🎉 Welcome {name}! You're now registered for arbitrage alerts!"
    thread = threading.Thread(target=send_telegram_sync, args=(welcome_msg, chat_id))
    thread.daemon = True
    thread.start()
    
    return f"✅ Welcome {name}! You'll receive alerts.", 200

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
    except Exception as e:
        print(f"❌ Error: {e}")

# ============================================
# MAIN
# ============================================

def view_users():
    users = load_users()
    print("\n" + "="*50)
    print("📋 REGISTERED USERS")
    print("="*50)
    if users:
        for i, user in enumerate(users, 1):
            print(f"{i}. {user['name']} - Chat ID: {user['chat_id']}")
    else:
        print("No users registered yet")
    print("="*50 + "\n")

async def background_scanner():
    print("🔍 DEBUG SCANNER STARTED")
    print(f"🎯 Min Spread: {CONFIG['MIN_PROFIT_PERCENT']}%")
    print(f"💰 Min Profit: ${CONFIG['MIN_PROFIT_USD']}")
    print()
    
    while True:
        try:
            await engine.scan()
            update_latest_data()
        except Exception as e:
            print(f"❌ Scanner error: {e}")
        await asyncio.sleep(CONFIG['SCAN_INTERVAL'])

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)

async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("="*70)
    print("🔍 ARBITRAGE BOT - DEBUG VERSION")
    print("="*70)
    print("🌐 Web: http://localhost:5000")
    print("📊 Shows: All data, spreads, and why opportunities might be filtered")
    print("="*70 + "\n")
    
    view_users()
    await background_scanner()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Stopping...")

"""
SIMPLE CRYPTO ARBITRAGE BOT
Just run it - no complex dependencies!
"""

import asyncio
import aiohttp
import time
from datetime import datetime
from typing import Dict, List

# Configuration
CONFIG = {
    'MIN_PROFIT_PERCENT': 0.5,
    'MIN_VOLUME_USD': 100,
    'TRADING_FEE': 0.001,
    'BASE_CURRENCIES': ['USDT', 'BTC', 'ETH'],
    'SCAN_INTERVAL': 10,
}

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
                        prices[symbol] = {
                            'bid': float(item.get('bidPrice', 0) or 0),
                            'ask': float(item.get('askPrice', 0) or 0),
                            'volume': float(item.get('volume', 0)) * float(item.get('lastPrice', 0) or 0),
                        }
                return prices

class ArbitrageEngine:
    def __init__(self):
        self.exchanges = {'binance': BinanceAPI()}
    
    async def scan(self):
        all_prices = {}
        for name, exchange in self.exchanges.items():
            prices = await exchange.get_prices()
            if prices:
                all_prices[name] = prices
        
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
            
            fee = CONFIG['TRADING_FEE']
            spread = (sell_price - buy_price) / buy_price * 100
            net_spread = spread - (fee * 2 * 100)
            
            if net_spread > CONFIG['MIN_PROFIT_PERCENT']:
                volume = min(buy_exchange[1].get('volume', 0), sell_exchange[1].get('volume', 0))
                volume = min(volume, 10000)
                
                if volume >= CONFIG['MIN_VOLUME_USD']:
                    investment = buy_price * (volume / sell_price)
                    gross_profit = (sell_price - buy_price) * (volume / sell_price)
                    net_profit = gross_profit - (investment * fee * 2)
                    roi = (net_profit / investment) * 100 if investment > 0 else 0
                    
                    if net_profit > 0:
                        opportunities.append({
                            'pair': pair,
                            'buy_exchange': buy_exchange[0],
                            'sell_exchange': sell_exchange[0],
                            'buy_price': buy_price,
                            'sell_price': sell_price,
                            'spread': net_spread,
                            'profit_usd': net_profit,
                            'roi': roi,
                            'investment': investment,
                        })
        
        opportunities.sort(key=lambda x: x['profit_usd'], reverse=True)
        return opportunities[:10]

async def main():
    engine = ArbitrageEngine()
    print("\n" + "="*60)
    print("🚀 CRYPTO ARBITRAGE BOT - SIMPLE VERSION")
    print("="*60)
    print("📊 Checking Binance only")
    print(f"🎯 Min profit: {CONFIG['MIN_PROFIT_PERCENT']}%")
    print("="*60 + "\n")
    
    while True:
        try:
            print(f"⏱️  Scanning at {datetime.now().strftime('%H:%M:%S')}...")
            opportunities = await engine.scan()
            
            if opportunities:
                print(f"\n🎯 Found {len(opportunities)} opportunities!\n")
                for opp in opportunities:
                    print(f"💰 {opp['pair']}")
                    print(f"   Profit: ${opp['profit_usd']:.2f} ({opp['roi']:.2f}%)")
                    print(f"   Buy: {opp['buy_exchange']} @ ${opp['buy_price']:.4f}")
                    print(f"   Sell: {opp['sell_exchange']} @ ${opp['sell_price']:.4f}")
                    print(f"   Spread: {opp['spread']:.2f}%")
                    print(f"   Capital: ${opp['investment']:.0f}\n")
            else:
                print("   No opportunities found")
            
            print("-"*60)
            await asyncio.sleep(CONFIG['SCAN_INTERVAL'])
            
        except KeyboardInterrupt:
            print("\n👋 Stopping...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

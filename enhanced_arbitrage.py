"""
ENHANCED CRYPTO ARBITRAGE BOT
Finds more opportunities with better detection
"""

import asyncio
import aiohttp
import time
from datetime import datetime
from typing import Dict, List
import json

# Configuration
CONFIG = {
    'MIN_PROFIT_PERCENT': 0.1,      # Lower threshold to find more opportunities
    'MIN_VOLUME_USD': 10,            # Lower volume requirement
    'TRADING_FEE': 0.001,
    'BASE_CURRENCIES': ['USDT', 'BTC', 'ETH'],
    'SCAN_INTERVAL': 5,              # Scan more frequently
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
                        try:
                            bid = float(item.get('bidPrice', 0) or 0)
                            ask = float(item.get('askPrice', 0) or 0)
                            last = float(item.get('lastPrice', 0) or 0)
                            volume = float(item.get('volume', 0)) * last
                            
                            if bid > 0 and ask > 0 and volume > 0:
                                prices[symbol] = {
                                    'bid': bid,
                                    'ask': ask,
                                    'last': last,
                                    'volume': volume,
                                    'spread': ((ask - bid) / bid * 100) if bid > 0 else 0
                                }
                        except:
                            continue
                return prices

class ArbitrageEngine:
    def __init__(self):
        self.exchanges = {'binance': BinanceAPI()}
        self.opportunity_count = 0
    
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
            
            # Calculate different profit metrics
            fee = CONFIG['TRADING_FEE']
            raw_spread = (sell_price - buy_price) / buy_price * 100
            net_spread = raw_spread - (fee * 2 * 100)
            
            if net_spread > CONFIG['MIN_PROFIT_PERCENT']:
                volume = min(buy_exchange[1].get('volume', 0), sell_exchange[1].get('volume', 0))
                
                # Try different trade sizes
                for trade_size in [100, 500, 1000, 5000]:
                    if volume >= trade_size:
                        investment = buy_price * (trade_size / sell_price)
                        gross_profit = (sell_price - buy_price) * (trade_size / sell_price)
                        net_profit = gross_profit - (investment * fee * 2)
                        roi = (net_profit / investment) * 100 if investment > 0 else 0
                        
                        if net_profit > 0.01:  # At least 1 cent profit
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
                                'roi': roi,
                                'investment': investment,
                                'volume_available': volume,
                            })
                            break  # Found a profitable size, no need to check larger ones
        
        # Sort by profit and remove duplicates
        opportunities.sort(key=lambda x: x['profit_usd'], reverse=True)
        unique_opps = []
        seen = set()
        for opp in opportunities:
            key = f"{opp['pair']}_{opp['buy_exchange']}_{opp['sell_exchange']}"
            if key not in seen:
                seen.add(key)
                unique_opps.append(opp)
        
        self.opportunity_count += len(unique_opps)
        return unique_opps[:20]

async def main():
    engine = ArbitrageEngine()
    print("\n" + "="*60)
    print("🚀 ENHANCED CRYPTO ARBITRAGE BOT")
    print("="*60)
    print(f"📊 Checking Binance")
    print(f"🎯 Min profit: {CONFIG['MIN_PROFIT_PERCENT']}%")
    print(f"💰 Min trade sizes: $100, $500, $1000, $5000")
    print("="*60 + "\n")
    
    start_time = time.time()
    
    while True:
        try:
            scan_start = datetime.now()
            print(f"⏱️  Scan at {scan_start.strftime('%H:%M:%S')}...")
            
            opportunities = await engine.scan()
            elapsed = (datetime.now() - scan_start).total_seconds()
            
            if opportunities:
                print(f"\n🎯 Found {len(opportunities)} opportunities!\n")
                for i, opp in enumerate(opportunities[:5], 1):
                    print(f"{i}. 💰 {opp['pair']}")
                    print(f"   Profit: ${opp['profit_usd']:.2f} ({opp['roi']:.2f}%)")
                    print(f"   Buy: {opp['buy_exchange']} @ ${opp['buy_price']:.4f}")
                    print(f"   Sell: {opp['sell_exchange']} @ ${opp['sell_price']:.4f}")
                    print(f"   Spread: {opp['net_spread']:.2f}% (raw: {opp['raw_spread']:.2f}%)")
                    print(f"   Trade size: ${opp['trade_size']} | Investment: ${opp['investment']:.0f}")
                    print(f"   Volume available: ${opp['volume_available']:.0f}\n")
                
                print(f"📊 Total opportunities found so far: {engine.opportunity_count}")
            else:
                print("   No opportunities found this scan")
            
            print(f"⏱️  Scan took: {elapsed:.2f}s")
            print("-"*60)
            
            await asyncio.sleep(CONFIG['SCAN_INTERVAL'])
            
        except KeyboardInterrupt:
            print("\n👋 Stopping...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

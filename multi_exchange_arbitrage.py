"""
MULTI-EXCHANGE ARBITRAGE BOT
Checks Binance + Bybit for real arbitrage opportunities
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import Dict

CONFIG = {
    'MIN_PROFIT_PERCENT': 0.1,      # Lower threshold
    'MIN_VOLUME_USD': 10,            # Smaller trades
    'TRADING_FEE': 0.001,            # 0.1% per trade
    'BASE_CURRENCIES': ['USDT', 'BTC', 'ETH'],
    'SCAN_INTERVAL': 5,
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

async def main():
    exchanges = {
        'binance': BinanceAPI(),
        'bybit': BybitAPI(),
    }
    
    print("\n" + "="*60)
    print("🚀 MULTI-EXCHANGE ARBITRAGE BOT")
    print("="*60)
    print(f"📊 Exchanges: {', '.join(exchanges.keys())}")
    print(f"🎯 Min profit: {CONFIG['MIN_PROFIT_PERCENT']}%")
    print(f"💰 Min trade: ${CONFIG['MIN_VOLUME_USD']}")
    print("="*60 + "\n")
    
    found_count = 0
    
    while True:
        try:
            print(f"⏱️  Scan at {datetime.now().strftime('%H:%M:%S')}...", end=" ")
            
            # Get prices from all exchanges
            all_prices = {}
            exchange_status = []
            
            for name, exchange in exchanges.items():
                try:
                    prices = await exchange.get_prices()
                    if prices:
                        all_prices[name] = prices
                        exchange_status.append(f"{name}: {len(prices)} pairs ✓")
                    else:
                        exchange_status.append(f"{name}: No data ✗")
                except Exception as e:
                    exchange_status.append(f"{name}: Error - {e}")
            
            print(" | ".join(exchange_status))
            
            # Find arbitrage opportunities
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
                
                # Find best buy and sell across exchanges
                buy_exchange = min(exchange_data.items(), key=lambda x: x[1]['ask'])
                sell_exchange = max(exchange_data.items(), key=lambda x: x[1]['bid'])
                
                buy_price = buy_exchange[1]['ask']
                sell_price = sell_exchange[1]['bid']
                
                if buy_price <= 0 or sell_price <= 0:
                    continue
                
                # Calculate profit after fees
                raw_spread = (sell_price - buy_price) / buy_price * 100
                fee_spread = CONFIG['TRADING_FEE'] * 2 * 100
                net_spread = raw_spread - fee_spread
                
                if net_spread > CONFIG['MIN_PROFIT_PERCENT']:
                    # Try different trade sizes
                    for trade_size in [10, 50, 100, 500, 1000]:
                        volume_available = min(
                            buy_exchange[1].get('volume', 0),
                            sell_exchange[1].get('volume', 0)
                        )
                        
                        if volume_available >= trade_size:
                            investment = buy_price * (trade_size / sell_price)
                            gross_profit = (sell_price - buy_price) * (trade_size / sell_price)
                            net_profit = gross_profit - (investment * CONFIG['TRADING_FEE'] * 2)
                            
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
                                    'roi': (net_profit / investment) * 100 if investment > 0 else 0,
                                    'volume_available': volume_available,
                                })
                                break  # Found profitable size, move to next pair
            
            # Show results
            if opportunities:
                opportunities.sort(key=lambda x: x['profit_usd'], reverse=True)
                found_count += len(opportunities)
                
                print(f"\n🎯 Found {len(opportunities)} opportunities!\n")
                for opp in opportunities[:5]:
                    print(f"💰 {opp['pair']}")
                    print(f"   Profit: ${opp['profit_usd']:.2f} ({opp['roi']:.2f}%)")
                    print(f"   Buy on {opp['buy_exchange']}: ${opp['buy_price']:.6f}")
                    print(f"   Sell on {opp['sell_exchange']}: ${opp['sell_price']:.6f}")
                    print(f"   Spread: {opp['net_spread']:.2f}% (raw: {opp['raw_spread']:.2f}%)")
                    print(f"   Trade size: ${opp['trade_size']} | Available: ${opp['volume_available']:.0f}")
                    print()
                
                print(f"📊 Total opportunities found so far: {found_count}")
            else:
                print("   No opportunities found")
            
            print("-"*60)
            await asyncio.sleep(CONFIG['SCAN_INTERVAL'])
            
        except KeyboardInterrupt:
            print("\n👋 Stopping...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

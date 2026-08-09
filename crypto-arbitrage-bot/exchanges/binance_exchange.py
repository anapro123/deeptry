import aiohttp
import asyncio
from typing import Dict, List, Optional
from decimal import Decimal
from .base_exchange import BaseExchange
from utils.rate_limiter import RateLimiter
import hashlib
import hmac
import time

class BinanceExchange(BaseExchange):
    def __init__(self, api_key: str = None, api_secret: str = None):
        super().__init__('binance', api_key, api_secret)
        self.base_url = 'https://api.binance.com'
        self.ws_url = 'wss://stream.binance.com:9443/ws'
        self.rate_limiter = RateLimiter(max_requests=1200, time_window=60)
        
    async def get_ticker(self, symbol: str) -> Dict:
        await self.rate_limiter.acquire()
        url = f"{self.base_url}/api/v3/ticker/24hr"
        params = {'symbol': symbol}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return {
                    'symbol': data['symbol'],
                    'bid': float(data['bidPrice']),
                    'ask': float(data['askPrice']),
                    'last': float(data['lastPrice']),
                    'volume': float(data['volume']),
                    'high': float(data['highPrice']),
                    'low': float(data['lowPrice'])
                }
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        await self.rate_limiter.acquire()
        url = f"{self.base_url}/api/v3/depth"
        params = {'symbol': symbol, 'limit': limit}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return {
                    'bids': [(float(price), float(qty)) for price, qty in data['bids']],
                    'asks': [(float(price), float(qty)) for price, qty in data['asks']]
                }
    
    async def get_fee(self, symbol: str) -> float:
        # Binance maker/taker fees
        return 0.001  # 0.1% default
    
    async def create_signed_request(self, method: str, endpoint: str, 
                                   params: Dict = None) -> Dict:
        timestamp = int(time.time() * 1000)
        if params is None:
            params = {}
        params['timestamp'] = timestamp
        params['recvWindow'] = 5000
        
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
        headers = {'X-MBX-APIKEY': self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers) as response:
                return await response.json()
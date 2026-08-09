import asyncio
from typing import Dict, List, Set
from decimal import Decimal
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from utils.cache import Cache
from utils.logger import get_logger
from exchanges.exchange_factory import ExchangeFactory

logger = get_logger(__name__)

class DataFetcher:
    def __init__(self, exchange_names: List[str]):
        self.exchanges = {}
        self.cache = Cache(ttl=5)  # 5 second cache
        self.semaphore = asyncio.Semaphore(20)  # Limit concurrent requests
        
        for name in exchange_names:
            self.exchanges[name] = ExchangeFactory.create_exchange(name)
            
    async def fetch_all_market_data(self) -> Dict:
        """Fetch market data from all exchanges concurrently"""
        tasks = []
        for exchange_name, exchange in self.exchanges.items():
            tasks.append(self._fetch_exchange_data(exchange_name, exchange))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        market_data = {}
        for i, result in enumerate(results):
            exchange_name = list(self.exchanges.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"Error fetching data from {exchange_name}: {result}")
                market_data[exchange_name] = {}
            else:
                market_data[exchange_name] = result
                
        return market_data
    
    async def _fetch_exchange_data(self, exchange_name: str, exchange) -> Dict:
        """Fetch data from a single exchange"""
        async with self.semaphore:
            cache_key = f"market_data:{exchange_name}"
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                return cached_data
            
            try:
                # Get available trading pairs
                pairs = await exchange.get_available_pairs()
                
                # Fetch ticker data for all pairs in batches
                tickers = {}
                batch_size = 50
                for i in range(0, len(pairs), batch_size):
                    batch = pairs[i:i+batch_size]
                    batch_tasks = [exchange.get_ticker(pair) for pair in batch]
                    batch_results = await asyncio.gather(*batch_tasks, 
                                                        return_exceptions=True)
                    
                    for pair, result in zip(batch, batch_results):
                        if not isinstance(result, Exception):
                            tickers[pair] = result
                
                # Get order books for top pairs
                order_books = {}
                top_pairs = sorted(tickers.items(), 
                                 key=lambda x: x[1].get('volume', 0), 
                                 reverse=True)[:50]
                
                for pair, _ in top_pairs:
                    order_book = await exchange.get_order_book(pair)
                    order_books[pair] = order_book
                
                exchange_data = {
                    'tickers': tickers,
                    'order_books': order_books,
                    'fee': await exchange.get_fee('USDT')  # Default fee
                }
                
                await self.cache.set(cache_key, exchange_data)
                return exchange_data
                
            except Exception as e:
                logger.error(f"Error in _fetch_exchange_data for {exchange_name}: {e}")
                raise
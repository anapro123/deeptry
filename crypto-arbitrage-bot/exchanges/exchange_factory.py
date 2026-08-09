from typing import Dict, Type
from .base_exchange import BaseExchange
from .binance_exchange import BinanceExchange
from .bybit_exchange import BybitExchange
from .okx_exchange import OKXExchange
# ... import other exchanges

class ExchangeFactory:
    _exchanges: Dict[str, Type[BaseExchange]] = {
        'binance': BinanceExchange,
        'bybit': BybitExchange,
        'okx': OKXExchange,
        # ... register other exchanges
    }
    
    @classmethod
    def create_exchange(cls, exchange_name: str, api_key: str = None, 
                       api_secret: str = None) -> BaseExchange:
        exchange_class = cls._exchanges.get(exchange_name.lower())
        if not exchange_class:
            raise ValueError(f"Unsupported exchange: {exchange_name}")
        return exchange_class(api_key, api_secret)
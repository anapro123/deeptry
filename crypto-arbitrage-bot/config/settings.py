import os
from typing import Dict, List
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class TradingConfig:
    base_currencies: List[str] = None
    min_profit_percentage: float = 0.5
    min_trade_volume: float = 100
    max_slippage: float = 0.01
    max_execution_time: float = 5.0
    trading_fee_percentage: float = 0.1
    withdrawal_fee_buffer: float = 0.01
    gas_price_buffer: float = 1.2
    
    def __post_init__(self):
        if self.base_currencies is None:
            self.base_currencies = ['USDT', 'BTC', 'ETH']

class Settings:
    def __init__(self):
        self.trading_config = TradingConfig()
        self.exchanges = [
            'binance', 'bybit', 'okx', 'kucoin', 
            'kraken', 'coinbase', 'bitget', 'gateio', 'mexc'
        ]
        self.api_keys = {
            'binance': os.getenv('BINANCE_API_KEY'),
            'binance_secret': os.getenv('BINANCE_API_SECRET'),
            'bybit': os.getenv('BYBIT_API_KEY'),
            'bybit_secret': os.getenv('BYBIT_API_SECRET'),
            # ... add other exchange keys
        }
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.scan_interval = int(os.getenv('SCAN_INTERVAL', 5))  # seconds
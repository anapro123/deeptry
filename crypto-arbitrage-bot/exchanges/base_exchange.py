from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from decimal import Decimal
import asyncio

class BaseExchange(ABC):
    def __init__(self, name: str, api_key: str = None, api_secret: str = None):
        self.name = name
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limiter = None
        self.session = None
        
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker data for a symbol"""
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        """Get order book for a symbol"""
        pass
    
    @abstractmethod
    async def get_balance(self, currency: str) -> Decimal:
        """Get account balance for a currency"""
        pass
    
    @abstractmethod
    async def create_order(self, symbol: str, side: str, order_type: str, 
                          amount: float, price: float = None) -> Dict:
        """Create a new order"""
        pass
    
    @abstractmethod
    async def get_fee(self, symbol: str) -> float:
        """Get trading fee for a symbol"""
        pass
    
    async def get_available_pairs(self) -> List[str]:
        """Get list of available trading pairs"""
        pass
    
    async def close(self):
        """Close the exchange connection"""
        if self.session:
            await self.session.close()
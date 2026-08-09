from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

class OpportunityType(Enum):
    CROSS_EXCHANGE = "cross_exchange"
    TRIANGULAR = "triangular"
    MULTI_HOP = "multi_hop"

@dataclass
class ArbitrageOpportunity:
    type: OpportunityType
    base_currency: str
    pair: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread: float
    available_liquidity: float
    timestamp: datetime
    
    # Optional fields for different types
    exchange: Optional[str] = None
    cycle: Optional[List[str]] = None
    expected_profit: Optional[dict] = None
    required_capital: Optional[float] = None
    net_profit: Optional[float] = None
    roi: Optional[float] = None
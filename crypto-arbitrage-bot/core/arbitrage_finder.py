import itertools
from typing import Dict, List, Tuple, Optional
from decimal import Decimal, getcontext
import numpy as np
from models.opportunity import ArbitrageOpportunity, OpportunityType
from core.profit_calculator import ProfitCalculator
from utils.logger import get_logger

logger = get_logger(__name__)
getcontext().prec = 28

class ArbitrageFinder:
    def __init__(self, config):
        self.config = config
        self.profit_calculator = ProfitCalculator(config)
        self.base_currencies = config.trading_config.base_currencies
        
    async def find_opportunities(self, market_data: Dict) -> List[ArbitrageOpportunity]:
        """Find all arbitrage opportunities from market data"""
        opportunities = []
        
        # Find cross-exchange arbitrage
        cross_exchange_opps = await self._find_cross_exchange_arbitrage(market_data)
        opportunities.extend(cross_exchange_opps)
        
        # Find triangular arbitrage within exchanges
        for exchange_name, data in market_data.items():
            if data:
                triangular_opps = await self._find_triangular_arbitrage(
                    exchange_name, data
                )
                opportunities.extend(triangular_opps)
        
        # Find multi-hop opportunities
        multi_hop_opps = await self._find_multi_hop_opportunities(market_data)
        opportunities.extend(multi_hop_opps)
        
        # Filter and rank opportunities
        opportunities = await self._filter_opportunities(opportunities)
        opportunities.sort(key=lambda x: x.roi, reverse=True)
        
        return opportunities
    
    async def _find_cross_exchange_arbitrage(self, market_data: Dict) -> List[ArbitrageOpportunity]:
        """Find cross-exchange arbitrage opportunities"""
        opportunities = []
        
        # Group tickers by trading pair
        pair_prices = {}
        for exchange_name, data in market_data.items():
            for pair, ticker in data.get('tickers', {}).items():
                # Filter for base currencies
                base_currency = self._extract_base_currency(pair)
                if base_currency not in self.base_currencies:
                    continue
                    
                if pair not in pair_prices:
                    pair_prices[pair] = {}
                pair_prices[pair][exchange_name] = {
                    'bid': ticker.get('bid', 0),
                    'ask': ticker.get('ask', 0),
                    'volume': ticker.get('volume', 0),
                    'order_book': data.get('order_books', {}).get(pair, {})
                }
        
        # Find arbitrage opportunities across exchanges
        for pair, exchanges in pair_prices.items():
            if len(exchanges) < 2:
                continue
                
            for (buy_exchange, buy_data), (sell_exchange, sell_data) in itertools.combinations(
                exchanges.items(), 2
            ):
                buy_price = buy_data['ask']
                sell_price = sell_data['bid']
                
                if buy_price > 0 and sell_price > 0:
                    spread = (sell_price - buy_price) / buy_price * 100
                    
                    if spread > self.config.trading_config.min_profit_percentage:
                        # Check liquidity
                        buy_liquidity = self._check_liquidity(buy_data['order_book'], 'asks')
                        sell_liquidity = self._check_liquidity(sell_data['order_book'], 'bids')
                        min_liquidity = min(buy_liquidity, sell_liquidity)
                        
                        if min_liquidity >= self.config.trading_config.min_trade_volume:
                            opportunity = ArbitrageOpportunity(
                                type=OpportunityType.CROSS_EXCHANGE,
                                base_currency=self._extract_base_currency(pair),
                                pair=pair,
                                buy_exchange=buy_exchange,
                                sell_exchange=sell_exchange,
                                buy_price=buy_price,
                                sell_price=sell_price,
                                spread=spread,
                                available_liquidity=min_liquidity,
                                timestamp=datetime.utcnow()
                            )
                            opportunities.append(opportunity)
        
        return opportunities
    
    async def _find_triangular_arbitrage(self, exchange_name: str, 
                                        data: Dict) -> List[ArbitrageOpportunity]:
        """Find triangular arbitrage opportunities within a single exchange"""
        opportunities = []
        tickers = data.get('tickers', {})
        
        # Build graph of trading pairs
        graph = self._build_trading_graph(tickers)
        
        # Find arbitrage cycles
        for base_currency in self.base_currencies:
            cycles = self._find_cycles(graph, base_currency)
            
            for cycle in cycles:
                profit_ratio = self._calculate_cycle_profit(cycle, tickers)
                if profit_ratio > 1 + (self.config.trading_config.min_profit_percentage / 100):
                    # Calculate expected profit
                    expected_profit = self.profit_calculator.calculate_triangular_profit(
                        cycle, 
                        self.config.trading_config.min_trade_volume
                    )
                    
                    if expected_profit['net_profit'] > 0:
                        opportunity = ArbitrageOpportunity(
                            type=OpportunityType.TRIANGULAR,
                            base_currency=base_currency,
                            exchange=exchange_name,
                            cycle=cycle,
                            expected_profit=expected_profit,
                            timestamp=datetime.utcnow()
                        )
                        opportunities.append(opportunity)
        
        return opportunities
    
    def _build_trading_graph(self, tickers: Dict) -> Dict:
        """Build a graph of trading pairs for triangular arbitrage"""
        graph = {}
        
        for pair, ticker in tickers.items():
            base, quote = self._split_pair(pair)
            if quote not in graph:
                graph[quote] = {}
            graph[quote][base] = {
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0)
            }
        
        return graph
    
    def _find_cycles(self, graph: Dict, start_currency: str, 
                    max_length: int = 3) -> List[List[str]]:
        """Find arbitrage cycles in the trading graph"""
        cycles = []
        
        def dfs(current: str, path: List[str]):
            if len(path) > max_length:
                return
            
            if current == start_currency and len(path) > 2:
                cycles.append(path.copy())
                return
            
            if current not in graph:
                return
                
            for neighbor in graph[current]:
                if neighbor not in path or neighbor == start_currency:
                    path.append(neighbor)
                    dfs(neighbor, path)
                    path.pop()
        
        dfs(start_currency, [start_currency])
        return cycles
    
    def _calculate_cycle_profit(self, cycle: List[str], tickers: Dict) -> float:
        """Calculate profit ratio for a triangular cycle"""
        ratio = 1.0
        
        for i in range(len(cycle) - 1):
            from_currency = cycle[i]
            to_currency = cycle[i + 1]
            pair = f"{to_currency}/{from_currency}"  # Adjust based on exchange
            
            if pair in tickers:
                ticker = tickers[pair]
                # Use ask price when selling, bid when buying
                price = ticker['ask'] if i == 0 else ticker['bid']
                ratio *= price
                
        return ratio
    
    def _check_liquidity(self, order_book: Dict, side: str) -> float:
        """Check liquidity at the top of the order book"""
        if not order_book or side not in order_book:
            return 0
        
        # Calculate total volume at top 5 price levels
        levels = order_book[side][:5]
        total_volume = sum(level[1] for level in levels)
        return total_volume
    
    def _extract_base_currency(self, pair: str) -> str:
        """Extract base currency from trading pair"""
        for base in self.base_currencies:
            if pair.endswith(base):
                return base
        return ''
    
    def _split_pair(self, pair: str) -> Tuple[str, str]:
        """Split trading pair into base and quote currencies"""
        for base in self.base_currencies:
            if pair.endswith(base):
                return pair[:-len(base)], base
        return pair, ''
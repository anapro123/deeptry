from typing import Dict, List, Tuple
from decimal import Decimal, getcontext
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)
getcontext().prec = 28

class ProfitCalculator:
    def __init__(self, config):
        self.config = config
        self.fee_rates = {}
        
    def calculate_cross_exchange_profit(self, buy_price: float, sell_price: float, 
                                       amount: float, buy_fee: float = 0.001,
                                       sell_fee: float = 0.001) -> Dict:
        """Calculate profit for cross-exchange arbitrage"""
        try:
            # Calculate gross profit
            gross_profit = (sell_price - buy_price) * amount
            
            # Calculate trading fees
            buy_fee_amount = buy_price * amount * buy_fee
            sell_fee_amount = sell_price * amount * sell_fee
            
            # Calculate withdrawal/deposit fees (estimated)
            withdrawal_fee = self._estimate_withdrawal_fee()
            deposit_fee = self._estimate_deposit_fee()
            
            # Calculate network/gas fees
            gas_fee = self._estimate_gas_fee()
            
            # Calculate slippage
            slippage_cost = self._calculate_slippage_cost(buy_price, sell_price, amount)
            
            # Net profit
            total_fees = buy_fee_amount + sell_fee_amount + withdrawal_fee + deposit_fee + gas_fee + slippage_cost
            net_profit = gross_profit - total_fees
            
            # ROI
            investment = buy_price * amount
            roi = (net_profit / investment) * 100 if investment > 0 else 0
            
            return {
                'gross_profit': gross_profit,
                'net_profit': net_profit,
                'roi': roi,
                'total_fees': total_fees,
                'buy_fee': buy_fee_amount,
                'sell_fee': sell_fee_amount,
                'withdrawal_fee': withdrawal_fee,
                'deposit_fee': deposit_fee,
                'gas_fee': gas_fee,
                'slippage_cost': slippage_cost,
                'required_capital': investment + total_fees
            }
            
        except Exception as e:
            logger.error(f"Error calculating cross-exchange profit: {e}")
            return None
    
    def calculate_triangular_profit(self, cycle: List[str], amount: float) -> Dict:
        """Calculate profit for triangular arbitrage"""
        try:
            # Simulate the triangular trade
            current_amount = amount
            
            for i in range(len(cycle) - 1):
                from_currency = cycle[i]
                to_currency = cycle[i + 1]
                price = self._get_price(from_currency, to_currency)
                fee = self._get_fee(from_currency, to_currency)
                
                # Execute trade
                current_amount = current_amount * price * (1 - fee)
            
            # Final amount in base currency
            net_profit = current_amount - amount
            roi = (net_profit / amount) * 100
            
            return {
                'gross_profit': current_amount - amount,
                'net_profit': net_profit - self._estimate_total_fees(current_amount),
                'roi': roi,
                'total_fees': self._estimate_total_fees(current_amount),
                'required_capital': amount
            }
            
        except Exception as e:
            logger.error(f"Error calculating triangular profit: {e}")
            return None
    
    def _estimate_withdrawal_fee(self) -> float:
        """Estimate withdrawal fee based on network conditions"""
        return self.config.trading_config.withdrawal_fee_buffer
    
    def _estimate_deposit_fee(self) -> float:
        """Estimate deposit fee"""
        return 0.0  # Most exchanges don't charge deposit fees
    
    def _estimate_gas_fee(self) -> float:
        """Estimate network gas fees"""
        # This should be fetched from an API or service
        return self.config.trading_config.gas_price_buffer * 1.0
    
    def _calculate_slippage_cost(self, buy_price: float, sell_price: float, 
                                amount: float) -> float:
        """Calculate expected slippage cost"""
        # Simple model: slippage increases with order size relative to volume
        estimated_slippage = self.config.trading_config.max_slippage * 0.5
        return buy_price * amount * estimated_slippage
    
    def _estimate_total_fees(self, amount: float) -> float:
        """Estimate total fees for a trade"""
        trading_fee_rate = self.config.trading_config.trading_fee_percentage / 100
        return amount * trading_fee_rate * 2 + self._estimate_withdrawal_fee()
    
    def _get_price(self, from_currency: str, to_currency: str) -> float:
        # Placeholder - should fetch from actual market data
        return 1.0
    
    def _get_fee(self, from_currency: str, to_currency: str) -> float:
        return 0.001
from typing import List, Dict
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from models.opportunity import ArbitrageOpportunity
from utils.logger import get_logger

logger = get_logger(__name__)

class OpportunityRanker:
    def __init__(self, config):
        self.config = config
        self.scaler = MinMaxScaler()
        
    def rank_opportunities(self, opportunities: List[ArbitrageOpportunity]) -> List[Dict]:
        """Rank opportunities by multiple criteria"""
        if not opportunities:
            return []
        
        # Prepare features for ranking
        features = []
        for opp in opportunities:
            features.append({
                'roi': opp.roi,
                'net_profit': opp.net_profit,
                'liquidity': opp.available_liquidity,
                'execution_time': self._estimate_execution_time(opp),
                'historical_success': self._get_historical_success(opp)
            })
        
        # Normalize features
        feature_matrix = np.array([[f['roi'], f['net_profit'], f['liquidity'], 
                                   f['execution_time'], f['historical_success']] 
                                  for f in features])
        
        normalized_features = self.scaler.fit_transform(feature_matrix)
        
        # Calculate combined score
        weights = [0.35, 0.25, 0.20, 0.10, 0.10]  # ROI, net profit, liquidity, execution, historical
        
        combined_scores = np.sum(normalized_features * weights, axis=1)
        
        # Sort and add ranking info
        ranked_opportunities = []
        for i, opp in enumerate(opportunities):
            ranked_opportunities.append({
                'opportunity': opp,
                'rank': i + 1,
                'combined_score': combined_scores[i],
                'confidence_score': self._calculate_confidence_score(opp),
                'estimated_execution_time': features[i]['execution_time'],
                'historical_success_probability': features[i]['historical_success']
            })
        
        ranked_opportunities.sort(key=lambda x: x['combined_score'], reverse=True)
        
        return ranked_opportunities
    
    def _estimate_execution_time(self, opportunity: ArbitrageOpportunity) -> float:
        """Estimate execution time in seconds"""
        # Simple model based on market liquidity and type
        base_time = {
            'cross_exchange': 2.0,
            'triangular': 1.5,
            'multi_hop': 3.0
        }.get(opportunity.type.value, 2.0)
        
        liquidity_factor = max(1.0, 10.0 / opportunity.available_liquidity)
        return base_time * liquidity_factor
    
    def _get_historical_success(self, opportunity: ArbitrageOpportunity) -> float:
        """Get historical success probability"""
        # This should be based on actual historical data
        return 0.85  # Placeholder
    
    def _calculate_confidence_score(self, opportunity: ArbitrageOpportunity) -> float:
        """Calculate confidence score for an opportunity"""
        factors = {
            'liquidity': min(1.0, opportunity.available_liquidity / 10000),
            'spread': min(1.0, opportunity.spread / 5.0),
            'historical': self._get_historical_success(opportunity)
        }
        
        weights = {'liquidity': 0.4, 'spread': 0.3, 'historical': 0.3}
        confidence = sum(factors[k] * weights[k] for k in factors)
        
        return min(1.0, confidence)
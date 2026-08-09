import asyncio
import signal
import sys
from datetime import datetime
from typing import Dict, List
import json

from config.settings import Settings
from core.data_fetcher import DataFetcher
from core.arbitrage_finder import ArbitrageFinder
from core.opportunity_ranker import OpportunityRanker
from alerts.alert_manager import AlertManager
from utils.logger import setup_logging, get_logger
from utils.cache import Cache
from dashboard.app import Dashboard

logger = get_logger(__name__)

class ArbitrageBot:
    def __init__(self):
        self.settings = Settings()
        self.logger = setup_logging(self.settings.log_level)
        
        # Initialize components
        self.data_fetcher = DataFetcher(self.settings.exchanges)
        self.arbitrage_finder = ArbitrageFinder(self.settings)
        self.opportunity_ranker = OpportunityRanker(self.settings)
        self.alert_manager = AlertManager(self.settings.api_keys)
        self.cache = Cache()
        
        # State
        self.running = False
        self.last_opportunities = []
        self.stats = {
            'scans_completed': 0,
            'opportunities_found': 0,
            'total_profit_estimated': 0.0,
            'last_scan_time': None,
            'avg_scan_duration': 0.0
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    async def run(self):
        """Main bot execution loop"""
        self.running = True
        self.logger.info("Starting Crypto Arbitrage Bot...")
        
        # Start dashboard in separate task
        dashboard_task = asyncio.create_task(self._run_dashboard())
        
        while self.running:
            try:
                start_time = datetime.utcnow()
                
                # Fetch market data
                self.logger.info("Fetching market data...")
                market_data = await self.data_fetcher.fetch_all_market_data()
                
                # Find opportunities
                self.logger.info("Scanning for arbitrage opportunities...")
                opportunities = await self.arbitrage_finder.find_opportunities(market_data)
                
                # Rank opportunities
                ranked_opportunities = self.opportunity_ranker.rank_opportunities(opportunities)
                
                # Update statistics
                self._update_stats(ranked_opportunities, start_time)
                
                # Send alerts for top opportunities
                if ranked_opportunities:
                    top_opportunities = ranked_opportunities[:10]  # Top 10
                    await self.alert_manager.check_and_alert(top_opportunities)
                    
                    # Cache opportunities
                    await self.cache.set('latest_opportunities', ranked_opportunities, ttl=300)
                    
                    # Log top opportunities
                    self._log_top_opportunities(top_opportunities)
                
                # Update dashboard data
                await self._update_dashboard(ranked_opportunities)
                
                # Wait before next scan
                await asyncio.sleep(self.settings.scan_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying
        
        # Cleanup
        await dashboard_task
        await self._cleanup()
    
    async def _run_dashboard(self):
        """Run the dashboard web server"""
        dashboard = Dashboard(self)
        await dashboard.run()
    
    async def _update_dashboard(self, opportunities: List[Dict]):
        """Update dashboard with latest data"""
        await self.cache.set('dashboard_data', {
            'opportunities': opportunities[:20],  # Top 20
            'stats': self.stats,
            'timestamp': datetime.utcnow().isoformat()
        }, ttl=60)
    
    def _update_stats(self, opportunities: List[Dict], start_time: datetime):
        """Update bot statistics"""
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        self.stats['scans_completed'] += 1
        self.stats['opportunities_found'] = len(opportunities)
        self.stats['last_scan_time'] = datetime.utcnow().isoformat()
        self.stats['avg_scan_duration'] = (
            (self.stats['avg_scan_duration'] * (self.stats['scans_completed'] - 1) + duration) 
            / self.stats['scans_completed']
        )
        
        if opportunities:
            total_profit = sum(o['opportunity'].net_profit for o in opportunities[:10])
            self.stats['total_profit_estimated'] += total_profit
    
    def _log_top_opportunities(self, opportunities: List[Dict]):
        """Log top opportunities to console"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"TOP {len(opportunities)} ARBITRAGE OPPORTUNITIES FOUND")
        self.logger.info(f"{'='*60}")
        
        for i, opp_data in enumerate(opportunities[:5], 1):
            opp = opp_data['opportunity']
            self.logger.info(
                f"{i}. {opp.type.value} | {opp.pair} | "
                f"ROI: {opp.roi:.2f}% | Profit: ${opp.net_profit:.2f} | "
                f"Confidence: {opp_data['confidence_score']:.2%}"
            )
            self.logger.info(f"   Buy: {opp.buy_exchange} @ ${opp.buy_price:.4f} | "
                           f"Sell: {opp.sell_exchange} @ ${opp.sell_price:.4f}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def _cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up...")
        await self.data_fetcher.close()
        await self.cache.close()
        self.logger.info("Bot stopped.")

if __name__ == "__main__":
    bot = ArbitrageBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        sys.exit(1)
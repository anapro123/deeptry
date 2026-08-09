import asyncio
from typing import Dict, List, Callable, Any
from datetime import datetime
import json
from utils.logger import get_logger
from alerts.notifiers import (
    TelegramNotifier, DiscordNotifier, 
    EmailNotifier, WebhookNotifier, DesktopNotifier
)

logger = get_logger(__name__)

class AlertManager:
    def __init__(self, config):
        self.config = config
        self.notifiers = {}
        self.thresholds = {
            'min_profit': 1.0,  # Percentage
            'min_roi': 2.0,
            'min_confidence': 0.7
        }
        self.active_alerts = {}
        self._init_notifiers()
        
    def _init_notifiers(self):
        """Initialize notification channels"""
        if self.config.get('telegram_token') and self.config.get('telegram_chat_id'):
            self.notifiers['telegram'] = TelegramNotifier(
                self.config['telegram_token'],
                self.config['telegram_chat_id']
            )
        
        if self.config.get('discord_webhook_url'):
            self.notifiers['discord'] = DiscordNotifier(
                self.config['discord_webhook_url']
            )
        
        if self.config.get('email_config'):
            self.notifiers['email'] = EmailNotifier(
                self.config['email_config']
            )
        
        if self.config.get('webhook_url'):
            self.notifiers['webhook'] = WebhookNotifier(
                self.config['webhook_url']
            )
        
        self.notifiers['desktop'] = DesktopNotifier()
    
    async def check_and_alert(self, opportunities: List[Any]) -> None:
        """Check opportunities and send alerts if criteria are met"""
        for opp_data in opportunities:
            opp = opp_data['opportunity']
            
            # Check if alert criteria are met
            if (opp.roi >= self.thresholds['min_roi'] and 
                opp.net_profit >= self.thresholds['min_profit'] and
                opp_data['confidence_score'] >= self.thresholds['min_confidence']):
                
                await self._send_alert(opp, opp_data)
                
                # Track active alerts
                alert_key = self._get_alert_key(opp)
                if alert_key not in self.active_alerts:
                    self.active_alerts[alert_key] = {
                        'first_seen': datetime.utcnow(),
                        'last_alert': datetime.utcnow(),
                        'count': 0,
                        'opportunity': opp
                    }
    
    async def _send_alert(self, opportunity: Any, opp_data: Dict) -> None:
        """Send alerts through all configured channels"""
        message = self._format_alert_message(opportunity, opp_data)
        
        tasks = []
        for notifier_name, notifier in self.notifiers.items():
            tasks.append(notifier.send(message))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to send alert via {list(self.notifiers.keys())[i]}: {result}")
    
    def _format_alert_message(self, opportunity: Any, opp_data: Dict) -> str:
        """Format alert message for display"""
        return f"""
🚀 **Arbitrage Opportunity Alert!**

Type: {opportunity.type.value}
Pair: {opportunity.pair}
Base: {opportunity.base_currency}

💰 Profit: ${opportunity.net_profit:.2f} ({opportunity.roi:.2f}%)
📊 Confidence: {opp_data['confidence_score']:.2%}
📈 ROI: {opportunity.roi:.2f}%
💵 Required Capital: ${opportunity.required_capital:.2f}

🔄 Buy: {opportunity.buy_exchange} @ ${opportunity.buy_price:.4f}
🔄 Sell: {opportunity.sell_exchange} @ ${opportunity.sell_price:.4f}

📊 Available Liquidity: ${opportunity.available_liquidity:.2f}
⏱️ Estimated Execution: {opp_data['estimated_execution_time']:.1f}s

🕐 Found at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
        """
    
    def _get_alert_key(self, opportunity: Any) -> str:
        """Generate unique key for alert deduplication"""
        return f"{opportunity.type}_{opportunity.pair}_{opportunity.buy_exchange}_{opportunity.sell_exchange}"
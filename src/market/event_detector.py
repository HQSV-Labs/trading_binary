"""
事件检测器：自动检测和筛选 BTC/ETH 15分钟涨跌市场
"""
import asyncio
import logging
from typing import List, Optional, Callable
from datetime import datetime, timedelta
from src.market.polymarket_api import PolymarketAPI, Market, OrderBook

logger = logging.getLogger(__name__)


class EventDetector:
    """事件检测器"""
    
    def __init__(self, api: PolymarketAPI):
        self.api = api
        self.detected_markets: List[Market] = []
        self.current_market: Optional[Market] = None
    
    async def detect_btc_eth_markets(self) -> List[Market]:
        """
        检测 BTC/ETH 15分钟涨跌市场
        
        使用 Gamma API (tag_id=102467) 直接获取 BTC/ETH 15分钟市场
        
        Returns:
            检测到的市场列表
        """
        logger.info("开始检测 BTC/ETH 15分钟涨跌市场（使用 Gamma API tag_id=102467）...")
        
        # 使用 Gamma API 搜索市场（tag_id=102467 专门返回 BTC/ETH 15分钟市场）
        all_markets = await self.api.search_markets(
            keywords=None,  # 已废弃，使用 tag_id 筛选
            active=True,
            limit=500  # 获取更多市场以确保能找到活跃的 15分钟市场
        )
        
        # 二次筛选以确保数据正确性（虽然 API 已经筛选过，但保留此步骤以确保数据质量）
        filtered = self.api.find_btc_eth_markets(all_markets)
        
        logger.info(f"从 Gamma API 获取了 {len(all_markets)} 个市场，筛选后剩余 {len(filtered)} 个 BTC/ETH 15分钟市场")
        
        # 按结束时间排序，选择最近的市场
        filtered.sort(key=lambda m: m.end_date or datetime.max, reverse=True)
        
        self.detected_markets = filtered
        
        logger.info(f"检测到 {len(filtered)} 个符合条件的市场")
        for market in filtered[:5]:  # 显示前5个
            logger.info(f"  - {market.question} (ID: {market.market_id})")
        
        return filtered
    
    async def select_active_market(self) -> Optional[Market]:
        """
        选择当前活跃的市场（距离结算时间最近且未结束的）
        
        Returns:
            选中的市场，如果没有则返回 None
        """
        if not self.detected_markets:
            await self.detect_btc_eth_markets()
        
        if not self.detected_markets:
            logger.warning("未找到符合条件的市场")
            return None
        
        # 选择第一个活跃市场
        for market in self.detected_markets:
            if market.is_active:
                self.current_market = market
                logger.info(f"选择市场: {market.question}")
                logger.info(f"市场 ID: {market.market_id}")
                return market
        
        return None
    
    async def monitor_market(
        self,
        market: Market,
        orderbook_callback: Callable[[OrderBook], None],
        update_interval: float = 0.1
    ):
        """
        监控指定市场的订单簿
        
        Args:
            market: 要监控的市场
            orderbook_callback: 订单簿更新回调
            update_interval: 更新间隔（秒）
        """
        logger.info(f"开始监控市场: {market.question}")
        
        # 使用 WebSocket 订阅（如果支持）
        # 否则使用轮询
        try:
            # 尝试 WebSocket 订阅
            await self.api.subscribe_orderbook(
                market.condition_id,
                orderbook_callback
            )
        except Exception as e:
            logger.warning(f"WebSocket 订阅失败，改用轮询: {e}")
            
            # 回退到轮询模式
            while True:
                try:
                    orderbook = await self.api.get_orderbook(market.condition_id)
                    if orderbook:
                        orderbook_callback(orderbook)
                    await asyncio.sleep(update_interval)
                except Exception as e:
                    logger.error(f"轮询订单簿失败: {e}")
                    await asyncio.sleep(1)
    
    def get_market_info(self) -> Optional[dict]:
        """获取当前市场信息"""
        if not self.current_market:
            return None
        
        return {
            "market_id": self.current_market.market_id,
            "question": self.current_market.question,
            "condition_id": self.current_market.condition_id,
            "slug": self.current_market.slug,
            "is_active": self.current_market.is_active
        }


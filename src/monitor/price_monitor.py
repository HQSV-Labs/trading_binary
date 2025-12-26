"""
高频监控模块：监控订单簿价格变化
"""
import asyncio
from typing import Callable, Optional
from src.market.simulator import OrderBook


class PriceMonitor:
    """价格监控器"""
    
    def __init__(
        self,
        entry_price_min: float = 0.35,
        entry_price_max: float = 0.50,
        callback: Optional[Callable] = None
    ):
        """
        初始化监控器
        
        Args:
            entry_price_min: 触发买入的最低价格
            entry_price_max: 触发买入的最高价格
            callback: 价格进入区间时的回调函数
        """
        self.entry_price_min = entry_price_min
        self.entry_price_max = entry_price_max
        self.callback = callback
        self.last_yes_price = 0.5
        self.last_no_price = 0.5
    
    def check_price(self, order_book: OrderBook) -> Optional[str]:
        """
        检查价格是否进入买入区间
        
        Returns:
            如果价格进入区间，返回 "YES" 或 "NO"，否则返回 None
        """
        yes_price = order_book.yes_mid_price
        no_price = order_book.no_mid_price
        
        # 检查 YES 价格
        if self.entry_price_min <= yes_price <= self.entry_price_max:
            if self.last_yes_price < self.entry_price_min or self.last_yes_price > self.entry_price_max:
                # 刚进入区间
                if self.callback:
                    self.callback("YES", yes_price, order_book)
                return "YES"
        
        # 检查 NO 价格
        if self.entry_price_min <= no_price <= self.entry_price_max:
            if self.last_no_price < self.entry_price_min or self.last_no_price > self.entry_price_max:
                # 刚进入区间
                if self.callback:
                    self.callback("NO", no_price, order_book)
                return "NO"
        
        self.last_yes_price = yes_price
        self.last_no_price = no_price
        
        return None


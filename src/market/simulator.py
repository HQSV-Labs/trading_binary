"""
Polymarket 市场模拟器
模拟 BTC/ETH 15分钟预测市场的订单簿和价格波动
"""
import asyncio
import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta


@dataclass
class OrderBookLevel:
    """订单簿层级"""
    price: float
    qty: float


@dataclass
class OrderBook:
    """订单簿"""
    yes_bids: List[OrderBookLevel]  # YES 买单
    yes_asks: List[OrderBookLevel]  # YES 卖单
    no_bids: List[OrderBookLevel]   # NO 买单
    no_asks: List[OrderBookLevel]   # NO 卖单
    
    @property
    def yes_mid_price(self) -> float:
        """YES 中间价"""
        if self.yes_bids and self.yes_asks:
            return (self.yes_bids[0].price + self.yes_asks[0].price) / 2
        return 0.5
    
    @property
    def no_mid_price(self) -> float:
        """NO 中间价"""
        if self.no_bids and self.no_asks:
            return (self.no_bids[0].price + self.no_asks[0].price) / 2
        return 0.5
    
    def get_best_ask(self, side: str) -> Optional[OrderBookLevel]:
        """获取最佳卖价（可以买入的价格）"""
        if side.upper() == "YES":
            return self.yes_asks[0] if self.yes_asks else None
        elif side.upper() == "NO":
            return self.no_asks[0] if self.no_asks else None
        return None


class MarketSimulator:
    """市场模拟器"""
    
    def __init__(self, initial_yes_price: float = 0.5):
        """
        初始化市场模拟器
        
        Args:
            initial_yes_price: 初始 YES 价格（0-1之间）
        """
        self.initial_yes_price = initial_yes_price
        self.current_yes_price = initial_yes_price
        self.order_book = self._generate_orderbook(initial_yes_price)
        self.settlement_time = datetime.now() + timedelta(minutes=15)
        self.is_running = False
        
    def _generate_orderbook(self, yes_price: float) -> OrderBook:
        """生成订单簿"""
        no_price = 1.0 - yes_price
        
        # 生成 YES 订单簿
        yes_bids = []
        yes_asks = []
        spread = 0.01  # 买卖价差
        
        for i in range(5):
            bid_price = yes_price - spread * (i + 1) - 0.01 * i
            ask_price = yes_price + spread * (i + 1) + 0.01 * i
            if bid_price > 0:
                yes_bids.append(OrderBookLevel(bid_price, random.uniform(50, 200)))
            if ask_price < 1:
                yes_asks.append(OrderBookLevel(ask_price, random.uniform(50, 200)))
        
        # 生成 NO 订单簿
        no_bids = []
        no_asks = []
        for i in range(5):
            bid_price = no_price - spread * (i + 1) - 0.01 * i
            ask_price = no_price + spread * (i + 1) + 0.01 * i
            if bid_price > 0:
                no_bids.append(OrderBookLevel(bid_price, random.uniform(50, 200)))
            if ask_price < 1:
                no_asks.append(OrderBookLevel(ask_price, random.uniform(50, 200)))
        
        # 按价格排序
        yes_bids.sort(key=lambda x: x.price, reverse=True)
        yes_asks.sort(key=lambda x: x.price)
        no_bids.sort(key=lambda x: x.price, reverse=True)
        no_asks.sort(key=lambda x: x.price)
        
        return OrderBook(yes_bids, yes_asks, no_bids, no_asks)
    
    def update_price(self, volatility: float = 0.05):
        """
        更新市场价格（模拟市场波动）
        
        Args:
            volatility: 波动率（0-1之间）
        """
        # 随机游走模型
        change = random.gauss(0, volatility * 0.1)
        self.current_yes_price = max(0.1, min(0.9, self.current_yes_price + change))
        
        # 重新生成订单簿
        self.order_book = self._generate_orderbook(self.current_yes_price)
    
    def execute_limit_order(self, side: str, price: float, qty: float) -> Optional[float]:
        """
        执行限价单
        
        Returns:
            实际成交价格，如果无法成交返回 None
        """
        best_ask = self.order_book.get_best_ask(side)
        if best_ask and price >= best_ask.price:
            # 可以成交
            executed_qty = min(qty, best_ask.qty)
            # 更新订单簿
            if side.upper() == "YES":
                if best_ask.qty <= executed_qty:
                    self.order_book.yes_asks.pop(0)
                else:
                    best_ask.qty -= executed_qty
            else:
                if best_ask.qty <= executed_qty:
                    self.order_book.no_asks.pop(0)
                else:
                    best_ask.qty -= executed_qty
            
            return best_ask.price
        return None
    
    def time_to_settlement(self) -> float:
        """距离结算的剩余时间（秒）"""
        remaining = (self.settlement_time - datetime.now()).total_seconds()
        return max(0, remaining)
    
    async def run(self, callback):
        """
        运行市场模拟器，定期更新价格并回调
        
        Args:
            callback: 价格更新回调函数 (order_book) -> None
        """
        self.is_running = True
        while self.is_running and self.time_to_settlement() > 0:
            self.update_price(volatility=0.05)
            await callback(self.order_book)
            await asyncio.sleep(0.1)  # 100ms 更新一次
    
    def stop(self):
        """停止模拟器"""
        self.is_running = False


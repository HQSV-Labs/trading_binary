"""
执行模块：模拟下单和限价单管理
注意：本模块仅进行模拟交易，不会调用真实的 Polymarket API 下单
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum
from datetime import datetime
from src.market.polymarket_api import PolymarketAPI, OrderBook
from src.core.position import PairPosition


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """订单（模拟交易）"""
    side: str  # YES or NO
    price: float
    qty: float
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    filled_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    is_simulated: bool = True  # 标记为模拟交易


class OrderManager:
    """订单管理器（模拟交易模式）"""
    
    def __init__(self, api: PolymarketAPI, condition_id: str, position: PairPosition):
        self.api = api
        self.condition_id = condition_id
        self.position = position
        self.pending_orders: List[Order] = []
        self.filled_orders: List[Order] = []
        self.current_orderbook: Optional[OrderBook] = None
        self.trade_history: List[Order] = []  # 所有交易历史
    
    def update_orderbook(self, orderbook: OrderBook):
        """更新订单簿"""
        self.current_orderbook = orderbook
    
    async def place_limit_order(self, side: str, qty: float, max_price: float) -> Optional[Order]:
        """
        模拟下限价单（不调用真实 API，仅在系统内记录）
        
        Args:
            side: YES or NO
            qty: 数量
            max_price: 最高可接受价格
        
        Returns:
            订单对象
        """
        if not self.current_orderbook:
            # 获取最新订单簿
            self.current_orderbook = await self.api.get_orderbook(self.condition_id)
            if not self.current_orderbook:
                return None
        
        best_ask = self.current_orderbook.get_best_ask(side)
        
        if not best_ask:
            return None
        
        # 计算目标价格：使用最佳卖价（确保能够成交），但不超过 max_price
        # 如果 max_price 小于 best_ask.price，说明价格太高，不应该下单
        if max_price < best_ask.price:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"目标价格 {max_price:.4f} 低于最佳卖价 {best_ask.price:.4f}，无法下单")
            return None
        
        # 使用最佳卖价作为订单价格（确保能够立即成交）
        target_price = best_ask.price
        
        order = Order(side=side, price=target_price, qty=qty, is_simulated=True)
        self.pending_orders.append(order)
        
        # 模拟成交（不调用真实 API）
        await self._try_fill_order(order)
        
        return order
    
    async def _try_fill_order(self, order: Order):
        """
        模拟成交订单（不调用真实 API）
        基于当前订单簿的最佳卖价进行模拟成交
        """
        if order.status != OrderStatus.PENDING:
            return
        
        # 模拟成交逻辑：基于真实订单簿数据，但不实际下单
        if self.current_orderbook:
            best_ask = self.current_orderbook.get_best_ask(order.side)
            if best_ask and order.price >= best_ask.price:
                # 模拟订单成交
                order.status = OrderStatus.FILLED
                order.filled_qty = min(order.qty, best_ask.qty)
                order.filled_price = best_ask.price
                
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"订单成交: {order.side} {order.filled_qty:.2f} @ ${order.filled_price:.4f}")
                
                # 更新持仓（仅在内存中）
                if order.side == "YES":
                    self.position.yes.add_position(order.filled_qty, order.filled_price)
                    logger.info(f"YES 持仓更新: qty={self.position.yes.qty:.2f}, cost={self.position.yes.cost:.2f}, avg={self.position.yes.avg_price:.4f}")
                else:
                    self.position.no.add_position(order.filled_qty, order.filled_price)
                    logger.info(f"NO 持仓更新: qty={self.position.no.qty:.2f}, cost={self.position.no.cost:.2f}, avg={self.position.no.avg_price:.4f}")
                
                # 移动到已成交列表
                if order in self.pending_orders:
                    self.pending_orders.remove(order)
                self.filled_orders.append(order)
                self.trade_history.append(order)  # 添加到交易历史
            else:
                import logging
                logger = logging.getLogger(__name__)
                if best_ask:
                    logger.warning(f"订单无法成交: 订单价格 {order.price:.4f} < 最佳卖价 {best_ask.price:.4f}")
                else:
                    logger.warning(f"订单无法成交: 没有最佳卖价")
    
    async def cancel_all_orders(self):
        """取消所有待成交订单"""
        for order in self.pending_orders:
            order.status = OrderStatus.CANCELLED
        self.pending_orders.clear()
    
    def calculate_target_price(self, side: str, opposite_avg: float) -> float:
        """
        根据准入判定公式反向计算目标买入价
        
        准入条件: new_avg + opposite_avg < 0.98（考虑 Polymarket 2% 手续费）
        所以: new_avg < 0.98 - opposite_avg
        
        对于新持仓: new_avg = price
        对于已有持仓: new_avg = (cost + price * qty) / (qty + new_qty)
        """
        current_pos = self.position.yes if side == "YES" else self.position.no
        max_new_avg = 0.98 - opposite_avg
        
        if current_pos.qty == 0:
            # 新持仓，直接返回
            return max_new_avg
        
        # 已有持仓，需要计算
        # 简化：假设买入后新平均价不超过 max_new_avg
        # 这是一个近似值，实际应该根据要买入的数量计算
        return max_new_avg * 0.95  # 留5%安全边际


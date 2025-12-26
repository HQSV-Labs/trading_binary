"""
核心数学模型：持仓成本跟踪和判定逻辑
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Position:
    """持仓数据结构"""
    qty: float = 0.0  # 持有份额数量
    cost: float = 0.0  # 总支出（美元）
    
    @property
    def avg_price(self) -> float:
        """平均持仓成本"""
        if self.qty == 0:
            return 0.5  # 默认参考价
        return self.cost / self.qty
    
    def add_position(self, qty: float, price: float) -> None:
        """添加持仓"""
        self.cost += price * qty
        self.qty += qty


@dataclass
class PairPosition:
    """双边持仓"""
    yes: Position
    no: Position
    
    def __init__(self):
        self.yes = Position()
        self.no = Position()
    
    @property
    def total_cost(self) -> float:
        """总投入成本"""
        return self.yes.cost + self.no.cost
    
    @property
    def min_qty(self) -> float:
        """最小持仓量（用于利润锁定判定）"""
        return min(self.yes.qty, self.no.qty)
    
    @property
    def pair_cost(self) -> float:
        """配对成本：两边平均价格之和"""
        return self.yes.avg_price + self.no.avg_price
    
    def is_profitable(self) -> bool:
        """
        利润锁定判定：min(Qty_YES, Qty_NO) > (Cost_YES + Cost_NO)
        """
        if self.min_qty == 0:
            return False
        return self.min_qty > self.total_cost
    
    def can_buy(self, side: str, qty: float, price: float) -> bool:
        """
        准入判定公式：
        (Cost_Current + (P × Δq)) / (Qty_Current + Δq) + Avg_Opposite < 0.98
        （考虑 Polymarket 2% 手续费）
        """
        if side.upper() == "YES":
            current_pos = self.yes
            opposite_avg = self.no.avg_price
        elif side.upper() == "NO":
            current_pos = self.no
            opposite_avg = self.yes.avg_price
        else:
            raise ValueError(f"Invalid side: {side}")
        
        # 计算买入后的新平均价
        new_cost = current_pos.cost + (price * qty)
        new_qty = current_pos.qty + qty
        new_avg = new_cost / new_qty if new_qty > 0 else price
        
        # 准入判定（考虑 2% 手续费）
        return (new_avg + opposite_avg) < 0.98
    
    def get_imbalance_ratio(self) -> float:
        """计算持仓不平衡比例"""
        total = self.yes.qty + self.no.qty
        if total == 0:
            return 0.0
        return abs(self.yes.qty - self.no.qty) / total
    
    def get_target_side(self) -> Optional[str]:
        """根据不平衡情况返回应该优先买入的方向"""
        if self.yes.qty > self.no.qty * 1.2:
            return "NO"
        elif self.no.qty > self.yes.qty * 1.2:
            return "YES"
        return None


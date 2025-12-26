"""
动态平衡模块：保持 YES/NO 持仓平衡
"""
from src.core.position import PairPosition


class Rebalancer:
    """持仓平衡器"""
    
    def __init__(self, imbalance_threshold: float = 0.2):
        """
        初始化平衡器
        
        Args:
            imbalance_threshold: 不平衡阈值（20%）
        """
        self.imbalance_threshold = imbalance_threshold
    
    def should_rebalance(self, position: PairPosition) -> bool:
        """判断是否需要重新平衡"""
        return position.get_imbalance_ratio() > self.imbalance_threshold
    
    def get_priority_side(self, position: PairPosition) -> str:
        """
        获取应该优先买入的方向
        
        Returns:
            "YES" 或 "NO"
        """
        target_side = position.get_target_side()
        if target_side:
            return target_side
        
        # 如果基本平衡，返回持仓较少的一边
        if position.yes.qty < position.no.qty:
            return "YES"
        return "NO"


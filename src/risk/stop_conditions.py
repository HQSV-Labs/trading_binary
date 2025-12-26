"""
风险控制模块：单边持仓和异常情况的终止条件
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta, timezone
from src.core.position import PairPosition
from src.market.polymarket_api import OrderBook


@dataclass
class StopConditionResult:
    """终止条件检查结果"""
    should_stop: bool
    reason: str
    details: dict


class RiskController:
    """风险控制器"""
    
    def __init__(
        self,
        max_total_capital: float = 1000.0,
        max_pos_per_window: float = 200.0,
        max_unhedged_seconds: int = 120,
        max_pair_cost: float = 0.98,  # 考虑 Polymarket 2% 手续费
        max_loss_ratio: float = 0.1,  # 最大亏损比例 10%
        settlement_buffer_seconds: int = 60,
        pair_cost_check_delay_seconds: int = 60  # 配对成本检查延迟（秒），避免交易早期过于敏感
    ):
        """
        初始化风险控制器
        
        Args:
            max_total_capital: 最大总资金
            max_pos_per_window: 单个窗口最大持仓成本
            max_unhedged_seconds: 单边持仓最大滞留时间（秒）
            max_pair_cost: 最大允许配对成本（超过此值停止交易）
            max_loss_ratio: 最大亏损比例（当前市值/成本 < 1 - max_loss_ratio 时停止）
            settlement_buffer_seconds: 结算前缓冲时间（秒）
            pair_cost_check_delay_seconds: 配对成本检查延迟（秒），单边持仓超过此时间后才检查配对成本
        """
        self.max_total_capital = max_total_capital
        self.max_pos_per_window = max_pos_per_window
        self.max_unhedged_seconds = max_unhedged_seconds
        self.max_pair_cost = max_pair_cost
        self.max_loss_ratio = max_loss_ratio
        self.settlement_buffer_seconds = settlement_buffer_seconds
        self.pair_cost_check_delay_seconds = pair_cost_check_delay_seconds
        
        # 记录单边持仓开始时间
        self.unhedged_start_time: Optional[datetime] = None
        self.last_unhedged_side: Optional[str] = None
    
    def check_stop_conditions(
        self,
        position: PairPosition,
        orderbook: Optional[OrderBook],
        market_end_time: Optional[datetime] = None
    ) -> StopConditionResult:
        """
        检查所有终止条件
        
        Returns:
            StopConditionResult: 是否应该停止交易及原因
        """
        # 1. 检查利润锁定（双边持仓且已盈利）
        if position.is_profitable():
            return StopConditionResult(
                should_stop=True,
                reason="✅ 已锁定利润，停止交易",
                details={
                    "type": "profit_locked",
                    "min_qty": position.min_qty,
                    "total_cost": position.total_cost,
                    "profit": position.min_qty - position.total_cost
                }
            )
        
        # 2. 检查单边持仓情况
        has_yes = position.yes.qty > 0
        has_no = position.no.qty > 0
        is_unhedged = (has_yes and not has_no) or (has_no and not has_yes)
        
        if is_unhedged:
            # 更新单边持仓时间
            current_side = "YES" if has_yes else "NO"
            if self.last_unhedged_side != current_side:
                # 切换了单边持仓方向，重置时间
                self.unhedged_start_time = datetime.now(timezone.utc)
                self.last_unhedged_side = current_side
            elif self.unhedged_start_time is None:
                self.unhedged_start_time = datetime.now(timezone.utc)
            
            # 2.1 检查单边持仓时间过长
            if self.unhedged_start_time:
                unhedged_duration = (datetime.now(timezone.utc) - self.unhedged_start_time).total_seconds()
                if unhedged_duration > self.max_unhedged_seconds:
                    return StopConditionResult(
                        should_stop=True,
                        reason=f"⚠️ 单边持仓时间过长（{int(unhedged_duration)}秒 > {self.max_unhedged_seconds}秒），停止交易",
                        details={
                            "type": "unhedged_timeout",
                            "side": current_side,
                            "duration_seconds": unhedged_duration,
                            "max_allowed": self.max_unhedged_seconds
                        }
                    )
            
            # 2.2 单边持仓时不检查配对成本
            # 原因：单边持仓时，配对成本 = 持仓平均价 + 市场中间价
            # 市场中间价可能虚高，不代表实际能买到的价格，因此不应该基于此停止交易
            # 配对成本检查只在双边持仓时进行（见下面的 2.2.1）
            
            # 2.3 单边持仓时不检查单边亏损
            # 原因：这是对冲套利策略，单边持仓只是临时状态，目标是尽快完成对冲
            # 单边价格短期波动（甚至亏损>10%）是正常的，不应该触发止损
            # 如果因为单边亏损就停止交易，会导致：
            #   - 无法完成对冲配对
            #   - 真正承担了单边风险（这才是最大的风险）
            # 正确的风控逻辑是：
            #   1. 限制单边持仓时间（上面的 2.1）- 如果长时间无法对冲，说明市场有问题
            #   2. 双边持仓后检查总体配对成本（下面的 2.2.1）- 确保对冲后的总成本合理
            # 
            # 注意：单边亏损止损已被移除，因为它违背了对冲套利的核心逻辑
            pass
        else:
            # 双边持仓或空仓，重置单边持仓时间
            self.unhedged_start_time = None
            self.last_unhedged_side = None
            
            # 2.2.1 双边持仓时检查配对成本（使用实际持仓平均价）
            # 这是真实的建仓成本，应该严格检查
            if orderbook and has_yes and has_no:
                pair_cost = position.yes.avg_price + position.no.avg_price
                
                if pair_cost > self.max_pair_cost:
                    return StopConditionResult(
                        should_stop=True,
                        reason=f"⚠️ 配对成本过高（${pair_cost:.4f} > ${self.max_pair_cost:.4f}），双边持仓无法盈利，停止交易",
                        details={
                            "type": "pair_cost_too_high",
                            "pair_cost": pair_cost,
                            "max_allowed": self.max_pair_cost,
                            "yes_avg": position.yes.avg_price,
                            "no_avg": position.no.avg_price,
                            "is_hedged": True
                        }
                    )
        
        # 3. 检查总资金限制
        if position.total_cost > self.max_total_capital:
            return StopConditionResult(
                should_stop=True,
                reason=f"⚠️ 总投入资金超过限制（${position.total_cost:.2f} > ${self.max_total_capital:.2f}），停止交易",
                details={
                    "type": "max_capital_exceeded",
                    "total_cost": position.total_cost,
                    "max_allowed": self.max_total_capital
                }
            )
        
        # 4. 检查单个窗口持仓限制（分别检查 YES 和 NO）
        # 对于对冲套利策略，每边应该有独立的限制
        # 例如：YES 最多 $300，NO 最多 $300，总共可以 $600
        if position.yes.cost > self.max_pos_per_window:
            return StopConditionResult(
                should_stop=True,
                reason=f"⚠️ YES 持仓成本超过限制（${position.yes.cost:.2f} > ${self.max_pos_per_window:.2f}），停止交易",
                details={
                    "type": "max_pos_exceeded",
                    "side": "YES",
                    "cost": position.yes.cost,
                    "max_allowed": self.max_pos_per_window
                }
            )
        
        if position.no.cost > self.max_pos_per_window:
            return StopConditionResult(
                should_stop=True,
                reason=f"⚠️ NO 持仓成本超过限制（${position.no.cost:.2f} > ${self.max_pos_per_window:.2f}），停止交易",
                details={
                    "type": "max_pos_exceeded",
                    "side": "NO",
                    "cost": position.no.cost,
                    "max_allowed": self.max_pos_per_window
                }
            )
        
        # 5. 检查结算时间
        if market_end_time:
            # 确保 market_end_time 是 aware 的，如果是 naive 则假设为 UTC
            if market_end_time.tzinfo is None:
                market_end_time = market_end_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            time_to_settlement = (market_end_time - now).total_seconds()
            if time_to_settlement <= self.settlement_buffer_seconds:
                return StopConditionResult(
                    should_stop=True,
                    reason=f"⚠️ 接近结算时间（剩余 {int(time_to_settlement)}秒 < {self.settlement_buffer_seconds}秒），停止交易",
                    details={
                        "type": "settlement_time_near",
                        "time_to_settlement": time_to_settlement,
                        "buffer_seconds": self.settlement_buffer_seconds
                    }
                )
        
        # 所有检查通过，可以继续交易
        return StopConditionResult(
            should_stop=False,
            reason="✅ 所有风险检查通过，可以继续交易",
            details={}
        )
    
    def reset(self):
        """重置风险控制器状态"""
        self.unhedged_start_time = None
        self.last_unhedged_side = None


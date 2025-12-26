"""
配置文件
"""
import os
from typing import Optional


class Config:
    """配置类"""
    
    # Polymarket API 配置（可选，读取公开数据不需要 API key）
    # API key 仅用于未来可能的真实交易功能，当前模拟模式不需要
    POLYMARKET_API_KEY: Optional[str] = os.getenv("POLYMARKET_API_KEY", None)
    
    # 交易参数
    ENTRY_PRICE_MIN: float = 0.35
    ENTRY_PRICE_MAX: float = 0.50
    DEFAULT_ORDER_SIZE: float = 100.0
    REBALANCE_ORDER_SIZE: float = 50.0
    IMBALANCE_THRESHOLD: float = 0.2
    
    # 安全参数
    SETTLEMENT_BUFFER_SECONDS: int = 60  # 结算前60秒停止交易
    
    # 风控参数
    MAX_TOTAL_CAPITAL: float = 1000.0  # 账户最大允许动用的总资金（USD）
    MAX_POS_PER_WINDOW: float = 300.0  # 单个 15 分钟合约窗口的最大持仓成本上限 - 这是单边（YES 或 NO）的限制，总共可以 YES $300 + NO $300 = $600
    MIN_EXPECTED_ROI: float = 0.02  # 最小利润率 (2%)，即配对成本必须 <= 0.98
    MAX_DELTA_RATIO: float = 0.20  # 最大允许单边敞口比例 (20%)
    MAX_SLIPPAGE: float = 0.01  # 订单价格相对于盘口的最大允许滑点 (1%)
    LOCK_WINDOW_SEC: int = 180  # 结算前最后 N 秒，进入"只减仓"模式
    MAX_UNHEDGED_SEC: int = 120  # 单边敞口最大滞留时间，超时强制停止
    MAX_PAIR_COST: float = 0.98  # 最大允许配对成本（超过此值停止交易，考虑 Polymarket 2% 手续费）
    MAX_LOSS_RATIO: float = 0.1  # 最大亏损比例（10%），当前市值/成本 < 0.9 时停止
    PAIR_COST_CHECK_DELAY_SECONDS: int = 60  # 配对成本检查延迟（秒），单边持仓超过此时间后才检查配对成本，避免交易早期过于敏感
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


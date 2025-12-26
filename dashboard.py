"""
Streamlit Dashboard - 15分钟预测市场双边对冲套利可视化界面
"""
import streamlit as st
import asyncio
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, timezone
import time
from typing import Optional

# 尝试导入 nest_asyncio 以支持在 Streamlit 中使用 asyncio
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# 创建一个辅助函数来安全地运行异步代码
def run_async(coro):
    """在 Streamlit 中安全地运行异步函数"""
    # 使用 nest_asyncio 允许嵌套事件循环
    # 这样可以避免与 Streamlit 的内部事件循环冲突
    
    # 确保 nest_asyncio 已应用
    try:
        import nest_asyncio
        if not hasattr(asyncio, '_nest_patched'):
            nest_asyncio.apply()
    except ImportError:
        pass
    
    # 检查是否有正在运行的事件循环
    try:
        # 尝试获取正在运行的循环
        loop = asyncio.get_running_loop()
        # 如果有正在运行的循环，nest_asyncio 应该允许我们嵌套运行
        # 但为了安全，我们仍然在新线程中运行
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_in_new_loop, coro)
            return future.result(timeout=30)  # 30秒超时
    except RuntimeError:
        # 没有正在运行的循环，可以安全地创建新的
        return _run_in_new_loop(coro)


def _run_in_new_loop(coro):
    """在新的事件循环中运行协程"""
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 包装协程为 task，以支持 asyncio.timeout()（Python 3.11+ 需要 task 上下文）
        async def run_in_task():
            task = asyncio.create_task(coro)
            return await task
        
        return loop.run_until_complete(run_in_task())
    finally:
        # 清理：关闭事件循环并移除
        try:
            # 取消所有未完成的任务
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            
            # 等待任务取消完成
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        
        # 关闭事件循环
        try:
            loop.close()
        except Exception:
            pass
        
        # 移除事件循环引用，避免与 Streamlit 冲突
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass

from config import Config
from src.core.position import PairPosition
from src.market.polymarket_api import PolymarketAPI, OrderBook
from src.market.event_detector import EventDetector
from src.market.demo_data import create_demo_markets, create_demo_orderbook, update_demo_orderbook
from src.monitor.price_monitor import PriceMonitor
from src.execution.order_manager import OrderManager
from src.rebalancing.balancer import Rebalancer
from src.risk.stop_conditions import RiskController, StopConditionResult


# 页面配置
st.set_page_config(
    page_title="15分钟预测市场套利 Bot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS - 改进配色方案
st.markdown("""
<style>
    /* 主标题 */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #0d6efd;
        text-align: center;
        padding: 1rem 0;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    
    /* 指标卡片背景 */
    .stMetric {
        background-color: #ffffff;
        padding: 1.2rem;
        border-radius: 12px;
        border: 2px solid #e9ecef;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* 指标标签 */
    .stMetric label {
        color: #495057 !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }
    
    /* 指标值 */
    .stMetric [data-testid="stMetricValue"] {
        color: #212529 !important;
        font-weight: 700 !important;
        font-size: 1.5rem !important;
    }
    
    /* 指标变化 */
    .stMetric [data-testid="stMetricDelta"] {
        font-weight: 600 !important;
    }
    
    /* 面板标题 */
    h2, h3 {
        color: #212529 !important;
        font-weight: 700 !important;
    }
    
    /* 表格样式 */
    .stDataFrame {
        background-color: #ffffff !important;
        border-radius: 8px;
    }
    
    /* 按钮样式 */
    .stButton > button {
        background-color: #0d6efd;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1.5rem;
    }
    
    .stButton > button:hover {
        background-color: #0b5ed7;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    /* 侧边栏 */
    .css-1d391kg {
        background-color: #f8f9fa;
    }
    
    /* 主内容区背景 */
    .main .block-container {
        background-color: #ffffff;
        padding: 2rem;
    }
    
    /* 信息框 */
    .stInfo {
        background-color: #d1ecf1;
        border-left: 4px solid #0dcaf0;
    }
    
    /* 成功消息 */
    .stSuccess {
        background-color: #d1e7dd;
        border-left: 4px solid #198754;
    }
    
    /* 警告消息 */
    .stWarning {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
    }
    
    /* 错误消息 */
    .stError {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
    }
    
    /* 选择框 */
    .stSelectbox label {
        color: #212529 !important;
        font-weight: 600 !important;
    }
    
    /* 复选框 */
    .stCheckbox label {
        color: #212529 !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)


# 初始化 session state
if 'position' not in st.session_state:
    st.session_state.position = PairPosition()
if 'order_manager' not in st.session_state:
    st.session_state.order_manager = None
if 'current_market' not in st.session_state:
    st.session_state.current_market = None
if 'price_history' not in st.session_state:
    st.session_state.price_history = []
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'demo_mode' not in st.session_state:
    st.session_state.demo_mode = False
if 'api' not in st.session_state:
    st.session_state.api = PolymarketAPI(api_key=Config.POLYMARKET_API_KEY)
if 'event_detector' not in st.session_state:
    st.session_state.event_detector = EventDetector(st.session_state.api)
if 'auto_trading_enabled' not in st.session_state:
    st.session_state.auto_trading_enabled = True
if 'last_auto_trade_check' not in st.session_state:
    st.session_state.last_auto_trade_check = {}
if 'pending_refresh' not in st.session_state:
    st.session_state.pending_refresh = False
if 'buy_reasons' not in st.session_state:
    st.session_state.buy_reasons = {"YES": None, "NO": None}
if 'risk_controller' not in st.session_state:
    st.session_state.risk_controller = RiskController(
        max_total_capital=Config.MAX_TOTAL_CAPITAL,
        max_pos_per_window=Config.MAX_POS_PER_WINDOW,
        max_unhedged_seconds=Config.MAX_UNHEDGED_SEC,
        max_pair_cost=Config.MAX_PAIR_COST,
        max_loss_ratio=Config.MAX_LOSS_RATIO,
        settlement_buffer_seconds=Config.SETTLEMENT_BUFFER_SECONDS,
        pair_cost_check_delay_seconds=Config.PAIR_COST_CHECK_DELAY_SECONDS
    )
if 'stop_condition_result' not in st.session_state:
    st.session_state.stop_condition_result = None


def get_orderbook_data(orderbook: OrderBook) -> dict:
    """从订单簿提取数据"""
    return {
        "timestamp": datetime.now(),
        "yes_mid": orderbook.yes_mid_price,
        "no_mid": orderbook.no_mid_price,
        "yes_best_bid": orderbook.yes_bids[0].price if orderbook.yes_bids else 0,
        "yes_best_ask": orderbook.yes_asks[0].price if orderbook.yes_asks else 0,
        "no_best_bid": orderbook.no_bids[0].price if orderbook.no_bids else 0,
        "no_best_ask": orderbook.no_asks[0].price if orderbook.no_asks else 0,
    }


def check_buy_conditions(side: str, price: float, position: PairPosition, order_manager, 
                         orderbook: OrderBook, auto_trading_enabled: bool, 
                         last_check_time: Optional[datetime] = None) -> dict:
    """
    检查买入条件并返回详细原因
    
    Returns:
        dict: {
            "can_buy": bool,
            "reason": str,  # 如果不能买入，说明原因
            "details": dict  # 详细信息
        }
    """
    result = {
        "can_buy": False,
        "reason": "",
        "details": {}
    }
    
    # 1. 检查自动交易是否启用
    if not auto_trading_enabled:
        result["reason"] = "❌ 自动交易未启用"
        result["details"]["auto_trading"] = False
        return result
    result["details"]["auto_trading"] = True
    
    # 2. 检查价格是否在买入区间（分初始建仓和平衡持仓两种情况）
    # 对于对冲套利策略：
    # - 初始建仓（空仓或单边）：要求价格在 0.35-0.50 区间
    # - 已有双边持仓后：优先平衡持仓，不限制价格区间（只要配对成本 < 0.98）
    
    has_yes = position.yes.qty > 0
    has_no = position.no.qty > 0
    is_empty = not has_yes and not has_no
    is_unhedged = (has_yes and not has_no) or (has_no and not has_yes)
    is_hedged = has_yes and has_no
    
    # 初始建仓阶段：空仓或单边持仓时，必须价格在区间内
    if is_empty or is_unhedged:
        if not (Config.ENTRY_PRICE_MIN <= price <= Config.ENTRY_PRICE_MAX):
            result["reason"] = f"❌ 初始建仓：价格不在区间 (${Config.ENTRY_PRICE_MIN:.2f} - ${Config.ENTRY_PRICE_MAX:.2f})"
            result["details"]["price_in_range"] = False
            result["details"]["current_price"] = price
            result["details"]["stage"] = "initial" if is_empty else "unhedged"
            return result
    
    # 已有双边持仓：优先买入持仓少的那边，不限制价格区间
    if is_hedged:
        # 检查是否应该优先买另一边（持仓不平衡）
        imbalance_ratio = position.get_imbalance_ratio()
        target_side = position.get_target_side()
        
        if target_side and target_side != side:
            # 应该优先买另一边，而不是当前这边
            result["reason"] = f"❌ 持仓不平衡：应优先买入 {target_side}（不平衡率 {imbalance_ratio*100:.1f}%）"
            result["details"]["should_buy_other_side"] = True
            result["details"]["target_side"] = target_side
            result["details"]["imbalance_ratio"] = imbalance_ratio
            result["details"]["yes_qty"] = position.yes.qty
            result["details"]["no_qty"] = position.no.qty
            return result
    
    result["details"]["price_in_range"] = True
    result["details"]["current_price"] = price
    result["details"]["stage"] = "hedged" if is_hedged else ("unhedged" if is_unhedged else "initial")
    
    # 3. 检查防重复下单（5秒内）
    if last_check_time:
        time_diff = (datetime.now() - last_check_time).total_seconds()
        if time_diff <= 5:
            result["reason"] = f"⏳ 防重复下单：{5 - int(time_diff)}秒前已检查过此价格"
            result["details"]["cooldown"] = True
            result["details"]["time_remaining"] = 5 - time_diff
            return result
    result["details"]["cooldown"] = False
    
    # 4. 检查是否已锁定利润
    if position.is_profitable():
        result["reason"] = "✅ 已锁定利润，停止交易"
        result["details"]["profit_locked"] = True
        result["details"]["min_qty"] = position.min_qty
        result["details"]["total_cost"] = position.total_cost
        return result
    result["details"]["profit_locked"] = False
    
    # 5. 检查订单管理器是否存在
    if not order_manager:
        result["reason"] = "❌ 订单管理器未初始化"
        result["details"]["order_manager"] = False
        return result
    result["details"]["order_manager"] = True
    
    # 6. 检查订单簿是否有最佳卖价
    best_ask = orderbook.get_best_ask(side)
    if not best_ask:
        result["reason"] = "❌ 订单簿中没有最佳卖价（市场可能没有流动性）"
        result["details"]["best_ask"] = None
        return result
    result["details"]["best_ask"] = best_ask.price
    result["details"]["best_ask_qty"] = best_ask.qty
    
    # 7. 检查准入条件
    qty = Config.DEFAULT_ORDER_SIZE
    if not position.can_buy(side, qty, price):
        opposite_side = "NO" if side == "YES" else "YES"
        current_pos = position.yes if side == "YES" else position.no
        opposite_pos = position.no if side == "YES" else position.yes
        
        # 计算买入后的新平均价
        new_cost = current_pos.cost + (price * qty)
        new_qty = current_pos.qty + qty
        new_avg = new_cost / new_qty if new_qty > 0 else price
        
        # 计算配对成本：如果对方没有持仓，使用当前市场价格
        if opposite_pos.qty > 0:
            opposite_avg = opposite_pos.avg_price
        else:
            # 使用当前订单簿的市场价格
            opposite_mid_price = orderbook.no_mid_price if opposite_side == "NO" else orderbook.yes_mid_price
            opposite_avg = opposite_mid_price
        
        pair_cost_after = new_avg + opposite_avg
        
        # 计算当前配对成本（同样使用市场价格）
        current_yes_avg = position.yes.avg_price if position.yes.qty > 0 else orderbook.yes_mid_price
        current_no_avg = position.no.avg_price if position.no.qty > 0 else orderbook.no_mid_price
        current_pair_cost = current_yes_avg + current_no_avg
        
        result["reason"] = f"❌ 不满足准入条件：买入后配对成本 ${pair_cost_after:.4f} >= $0.98（考虑 2% 手续费）"
        result["details"]["can_buy"] = False
        result["details"]["current_pair_cost"] = current_pair_cost
        result["details"]["pair_cost_after"] = pair_cost_after
        result["details"]["current_avg"] = current_pos.avg_price
        result["details"]["opposite_avg"] = opposite_avg
        result["details"]["new_avg_after"] = new_avg
        return result
    result["details"]["can_buy"] = True
    
    # 8. 检查目标价格
    opposite_side = "NO" if side == "YES" else "YES"
    opposite_avg = getattr(position, opposite_side.lower()).avg_price
    target_price = order_manager.calculate_target_price(side, opposite_avg)
    
    if target_price < best_ask.price:
        result["reason"] = f"❌ 目标价格 ${target_price:.4f} 低于最佳卖价 ${best_ask.price:.4f}，无法成交"
        result["details"]["target_price"] = target_price
        result["details"]["best_ask_price"] = best_ask.price
        result["details"]["price_diff"] = best_ask.price - target_price
        return result
    result["details"]["target_price"] = target_price
    
    # 所有条件都满足
    result["can_buy"] = True
    result["reason"] = "✅ 所有条件满足，可以买入"
    result["details"]["qty"] = qty
    result["details"]["target_price"] = target_price
    
    return result


def create_price_chart(price_history: list) -> go.Figure:
    """创建价格趋势图 - 改进配色"""
    if not price_history:
        fig = go.Figure()
        fig.add_annotation(
            text="等待数据...", 
            xref="paper", 
            yref="paper", 
            x=0.5, 
            y=0.5, 
            showarrow=False,
            font=dict(size=20, color="#495057")
        )
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig
    
    df = pd.DataFrame(price_history)
    
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('🟢 YES 价格趋势', '🔴 NO 价格趋势'),
        vertical_spacing=0.12,
        row_heights=[0.5, 0.5]
    )
    
    # YES 价格 - 使用更鲜明的绿色
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['yes_mid'],
            mode='lines+markers',
            name='YES',
            line=dict(color='#28a745', width=3),
            marker=dict(size=6, color='#28a745'),
            fill='tonexty',
            fillcolor='rgba(40, 167, 69, 0.1)'
        ),
        row=1, col=1
    )
    
    # NO 价格 - 使用更鲜明的红色
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['no_mid'],
            mode='lines+markers',
            name='NO',
            line=dict(color='#dc3545', width=3),
            marker=dict(size=6, color='#dc3545'),
            fill='tonexty',
            fillcolor='rgba(220, 53, 69, 0.1)'
        ),
        row=2, col=1
    )
    
    # 添加买入区间线 - 使用更明显的颜色
    for row in [1, 2]:
        fig.add_hline(
            y=Config.ENTRY_PRICE_MIN, 
            line_dash="dash", 
            line_color="#0d6efd", 
            line_width=2,
            annotation_text=f"买入下限 ${Config.ENTRY_PRICE_MIN:.2f}", 
            annotation_position="right",
            row=row, 
            col=1
        )
        fig.add_hline(
            y=Config.ENTRY_PRICE_MAX, 
            line_dash="dash", 
            line_color="#0d6efd",
            line_width=2,
            annotation_text=f"买入上限 ${Config.ENTRY_PRICE_MAX:.2f}",
            annotation_position="right",
            row=row, 
            col=1
        )
    
    fig.update_layout(
        height=600,
        showlegend=True,
        hovermode='x unified',
        template='plotly_white',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(size=12, color='#212529'),
        title_font=dict(size=16, color='#212529')
    )
    
    fig.update_xaxes(
        title_text="时间", 
        row=2, 
        col=1,
        title_font=dict(size=12, color='#495057'),
        gridcolor='#e9ecef'
    )
    fig.update_yaxes(
        title_text="价格 ($)", 
        row=1, 
        col=1,
        title_font=dict(size=12, color='#495057'),
        gridcolor='#e9ecef'
    )
    fig.update_yaxes(
        title_text="价格 ($)", 
        row=2, 
        col=1,
        title_font=dict(size=12, color='#495057'),
        gridcolor='#e9ecef'
    )
    
    return fig


def main():
    # 确保 check_buy_conditions 函数可用
    if 'check_buy_conditions' not in globals():
        st.error("❌ 错误: check_buy_conditions 函数未定义。请清除 Streamlit 缓存并重新启动。")
        st.stop()
    
    # 标题
    st.markdown('<h1 class="main-header">📊 15分钟预测市场双边对冲套利 Bot</h1>', unsafe_allow_html=True)
    
    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 设置")
        
        # 演示模式开关
        demo_mode = st.checkbox("演示模式", value=st.session_state.demo_mode, 
                               help="使用模拟数据展示界面")
        st.session_state.demo_mode = demo_mode
        
        # 市场选择
        st.header("📈 市场选择")
        
        # 手动输入市场 ID 或 Slug
        st.markdown("**方式1: 手动输入市场**")
        st.markdown("💡 **提示**: 如果找不到市场，可能是市场已过期。请尝试:")
        st.markdown("- 使用最新的 15 分钟市场 URL")
        st.markdown("- 或者直接输入 Condition ID (0x 开头的 16 进制)")
        
        market_input = st.text_input(
            "输入市场 Slug、URL 或 Condition ID",
            placeholder="例如: btc-updown-15m-1766509200 或 0x...",
            help="从 Polymarket URL 中获取，如: https://polymarket.com/event/btc-updown-15m-1766509200"
        )
        
        if market_input and st.button("✅ 使用此市场", type="primary"):
            # 清理输入：从 URL 中提取 slug
            import re
            # 移除 URL 前缀
            clean_input = market_input.strip()
            if "polymarket.com" in clean_input:
                # 从 URL 中提取 slug
                match = re.search(r'/event/([^/?]+)', clean_input)
                if match:
                    clean_input = match.group(1)
                else:
                    # 尝试从路径中提取
                    clean_input = clean_input.split("/")[-1].split("?")[0]
            else:
                # 移除查询参数
                clean_input = clean_input.split("?")[0].strip("/")
            
            # 尝试通过 API 查找市场信息
            from src.market.polymarket_api import Market
            try:
                with st.spinner("正在查找市场..."):
                    # 优先策略：如果输入的是 condition_id (0x 开头)，直接使用
                    if clean_input.startswith("0x"):
                        # 直接使用 condition_id 创建市场对象
                        temp_market = Market(
                            market_id=clean_input,
                            question=f"市场 (Condition ID: {clean_input[:20]}...)",
                            condition_id=clean_input,
                            slug=clean_input,
                            is_active=True
                        )
                        st.session_state.current_market = temp_market
                        # 初始化订单管理器
                        st.session_state.order_manager = OrderManager(
                            st.session_state.api,
                            clean_input,
                            st.session_state.position
                        )
                        st.success(f"✅ 使用 Condition ID: {clean_input}")
                        st.rerun()
                    
                    # 策略1：直接通过 slug 获取市场信息（最快，不需要搜索所有市场）
                    try:
                        market_info = run_async(
                            st.session_state.api.get_market_info_by_slug(clean_input)
                        )
                        if market_info and market_info.get("conditionId"):
                            condition_id = market_info["conditionId"]
                            question = market_info.get("question", f"市场 - {clean_input}")
                            slug = market_info.get("slug", clean_input)
                            
                            # 解析 end_date（如果需要）
                            end_date = None
                            # 注意：get_market_info_by_slug 目前不返回 end_date
                            # 如果需要，可以从 events API 中获取
                            
                            temp_market = Market(
                                market_id=condition_id,
                                question=question,
                                condition_id=condition_id,
                                slug=slug,
                                is_active=market_info.get("active", True),
                                end_date=end_date
                            )
                            st.session_state.current_market = temp_market
                            # 初始化订单管理器
                            st.session_state.order_manager = OrderManager(
                                st.session_state.api,
                                condition_id,
                                st.session_state.position
                            )
                            st.success(f"✅ 找到市场: {question}")
                            st.info(f"Condition ID: {condition_id}")
                            st.rerun()
                    except Exception as e1:
                        # 直接通过 slug 获取失败，继续尝试其他方法
                        # 不显示错误，因为这是正常的 fallback 流程
                        pass
                    
                    # 策略2：如果直接获取失败，尝试从订单簿中提取（fallback）
                    st.info("🔍 尝试从订单簿中提取市场信息...")
                    try:
                        # 尝试获取订单簿（会自动从网页提取 condition_id）
                        test_orderbook = run_async(
                            st.session_state.api.get_orderbook(clean_input)
                        )
                        if test_orderbook:
                            # 如果能获取到订单簿，说明找到了 condition_id
                            # 创建一个临时市场对象
                            temp_market = Market(
                                market_id=clean_input,
                                question=f"BTC/ETH 15分钟市场 - {clean_input}",
                                condition_id=clean_input,
                                slug=clean_input,
                                is_active=True
                            )
                            st.session_state.current_market = temp_market
                            # 初始化订单管理器
                            st.session_state.order_manager = OrderManager(
                                st.session_state.api,
                                clean_input,
                                st.session_state.position
                            )
                            st.success(f"✅ 从订单簿提取到市场信息，可以使用")
                            st.rerun()
                        else:
                            st.error(f"❌ 无法获取市场数据: {clean_input}")
                            st.warning("⚠️ **可能的原因**:")
                            st.markdown("1. **市场已关闭**：15 分钟市场在时间结束后会关闭，无法获取订单簿")
                            st.markdown("2. **市场不在 API 列表中**：某些短期市场可能不在公共 API 返回列表中")
                            st.markdown("3. **输入的市场 slug 不正确**")
                            st.info("💡 **解决方案**:")
                            st.markdown("- ✅ **使用最新的活跃市场**：访问 [Polymarket 15分钟市场页面](https://polymarket.com/crypto/15M) 获取最新的市场")
                            st.markdown("- ✅ **使用演示模式**：在侧边栏启用演示模式进行测试")
                            st.markdown("- ✅ **直接输入 Condition ID**：如果知道 condition_id (0x 开头)，可以直接输入")
                    except Exception as e2:
                        st.error(f"从订单簿提取失败: {e2}")
                        import traceback
                        st.code(traceback.format_exc())
                        st.info("💡 请尝试:")
                        st.markdown("- 使用最新的活跃市场（访问 https://polymarket.com/crypto/15M）")
                        st.markdown("- 或使用演示模式进行测试")
            except Exception as e:
                st.error(f"查找市场失败: {e}")
                import traceback
                st.code(traceback.format_exc())
        
        st.divider()
        
        st.markdown("**方式2: 搜索市场**")
        st.markdown("⚠️ **注意**: 搜索市场会调用 API 获取所有市场列表，如果网络不稳定可能会失败。")
        st.markdown("💡 **建议**: 优先使用方式1手动输入市场 slug 或 condition_id，更快更可靠。")
        if st.button("🔍 搜索市场", type="primary"):
            with st.spinner("正在搜索市场..."):
                if demo_mode:
                    markets = create_demo_markets()
                else:
                    try:
                        # 使用同步方式调用异步函数
                        # 注意：这会调用 search_markets() API，如果网络不稳定可能会失败
                        markets = run_async(
                            st.session_state.event_detector.detect_btc_eth_markets()
                        )
                    except Exception as e:
                        st.error(f"❌ API 无法访问: {e}")
                        st.warning("⚠️ **搜索市场失败**")
                        st.info("💡 **建议**:")
                        st.markdown("- ✅ **使用方式1手动输入**：直接输入市场 slug 或 condition_id，不需要搜索所有市场")
                        st.markdown("- ✅ **启用演示模式**：在侧边栏启用演示模式进行测试")
                        st.markdown("- ✅ **检查网络连接**：确保可以访问 gamma-api.polymarket.com")
                        markets = []
                
                if markets:
                    st.session_state.markets_list = markets
                    st.success(f"找到 {len(markets)} 个市场")
                    
                    # 如果没有选择市场，自动选择第一个
                    if not st.session_state.current_market and markets:
                        st.session_state.current_market = markets[0]
                        st.session_state.order_manager = OrderManager(
                            st.session_state.api,
                            st.session_state.current_market.condition_id,
                            st.session_state.position
                        )
                        st.rerun()
                else:
                    st.warning("未找到市场")
        
        # 显示市场选择下拉框
        if 'markets_list' in st.session_state and st.session_state.markets_list:
            market_options = {f"{m.question[:60]}...": m for m in st.session_state.markets_list}
            selected = st.selectbox("选择市场", options=list(market_options.keys()))
            if selected:
                new_market = market_options[selected]
                market_changed = st.session_state.current_market != new_market
                st.session_state.current_market = new_market
                
                # 初始化订单管理器和价格监控器
                if not st.session_state.order_manager or \
                   st.session_state.order_manager.condition_id != st.session_state.current_market.condition_id or \
                   market_changed:
                    st.session_state.order_manager = OrderManager(
                        st.session_state.api,
                        st.session_state.current_market.condition_id,
                        st.session_state.position
                    )
                    # 选择市场后立即加载一次数据
                    st.rerun()
        
        if st.session_state.current_market:
            st.success(f"当前市场:\n{st.session_state.current_market.question}")
        
        st.divider()
        
        # 控制按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ 开始监控", type="primary", disabled=st.session_state.is_running):
                st.session_state.is_running = True
                st.rerun()
        
        with col2:
            if st.button("⏸️ 停止监控", disabled=not st.session_state.is_running):
                st.session_state.is_running = False
                st.rerun()
        
        # 自动交易开关
        st.divider()
        st.markdown("**🤖 自动交易**")
        auto_trading = st.checkbox(
            "启用自动买入",
            value=st.session_state.auto_trading_enabled,
            help="当 YES/NO 价格进入买入区间时自动下单"
        )
        st.session_state.auto_trading_enabled = auto_trading
        
        # 重置按钮
        if st.button("🔄 重置", type="secondary"):
            st.session_state.position = PairPosition()
            st.session_state.price_history = []
            st.session_state.trade_history = []
            st.rerun()
    
    # 主界面
    if not st.session_state.current_market:
        st.info("👈 请在侧边栏搜索并选择市场")
        # 如果没有选择市场，也尝试加载演示市场
        if demo_mode:
            st.info("💡 提示：已启用演示模式，可以点击'搜索市场'查看演示数据")
        return
    
    # 获取订单簿数据的辅助函数
    def fetch_orderbook():
        """同步方式获取订单簿"""
        try:
            # 优先使用 slug，因为 get_orderbook 可以自动从 gamma-api 获取信息
            market_id = st.session_state.current_market.slug or st.session_state.current_market.condition_id
            if not market_id:
                return None
            
            result = run_async(
                st.session_state.api.get_orderbook(market_id)
            )
            return result
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取订单簿失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    # 获取订单簿数据
    orderbook = None
    
    # 如果没有运行，也尝试获取一次数据用于显示
    if not st.session_state.is_running:
        # 即使没有运行，也显示初始数据
        if demo_mode:
            if not st.session_state.price_history:
                orderbook = create_demo_orderbook()
        else:
            orderbook = fetch_orderbook()
            if not orderbook:
                st.error("❌ 无法获取订单簿")
                st.info("💡 可能的原因：市场已关闭、网络问题或市场暂时没有流动性")
                orderbook = None
    
    if st.session_state.is_running:
        if demo_mode:
            # 演示模式：每次更新时生成新的订单簿
            orderbook = create_demo_orderbook()
        else:
            orderbook = fetch_orderbook()
            if not orderbook:
                st.error("❌ 无法获取订单簿")
                st.info("💡 可能的原因：市场已关闭、网络问题或市场暂时没有流动性")
                orderbook = None
        
        if orderbook:
            if st.session_state.order_manager:
                st.session_state.order_manager.update_orderbook(orderbook)
            
            # 风险控制检查（最高优先级）
            if st.session_state.current_market:
                market_end_time = st.session_state.current_market.end_date if hasattr(st.session_state.current_market, 'end_date') else None
                stop_result = st.session_state.risk_controller.check_stop_conditions(
                    st.session_state.position,
                    orderbook,
                    market_end_time
                )
                st.session_state.stop_condition_result = stop_result
                
                # 如果风险控制要求停止，禁用自动交易
                if stop_result.should_stop:
                    st.session_state.auto_trading_enabled = False
            
            # 价格监控和自动交易（在 Streamlit 中直接检查，不使用回调）
            yes_price = orderbook.yes_mid_price
            no_price = orderbook.no_mid_price
            current_time = datetime.now()
            
            # 检查 YES 买入条件
            yes_price_key = f"YES_{yes_price:.4f}"
            yes_last_check = st.session_state.last_auto_trade_check.get(yes_price_key)
            yes_check_result = check_buy_conditions(
                "YES", yes_price, st.session_state.position, 
                st.session_state.order_manager, orderbook,
                st.session_state.auto_trading_enabled, yes_last_check
            )
            st.session_state.buy_reasons["YES"] = yes_check_result
            
            # 如果条件满足，尝试下单
            if yes_check_result["can_buy"]:
                try:
                    qty = Config.DEFAULT_ORDER_SIZE
                    opposite_avg = st.session_state.position.no.avg_price
                    target_price = st.session_state.order_manager.calculate_target_price("YES", opposite_avg)
                    
                    async def place_yes_order():
                        order = await st.session_state.order_manager.place_limit_order("YES", qty, target_price)
                        if order:
                            if order.status.value == "filled":
                                st.session_state.trade_history.append({
                                    "timestamp": datetime.now(),
                                    "side": "YES",
                                    "qty": order.filled_qty,
                                    "price": order.filled_price
                                })
                                st.session_state.pending_refresh = True
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(f"✅ YES 订单成交: {order.filled_qty:.2f} @ ${order.filled_price:.4f}")
                    
                    run_async(place_yes_order())
                    st.session_state.last_auto_trade_check[yes_price_key] = current_time
                    if st.session_state.pending_refresh:
                        st.session_state.pending_refresh = False
                        st.rerun()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"自动买入 YES 失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # 检查 NO 买入条件（无论价格是否在区间内都检查）
            no_price_key = f"NO_{no_price:.4f}"
            no_last_check = st.session_state.last_auto_trade_check.get(no_price_key)
            no_check_result = check_buy_conditions(
                "NO", no_price, st.session_state.position,
                st.session_state.order_manager, orderbook,
                st.session_state.auto_trading_enabled, no_last_check
            )
            st.session_state.buy_reasons["NO"] = no_check_result
            
            # 如果条件满足，尝试下单
            if no_check_result["can_buy"]:
                try:
                    qty = Config.DEFAULT_ORDER_SIZE
                    opposite_avg = st.session_state.position.yes.avg_price
                    target_price = st.session_state.order_manager.calculate_target_price("NO", opposite_avg)
                    
                    async def place_no_order():
                        order = await st.session_state.order_manager.place_limit_order("NO", qty, target_price)
                        if order:
                            if order.status.value == "filled":
                                st.session_state.trade_history.append({
                                    "timestamp": datetime.now(),
                                    "side": "NO",
                                    "qty": order.filled_qty,
                                    "price": order.filled_price
                                })
                                st.session_state.pending_refresh = True
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(f"✅ NO 订单成交: {order.filled_qty:.2f} @ ${order.filled_price:.4f}")
                    
                    run_async(place_no_order())
                    st.session_state.last_auto_trade_check[no_price_key] = current_time
                    if st.session_state.pending_refresh:
                        st.session_state.pending_refresh = False
                        st.rerun()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"自动买入 NO 失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # 更新价格历史（即使订单簿为空，也记录数据）
            price_data = get_orderbook_data(orderbook)
            st.session_state.price_history.append(price_data)
            
            # 保持最近100个数据点
            if len(st.session_state.price_history) > 100:
                st.session_state.price_history.pop(0)
            
            # 如果订单簿为空，显示提示
            if not orderbook.yes_bids and not orderbook.yes_asks and not orderbook.no_bids and not orderbook.no_asks:
                st.warning("⚠️ 订单簿为空：市场可能刚开始或没有流动性，等待订单数据...")
        else:
            # 如果没有订单簿，显示错误信息
            st.error("❌ 无法获取订单簿数据")
            st.info("💡 请检查网络连接或尝试使用其他市场")
    elif orderbook:
        # 即使没有运行，也显示一次数据
        if st.session_state.order_manager:
            st.session_state.order_manager.update_orderbook(orderbook)
        
        # 初始化价格历史（如果为空）
        if not st.session_state.price_history:
            price_data = get_orderbook_data(orderbook)
            st.session_state.price_history.append(price_data)
    
    # 顶部指标卡片 - 使用更清晰的样式
    # 确保使用最新的持仓数据
    if st.session_state.order_manager:
        display_position = st.session_state.order_manager.position
    else:
        display_position = st.session_state.position
    
    st.markdown("### 📊 关键指标")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # 计算配对成本：如果只买入单边，使用当前市场价格
        if orderbook:
            yes_avg = display_position.yes.avg_price if display_position.yes.qty > 0 else orderbook.yes_mid_price
            no_avg = display_position.no.avg_price if display_position.no.qty > 0 else orderbook.no_mid_price
            pair_cost = yes_avg + no_avg
        else:
            # 如果没有订单簿，使用默认计算（可能不准确）
            pair_cost = display_position.pair_cost
        
        delta_text = "✅ 安全" if pair_cost < 0.98 else "⚠️ 风险"
        delta_color = "normal" if pair_cost < 0.98 else "inverse"
        st.metric(
            "配对成本",
            f"${pair_cost:.4f}",
            delta=delta_text,
            delta_color=delta_color
        )
    
    with col2:
        total_cost = display_position.total_cost
        st.metric(
            "总成本",
            f"${total_cost:.2f}",
            delta=None
        )
    
    with col3:
        min_qty = display_position.min_qty
        st.metric(
            "最小持仓",
            f"{min_qty:.2f}",
            delta=None
        )
    
    with col4:
        is_profitable = display_position.is_profitable()
        status_text = "✅ 已锁定" if is_profitable else "⏳ 未锁定"
        delta_text = "💰 盈利" if is_profitable else "⏳ 等待中"
        st.metric(
            "利润状态",
            status_text,
            delta=delta_text,
            delta_color="normal" if is_profitable else "off"
        )
    
    # 风险控制状态显示
    if st.session_state.stop_condition_result:
        stop_result = st.session_state.stop_condition_result
        if stop_result.should_stop:
            st.warning(f"⚠️ **风险控制停止交易**: {stop_result.reason}")
            if stop_result.details:
                with st.expander("查看详细信息"):
                    for key, value in stop_result.details.items():
                        st.caption(f"{key}: {value}")
        else:
            st.success("✅ 风险检查通过")
    
    st.divider()
    
    # 风险控制状态显示
    if st.session_state.stop_condition_result:
        stop_result = st.session_state.stop_condition_result
        if stop_result.should_stop:
            st.warning(f"⚠️ **风险控制停止交易**: {stop_result.reason}")
            if stop_result.details:
                with st.expander("📋 查看详细信息"):
                    for key, value in stop_result.details.items():
                        if isinstance(value, float):
                            st.caption(f"**{key}**: {value:.4f}")
                        else:
                            st.caption(f"**{key}**: {value}")
        else:
            # 显示风险状态（即使通过也显示）
            has_yes = display_position.yes.qty > 0
            has_no = display_position.no.qty > 0
            is_unhedged = (has_yes and not has_no) or (has_no and not has_yes)
            
            if is_unhedged:
                unhedged_side = "YES" if has_yes else "NO"
                unhedged_duration = 0
                if st.session_state.risk_controller.unhedged_start_time:
                    unhedged_duration = (datetime.now(timezone.utc) - st.session_state.risk_controller.unhedged_start_time).total_seconds()
                
                remaining_time = Config.MAX_UNHEDGED_SEC - unhedged_duration
                if remaining_time > 0:
                    st.info(f"⚠️ **单边持仓警告**: 当前只有 {unhedged_side} 持仓，剩余时间 {int(remaining_time)}秒")
                else:
                    st.error(f"❌ **单边持仓超时**: {unhedged_side} 持仓时间超过 {Config.MAX_UNHEDGED_SEC}秒")
    
    st.divider()
    
    # 主要内容区域
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 📈 实时价格趋势")
        
        if st.session_state.price_history:
            fig = create_price_chart(st.session_state.price_history)
            st.plotly_chart(fig, width='stretch', theme="streamlit")
        else:
            st.info("⏳ 等待价格数据...")
        
        # 持仓信息
        st.markdown("### 💼 持仓信息")
        
        # 确保使用最新的持仓数据（从 order_manager 同步，如果存在）
        if st.session_state.order_manager:
            # order_manager.position 和 st.session_state.position 是同一个对象引用
            # 但为了确保数据同步，我们显式使用 order_manager 的 position
            display_position = st.session_state.order_manager.position
        else:
            display_position = st.session_state.position
        
        col_pos1, col_pos2 = st.columns(2)
        
        with col_pos1:
            st.markdown("#### 🟢 YES")
            st.metric("持仓数量", f"{display_position.yes.qty:.2f}", delta=None)
            st.metric("总成本", f"${display_position.yes.cost:.2f}", delta=None)
            st.metric("平均价格", f"${display_position.yes.avg_price:.4f}", delta=None)
            # 调试信息
            if st.session_state.order_manager and st.session_state.order_manager.filled_orders:
                yes_orders = [o for o in st.session_state.order_manager.filled_orders if o.side == "YES"]
                if yes_orders:
                    st.caption(f"✅ 已成交 {len(yes_orders)} 笔 YES 订单")
        
        with col_pos2:
            st.markdown("#### 🔴 NO")
            st.metric("持仓数量", f"{display_position.no.qty:.2f}", delta=None)
            st.metric("总成本", f"${display_position.no.cost:.2f}", delta=None)
            st.metric("平均价格", f"${display_position.no.avg_price:.4f}", delta=None)
            # 调试信息
            if st.session_state.order_manager and st.session_state.order_manager.filled_orders:
                no_orders = [o for o in st.session_state.order_manager.filled_orders if o.side == "NO"]
                if no_orders:
                    st.caption(f"✅ 已成交 {len(no_orders)} 笔 NO 订单")
    
    with col_right:
        # 市场行情
        st.markdown("### 📊 市场行情")
        if orderbook:
            yes_mid = orderbook.yes_mid_price
            no_mid = orderbook.no_mid_price
            
            st.metric("🟢 YES 中间价", f"${yes_mid:.4f}", delta=None)
            st.metric("🔴 NO 中间价", f"${no_mid:.4f}", delta=None)
            
            # 买入状态（显示详细原因）
            yes_can_buy = Config.ENTRY_PRICE_MIN <= yes_mid <= Config.ENTRY_PRICE_MAX
            no_can_buy = Config.ENTRY_PRICE_MIN <= no_mid <= Config.ENTRY_PRICE_MAX
            
            st.markdown("**买入状态**")
            
            # YES 买入状态
            with st.expander(f"🟢 YES 价格: ${yes_mid:.4f}", expanded=yes_can_buy):
                if yes_can_buy:
                    yes_reason = st.session_state.buy_reasons.get("YES")
                    if yes_reason and yes_reason.get("can_buy"):
                        st.success("✅ " + yes_reason.get("reason", "可以买入"))
                    elif yes_reason:
                        # 价格在区间内但未买入，显示详细原因
                        st.warning(yes_reason.get("reason", "未买入"))
                        details = yes_reason.get("details", {})
                        if details:
                            st.markdown("**详细信息:**")
                            if details.get("cooldown"):
                                st.caption(f"⏳ 冷却时间剩余: {details.get('time_remaining', 0):.1f}秒")
                            if details.get("can_buy") == False:
                                st.caption(f"当前配对成本: ${details.get('current_pair_cost', 0):.4f}")
                                st.caption(f"买入后配对成本: ${details.get('pair_cost_after', 0):.4f}")
                                st.caption(f"当前平均价: ${details.get('current_avg', 0):.4f}")
                                st.caption(f"对方平均价: ${details.get('opposite_avg', 0):.4f}")
                            if details.get("target_price") and details.get("best_ask_price"):
                                st.caption(f"目标价格: ${details.get('target_price', 0):.4f}")
                                st.caption(f"最佳卖价: ${details.get('best_ask_price', 0):.4f}")
                                if details.get("price_diff"):
                                    st.caption(f"价格差: ${details.get('price_diff', 0):.4f}")
                    else:
                        st.info("⏳ 正在检查买入条件...")
                else:
                    st.info(f"⚪ 价格不在买入区间 (${Config.ENTRY_PRICE_MIN:.2f} - ${Config.ENTRY_PRICE_MAX:.2f})")
            
            # NO 买入状态
            with st.expander(f"🔴 NO 价格: ${no_mid:.4f}", expanded=no_can_buy):
                if no_can_buy:
                    no_reason = st.session_state.buy_reasons.get("NO")
                    if no_reason and no_reason.get("can_buy"):
                        st.success("✅ " + no_reason.get("reason", "可以买入"))
                    elif no_reason:
                        # 价格在区间内但未买入，显示详细原因
                        st.warning(no_reason.get("reason", "未买入"))
                        details = no_reason.get("details", {})
                        if details:
                            st.markdown("**详细信息:**")
                            if details.get("cooldown"):
                                st.caption(f"⏳ 冷却时间剩余: {details.get('time_remaining', 0):.1f}秒")
                            if details.get("can_buy") == False:
                                st.caption(f"当前配对成本: ${details.get('current_pair_cost', 0):.4f}")
                                st.caption(f"买入后配对成本: ${details.get('pair_cost_after', 0):.4f}")
                                st.caption(f"当前平均价: ${details.get('current_avg', 0):.4f}")
                                st.caption(f"对方平均价: ${details.get('opposite_avg', 0):.4f}")
                            if details.get("target_price") and details.get("best_ask_price"):
                                st.caption(f"目标价格: ${details.get('target_price', 0):.4f}")
                                st.caption(f"最佳卖价: ${details.get('best_ask_price', 0):.4f}")
                                if details.get("price_diff"):
                                    st.caption(f"价格差: ${details.get('price_diff', 0):.4f}")
                    else:
                        st.info("⏳ 正在检查买入条件...")
                else:
                    st.info(f"⚪ 价格不在买入区间 (${Config.ENTRY_PRICE_MIN:.2f} - ${Config.ENTRY_PRICE_MAX:.2f})")
        else:
            st.info("⏳ 等待订单簿数据...")
        
        st.divider()
        
        # 执行参数
        st.markdown("### ⚙️ 执行参数")
        params_df = pd.DataFrame({
            "参数": [
                "买入价格区间",
                "默认订单大小",
                "平衡订单大小",
                "不平衡阈值",
                "准入判定阈值"
            ],
            "值": [
                f"${Config.ENTRY_PRICE_MIN:.2f} - ${Config.ENTRY_PRICE_MAX:.2f}",
                f"{Config.DEFAULT_ORDER_SIZE:.0f} 份",
                f"{Config.REBALANCE_ORDER_SIZE:.0f} 份",
                f"{Config.IMBALANCE_THRESHOLD * 100:.0f}%",
                "< 0.98 (2% 手续费)"
            ]
        })
        st.dataframe(
            params_df, 
            width='stretch',
            hide_index=True,
            height=200
        )
        
        st.divider()
        
        # 交易历史
        st.markdown("### 🔄 交易历史")
        if st.session_state.order_manager and st.session_state.order_manager.filled_orders:
            trades_data = []
            for order in st.session_state.order_manager.filled_orders[-10:]:
                side_emoji = "🟢" if order.side == "YES" else "🔴"
                trades_data.append({
                    "时间": order.timestamp.strftime("%H:%M:%S"),
                    "方向": f"{side_emoji} {order.side}",
                    "数量": f"{order.filled_qty:.2f}",
                    "价格": f"${order.filled_price:.4f}",
                    "成本": f"${order.filled_qty * order.filled_price:.2f}"
                })
            
            if trades_data:
                trades_df = pd.DataFrame(trades_data)
                st.dataframe(
                    trades_df, 
                    width='stretch',
                    hide_index=True,
                    height=300
                )
        else:
            st.info("📝 暂无交易记录")
    
    # 底部状态栏
    st.divider()
    status_col1, status_col2, status_col3 = st.columns(3)
    
    with status_col1:
        if st.session_state.demo_mode:
            st.warning("🔶 演示模式 - 使用模拟数据")
        else:
            st.success("✅ 连接真实 API")
    
    with status_col2:
        if st.session_state.is_running:
            st.success("🟢 监控中...")
        else:
            st.info("⏸️ 已停止")
    
    with status_col3:
        if st.session_state.order_manager:
            total_trades = len(st.session_state.order_manager.filled_orders)
            st.metric("总交易数", total_trades)
    
    # 自动刷新
    if st.session_state.is_running:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()


"""
地址追踪图表模块
按市场显示 YES/NO 交易的时间序列图表
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from typing import List, Dict, Optional, Set
import asyncio

from ..market.address_tracker import AddressTracker, Trade


def create_market_trade_chart(
    trades: List[Trade], 
    market_condition_id: str, 
    market_title: str,
    tracked_proxy_wallets: Optional[Set[str]] = None
):
    """
    创建单个市场的交易图表
    显示 YES 和 NO 的买卖随时间变化
    
    Args:
        trades: 该市场的交易列表
        market_condition_id: 市场条件ID
        market_title: 市场标题
        tracked_proxy_wallets: 当前追踪地址的代理钱包集合（用于标记）
    """
    # 筛选该市场的交易
    market_trades = [t for t in trades if t.condition_id == market_condition_id]
    
    if not market_trades:
        st.warning(f"该市场没有交易数据")
        return
    
    # 按时间排序
    market_trades.sort(key=lambda x: x.timestamp)
    
    # 创建数据框
    df = pd.DataFrame([
        {
            'time': datetime.fromtimestamp(t.timestamp),
            'price': t.price,
            'size': t.size,
            'side': t.side,
            'value': t.value,
            'asset': t.asset,
            'proxy_wallet': t.proxy_wallet,
            'is_tracked': tracked_proxy_wallets is not None and t.proxy_wallet in tracked_proxy_wallets
        }
        for t in market_trades
    ])
    
    # 判断 YES/NO：价格 > 0.5 的是 YES，<= 0.5 的是 NO
    df['outcome'] = df['price'].apply(lambda p: 'YES' if p > 0.5 else 'NO')
    
    # 创建图表
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('交易价格随时间变化', '交易数量随时间变化'),
        vertical_spacing=0.15,
        row_heights=[0.6, 0.4]
    )
    
    # 统一的 marker 大小
    marker_size = 10
    marker_size_tracked = 14  # 当前追踪地址的交易用更大的marker
    
    # 分离四种类型：买YES、买NO、卖YES、卖NO
    buy_yes = df[(df['side'] == 'BUY') & (df['outcome'] == 'YES')]
    buy_no = df[(df['side'] == 'BUY') & (df['outcome'] == 'NO')]
    sell_yes = df[(df['side'] == 'SELL') & (df['outcome'] == 'YES')]
    sell_no = df[(df['side'] == 'SELL') & (df['outcome'] == 'NO')]
    
    # 第一个子图：价格图
    # 买入 YES - 其他用户
    if not buy_yes.empty:
        buy_yes_others = buy_yes[~buy_yes['is_tracked']]
        buy_yes_tracked = buy_yes[buy_yes['is_tracked']]
        
        # 其他用户的交易
        if not buy_yes_others.empty:
            fig.add_trace(
                go.Scatter(
                    x=buy_yes_others['time'],
                    y=buy_yes_others['price'],
                    mode='markers',
                    name='买入 YES',
                    marker=dict(
                        size=marker_size,
                        color='#00CC00',  # 亮绿色
                        symbol='triangle-up',
                        line=dict(width=1, color='darkgreen'),
                        opacity=0.6  # 其他用户的交易半透明
                    ),
                    text=[f"<b>买入 YES</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(buy_yes_others['size'], buy_yes_others['price'], buy_yes_others['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    legendgroup='buy_yes',
                    showlegend=True
                ),
                row=1, col=1
            )
        
        # 当前追踪地址的交易
        if not buy_yes_tracked.empty:
            fig.add_trace(
                go.Scatter(
                    x=buy_yes_tracked['time'],
                    y=buy_yes_tracked['price'],
                    mode='markers',
                    name='买入 YES (⭐你的)',
                    marker=dict(
                        size=marker_size_tracked,
                        color='#00CC00',  # 亮绿色
                        symbol='triangle-up',
                        line=dict(width=3, color='darkgreen'),  # 加粗边框
                        opacity=1.0  # 完全不透明
                    ),
                    text=[f"<b>⭐ 买入 YES (你的交易)</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(buy_yes_tracked['size'], buy_yes_tracked['price'], buy_yes_tracked['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    legendgroup='buy_yes',
                    showlegend=True
                ),
                row=1, col=1
            )
    
    # 买入 NO
    if not buy_no.empty:
        buy_no_others = buy_no[~buy_no['is_tracked']]
        buy_no_tracked = buy_no[buy_no['is_tracked']]
        
        # 其他用户的交易
        if not buy_no_others.empty:
            fig.add_trace(
                go.Scatter(
                    x=buy_no_others['time'],
                    y=buy_no_others['price'],
                    mode='markers',
                    name='买入 NO',
                    marker=dict(
                        size=marker_size,
                        color='#90EE90',  # 浅绿色
                        symbol='circle',
                        line=dict(width=1, color='green'),
                        opacity=0.6
                    ),
                    text=[f"<b>买入 NO</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(buy_no_others['size'], buy_no_others['price'], buy_no_others['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    legendgroup='buy_no',
                    showlegend=True
                ),
                row=1, col=1
            )
        
        # 当前追踪地址的交易
        if not buy_no_tracked.empty:
            fig.add_trace(
                go.Scatter(
                    x=buy_no_tracked['time'],
                    y=buy_no_tracked['price'],
                    mode='markers',
                    name='买入 NO (⭐你的)',
                    marker=dict(
                        size=marker_size_tracked,
                        color='#90EE90',  # 浅绿色
                        symbol='circle',
                        line=dict(width=3, color='green'),
                        opacity=1.0
                    ),
                    text=[f"<b>⭐ 买入 NO (你的交易)</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(buy_no_tracked['size'], buy_no_tracked['price'], buy_no_tracked['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    legendgroup='buy_no',
                    showlegend=True
                ),
                row=1, col=1
            )
    
    # 卖出 YES
    if not sell_yes.empty:
        sell_yes_others = sell_yes[~sell_yes['is_tracked']]
        sell_yes_tracked = sell_yes[sell_yes['is_tracked']]
        
        # 其他用户的交易
        if not sell_yes_others.empty:
            fig.add_trace(
                go.Scatter(
                    x=sell_yes_others['time'],
                    y=sell_yes_others['price'],
                    mode='markers',
                    name='卖出 YES',
                    marker=dict(
                        size=marker_size,
                        color='#FF0000',  # 亮红色
                        symbol='triangle-down',
                        line=dict(width=1, color='darkred'),
                        opacity=0.6
                    ),
                    text=[f"<b>卖出 YES</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(sell_yes_others['size'], sell_yes_others['price'], sell_yes_others['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    legendgroup='sell_yes',
                    showlegend=True
                ),
                row=1, col=1
            )
        
        # 当前追踪地址的交易
        if not sell_yes_tracked.empty:
            fig.add_trace(
                go.Scatter(
                    x=sell_yes_tracked['time'],
                    y=sell_yes_tracked['price'],
                    mode='markers',
                    name='卖出 YES (⭐你的)',
                    marker=dict(
                        size=marker_size_tracked,
                        color='#FF0000',  # 亮红色
                        symbol='triangle-down',
                        line=dict(width=3, color='darkred'),
                        opacity=1.0
                    ),
                    text=[f"<b>⭐ 卖出 YES (你的交易)</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(sell_yes_tracked['size'], sell_yes_tracked['price'], sell_yes_tracked['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    legendgroup='sell_yes',
                    showlegend=True
                ),
                row=1, col=1
            )
    
    # 卖出 NO
    if not sell_no.empty:
        sell_no_others = sell_no[~sell_no['is_tracked']]
        sell_no_tracked = sell_no[sell_no['is_tracked']]
        
        # 其他用户的交易
        if not sell_no_others.empty:
            fig.add_trace(
                go.Scatter(
                    x=sell_no_others['time'],
                    y=sell_no_others['price'],
                    mode='markers',
                    name='卖出 NO',
                    marker=dict(
                        size=marker_size,
                        color='#FFB6C1',  # 浅红色
                        symbol='square',
                        line=dict(width=1, color='red'),
                        opacity=0.6
                    ),
                    text=[f"<b>卖出 NO</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(sell_no_others['size'], sell_no_others['price'], sell_no_others['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    legendgroup='sell_no',
                    showlegend=True
                ),
                row=1, col=1
            )
        
        # 当前追踪地址的交易
        if not sell_no_tracked.empty:
            fig.add_trace(
                go.Scatter(
                    x=sell_no_tracked['time'],
                    y=sell_no_tracked['price'],
                    mode='markers',
                    name='卖出 NO (⭐你的)',
                    marker=dict(
                        size=marker_size_tracked,
                        color='#FFB6C1',  # 浅红色
                        symbol='square',
                        line=dict(width=3, color='red'),
                        opacity=1.0
                    ),
                    text=[f"<b>⭐ 卖出 NO (你的交易)</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(sell_no_tracked['size'], sell_no_tracked['price'], sell_no_tracked['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    legendgroup='sell_no',
                    showlegend=True
                ),
                row=1, col=1
            )
    
    # 第二个子图：数量柱状图
    # 买入数量（正值）
    buy_df = df[df['side'] == 'BUY']
    if not buy_df.empty:
        colors = ['#00CC00' if o == 'YES' else '#90EE90' for o in buy_df['outcome']]
        fig.add_trace(
            go.Bar(
                x=buy_df['time'],
                y=buy_df['size'],
                name='买入数量',
                marker=dict(color=colors),
                showlegend=False,
                text=[f"{o}" for o in buy_df['outcome']],
                hovertemplate='买入 %{text}<br>数量: %{y:.0f} shares<br>时间: %{x}<extra></extra>'
            ),
            row=2, col=1
        )
    
    # 卖出数量（负值）
    sell_df = df[df['side'] == 'SELL']
    if not sell_df.empty:
        colors = ['#FF0000' if o == 'YES' else '#FFB6C1' for o in sell_df['outcome']]
        fig.add_trace(
            go.Bar(
                x=sell_df['time'],
                y=-sell_df['size'],  # 负值显示在下方
                name='卖出数量',
                marker=dict(color=colors),
                showlegend=False,
                text=[f"{o}" for o in sell_df['outcome']],
                hovertemplate='卖出 %{text}<br>数量: %{y:.0f} shares<br>时间: %{x}<extra></extra>'
            ),
            row=2, col=1
        )
    
    # 更新布局
    fig.update_xaxes(title_text="时间", row=2, col=1)
    fig.update_yaxes(title_text="价格 ($)", row=1, col=1)
    fig.update_yaxes(title_text="数量", row=2, col=1)
    
    fig.update_layout(
        title=dict(
            text=f"{market_title}<br><sub>交易时间序列分析</sub>",
            x=0.5,
            xanchor='center'
        ),
        height=700,
        hovermode='closest',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # 显示图表
    st.plotly_chart(fig, use_container_width=True)
    
    # 显示统计信息
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总交易数", len(market_trades))
    
    with col2:
        avg_buy_price = buy_df['price'].mean() if not buy_df.empty else 0
        st.metric("平均买入价", f"${avg_buy_price:.3f}")
    
    with col3:
        avg_sell_price = sell_df['price'].mean() if not sell_df.empty else 0
        st.metric("平均卖出价", f"${avg_sell_price:.3f}")
    
    with col4:
        total_volume = df['value'].sum()
        st.metric("总交易额", f"${total_volume:.2f}")


async def get_market_all_trades(condition_id: str, limit: int = 200) -> List[Trade]:
    """获取市场的所有交易（用于对比）"""
    async with AddressTracker() as tracker:
        return await tracker.get_market_trades(condition_id, limit=limit)


async def get_market_all_trades_paginated(condition_id: str, max_trades: Optional[int] = None) -> List[Trade]:
    """获取市场的所有交易（分页获取，突破限制）"""
    async with AddressTracker() as tracker:
        return await tracker.get_all_market_trades(condition_id, max_trades=max_trades, batch_size=1000)


def create_market_comparison_chart(
    my_trades: List[Trade],
    all_trades: List[Trade],
    market_condition_id: str,
    market_title: str,
    tracked_proxy_wallets: Optional[Set[str]] = None
):
    """
    创建市场对比图表
    显示自己的交易 vs 市场所有交易
    
    Args:
        my_trades: 自己的交易列表
        all_trades: 市场所有交易列表
        market_condition_id: 市场条件ID
        market_title: 市场标题
        tracked_proxy_wallets: 当前追踪地址的代理钱包集合（用于标记）
    """
    # 筛选该市场的交易
    my_market_trades = [t for t in my_trades if t.condition_id == market_condition_id]
    
    if not my_market_trades or not all_trades:
        st.warning("没有足够的数据进行对比")
        return
    
    # 创建数据框
    all_df = pd.DataFrame([
        {
            'time': datetime.fromtimestamp(t.timestamp),
            'price': t.price,
            'size': t.size,
            'side': t.side,
            'wallet': t.proxy_wallet
        }
        for t in all_trades
    ])
    
    # 获取当前追踪地址的所有代理钱包
    if tracked_proxy_wallets:
        my_wallets = tracked_proxy_wallets
    else:
        # 如果没有提供，从交易中提取
        my_wallets = set(t.proxy_wallet for t in my_market_trades)
    
    # 创建图表
    fig = go.Figure()
    
    # 市场所有交易（作为背景）
    other_trades = all_df[~all_df['wallet'].isin(my_wallets)]
    if not other_trades.empty:
        # 买入
        other_buy = other_trades[other_trades['side'] == 'BUY']
        if not other_buy.empty:
            fig.add_trace(
                go.Scatter(
                    x=other_buy['time'],
                    y=other_buy['price'],
                    mode='markers',
                    name='其他人买入',
                    marker=dict(
                        size=4,
                        color='lightgreen',
                        opacity=0.3,
                        symbol='circle'
                    ),
                    showlegend=True
                )
            )
        
        # 卖出
        other_sell = other_trades[other_trades['side'] == 'SELL']
        if not other_sell.empty:
            fig.add_trace(
                go.Scatter(
                    x=other_sell['time'],
                    y=other_sell['price'],
                    mode='markers',
                    name='其他人卖出',
                    marker=dict(
                        size=4,
                        color='lightcoral',
                        opacity=0.3,
                        symbol='circle'
                    ),
                    showlegend=True
                )
            )
    
    # 我的交易（高亮显示）
    my_df = all_df[all_df['wallet'].isin(my_wallets)]
    if not my_df.empty:
        # 买入
        my_buy = my_df[my_df['side'] == 'BUY']
        if not my_buy.empty:
            fig.add_trace(
                go.Scatter(
                    x=my_buy['time'],
                    y=my_buy['price'],
                    mode='markers',
                    name='⭐ 我的买入',
                    marker=dict(
                        size=8,
                        color='green',
                        symbol='star',
                        line=dict(width=2, color='darkgreen')
                    ),
                    text=[f"数量: {s:.0f}<br>价格: ${p:.3f}" 
                          for s, p in zip(my_buy['size'], my_buy['price'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>'
                )
            )
        
        # 卖出
        my_sell = my_df[my_df['side'] == 'SELL']
        if not my_sell.empty:
            fig.add_trace(
                go.Scatter(
                    x=my_sell['time'],
                    y=my_sell['price'],
                    mode='markers',
                    name='⭐ 我的卖出',
                    marker=dict(
                        size=8,
                        color='red',
                        symbol='star',
                        line=dict(width=2, color='darkred')
                    ),
                    text=[f"数量: {s:.0f}<br>价格: ${p:.3f}" 
                          for s, p in zip(my_sell['size'], my_sell['price'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>'
                )
            )
    
    # 更新布局
    fig.update_layout(
        title=dict(
            text=f"{market_title}<br><sub>市场交易对比（你 vs 其他人）</sub>",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="时间",
        yaxis_title="价格 ($)",
        height=600,
        hovermode='closest',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # 显示图表
    st.plotly_chart(fig, use_container_width=True)


def display_address_tracking_with_charts():
    """显示带图表的地址追踪界面"""
    st.title("🔍 地址追踪 - 图表分析")
    st.markdown("---")
    
    # 默认地址
    DEFAULT_ADDRESS = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"
    
    # 初始化 session state
    if 'tracked_address' not in st.session_state:
        st.session_state.tracked_address = DEFAULT_ADDRESS
    if 'trades_data' not in st.session_state:
        st.session_state.trades_data = None
    if 'analysis_data' not in st.session_state:
        st.session_state.analysis_data = None
    
    # 输入地址和设置
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        address = st.text_input(
            "输入要追踪的以太坊地址",
            value=st.session_state.tracked_address or DEFAULT_ADDRESS,
            placeholder="0x...",
            help="输入以太坊地址（0x开头）来追踪其在 Polymarket 的交易活动",
            key="address_input"
        )
    
    with col2:
        trade_limit = st.selectbox(
            "交易数量",
            options=[200, 500, 1000, 2000, 3000],
            index=0,  # 默认200
            help="选择获取的交易数量（增加以覆盖更长时间）",
            key="trade_limit_select"
        )
    
    with col3:
        st.write("")
        st.write("")
        track_button = st.button("🔍 追踪并分析", use_container_width=True, key="track_btn")
    
    st.caption("💡 已填充默认地址，增加了交易数量选项以覆盖最近1-3小时")
    
    # 如果点击追踪按钮或已有数据
    if track_button and address:
        if not address.startswith("0x") or len(address) != 42:
            st.error("❌ 请输入有效的以太坊地址（0x开头，42字符）")
            return
        
        with st.spinner(f"正在获取地址 {address} 的交易数据（最多 {trade_limit} 笔）..."):
            try:
                # 获取交易数据（使用分页方法突破500笔限制）
                async def fetch_data():
                    async with AddressTracker() as tracker:
                        trades = await tracker.get_all_address_trades(address, max_trades=trade_limit)
                        analysis = tracker.analyze_trades(trades)
                        return trades, analysis
                
                trades, analysis = asyncio.run(fetch_data())
                
                # 保存到 session state
                st.session_state.tracked_address = address
                st.session_state.trades_data = trades
                st.session_state.analysis_data = analysis
            except Exception as e:
                st.error(f"❌ 获取数据失败: {e}")
                import traceback
                st.code(traceback.format_exc())
                return
    
    # 使用 session state 中的数据
    if st.session_state.trades_data and st.session_state.analysis_data:
        trades = st.session_state.trades_data
        analysis = st.session_state.analysis_data
        
        if not trades:
            st.warning("❌ 未找到该地址的交易记录")
            return
        
        st.success(f"✓ 找到 {analysis['total_trades']} 笔交易，涉及 {analysis['markets_count']} 个市场")
        
        # 显示追踪的地址信息
        with st.expander("📋 地址信息", expanded=False):
            st.markdown(f"""
            **追踪的主地址**：  
            `{st.session_state.tracked_address}`
            
            **关联的代理钱包**（{len(analysis['proxy_wallets'])} 个）：
            """)
            for wallet in analysis['proxy_wallets']:
                st.code(wallet, language=None)
            
            st.info("""
            💡 **说明**：
            - 你输入的是主地址
            - Polymarket 通过代理钱包执行交易
            - 图表显示的是主地址关联的所有交易
            - "我的买入/卖出" = 你这个主地址的所有交易
            """)
        
        # 显示概览
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总交易数", analysis['total_trades'])
        with col2:
            st.metric("买入交易", analysis['buy_trades'])
        with col3:
            st.metric("卖出交易", analysis['sell_trades'])
        with col4:
            st.metric("涉及市场", analysis['markets_count'])
        
        st.markdown("---")
        
        # 按市场分组
        markets = analysis['markets']
        if not markets:
            st.warning("没有市场数据")
            return
        
        # 按交易次数排序
        sorted_markets = sorted(
            markets.items(),
            key=lambda x: len(x[1]['trades']),
            reverse=True
        )
        
        # 选择市场
        st.subheader("📊 选择市场查看详细图表")
        
        # 筛选选项
        filter_option = st.selectbox(
            "筛选市场状态",
            options=["全部市场", "🟢 只看活跃", "🔴 只看已关闭", "🟡 只看未激活"],
            index=0,
            help="🟢活跃=可交易 | 🔴已关闭=已结束 | 🟡未激活=暂不可交易 | ⚪未知=无法获取状态",
            key="market_filter"
        )
        
        # 状态说明
        with st.expander("ℹ️ 市场状态说明"):
            st.markdown("""
            **市场状态类型**：
            - 🟢 **活跃**：市场开放且接受订单，可以交易
            - 🔴 **已关闭**：市场已结束，不再接受订单
            - 🟡 **未激活**：市场存在但暂时不接受订单
            - ⚪ **未知**：无法从API获取市场状态信息
            
            💡 **建议**：
            - 想交易？选择 "🟢 只看活跃"
            - 想分析已结束的市场？选择 "🔴 只看已关闭"
            - 查看所有历史？选择 "全部市场"
            """)
        
        # 获取市场状态（异步批量获取）
        async def get_markets_status():
            async with AddressTracker() as tracker:
                statuses = {}
                for condition_id, info in sorted_markets[:30]:  # 限制获取前30个
                    slug = info['slug']
                    status = await tracker.get_market_status(slug)
                    statuses[condition_id] = status
                return statuses
        
        # 显示加载状态
        with st.spinner("正在获取市场状态..."):
            market_statuses = asyncio.run(get_markets_status())
        
        # 创建市场选项（包含状态）并筛选
        market_options = []
        market_mapping = []  # 存储实际的市场索引
        for idx, (condition_id, info) in enumerate(sorted_markets[:30]):
            status = market_statuses.get(condition_id)
            
            # 判断市场状态
            market_state = "unknown"  # unknown, active, closed, inactive
            if status:
                if status.get('closed'):
                    status_text = "🔴 已关闭"
                    market_state = "closed"
                elif status.get('active') and status.get('acceptingOrders'):
                    status_text = "🟢 活跃"
                    market_state = "active"
                else:
                    status_text = "🟡 未激活"
                    market_state = "inactive"
            else:
                status_text = "⚪ 未知"
                market_state = "unknown"
            
            # 根据筛选选项过滤
            if filter_option == "🟢 只看活跃" and market_state != "active":
                continue
            elif filter_option == "🔴 只看已关闭" and market_state != "closed":
                continue
            elif filter_option == "🟡 只看未激活" and market_state != "inactive":
                continue
            # "全部市场" 不过滤
            
            market_options.append(
                f"{info['title'][:50]} ({len(info['trades'])} 笔) {status_text}"
            )
            market_mapping.append(idx)
        
        if not market_options:
            st.warning("没有符合筛选条件的市场")
            return
        
        selected_display_index = st.selectbox(
            "选择市场",
            range(len(market_options)),
            format_func=lambda i: market_options[i],
            key="market_selector"
        )
        
        # 获取实际的市场索引
        selected_index = market_mapping[selected_display_index]
        
        if selected_index is not None:
            condition_id, market_info = sorted_markets[selected_index]
            market_title = market_info['title']
            market_slug = market_info['slug']
            
            st.markdown("---")
            
            # 获取并显示市场状态
            market_status = market_statuses.get(condition_id)
            
            # 显示市场信息
            if market_status:
                if market_status.get('closed'):
                    status_badge = "🔴 已关闭"
                    status_color = "red"
                elif market_status.get('active') and market_status.get('acceptingOrders'):
                    status_badge = "🟢 活跃中"
                    status_color = "green"
                else:
                    status_badge = "🟡 未激活"
                    status_color = "orange"
                
                st.subheader(f"📈 {market_title}")
                st.markdown(f"**状态**: :{status_color}[{status_badge}]")
                
                # 显示市场链接
                st.caption(f"🔗 [在 Polymarket 上查看](https://polymarket.com/event/{market_slug})")
            else:
                st.subheader(f"📈 {market_title}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("交易次数", len(market_info['trades']))
            with col2:
                st.metric("买入", f"{market_info['buy_count']} 笔 (${market_info['buy_volume']:.2f})")
            with col3:
                st.metric("卖出", f"{market_info['sell_count']} 笔 (${market_info['sell_volume']:.2f})")
            
            # Tab 切换不同视图
            tab1, tab2 = st.tabs(["📊 我的交易分析", "🔄 市场对比分析"])
            
            with tab1:
                st.markdown("### 交易时间序列")
                # 传入追踪地址的代理钱包，用于标记
                tracked_wallets = set(analysis['proxy_wallets'])
                create_market_trade_chart(trades, condition_id, market_title, tracked_wallets)
            
            with tab2:
                st.markdown("### 市场整体交易对比")
                
                # 市场交易数量选择
                col_market1, col_market2, col_market3 = st.columns([2, 2, 2])
                
                with col_market1:
                    fetch_mode = st.radio(
                        "获取模式",
                        options=["限制数量", "🔥 获取全部"],
                        index=0,
                        help="限制数量：快速获取指定数量\n获取全部：分页获取所有交易（可能很多）",
                        key="fetch_mode"
                    )
                
                with col_market2:
                    if fetch_mode == "限制数量":
                        market_trade_limit = st.selectbox(
                            "交易数量",
                            options=[100, 200, 500, 1000, 2000, 5000, 10000],
                            index=2,  # 默认500
                            help="选择要获取的交易数量",
                            key="market_trade_limit"
                        )
                    else:
                        max_limit = st.number_input(
                            "最大数量（可选）",
                            min_value=0,
                            max_value=100000,
                            value=0,
                            step=1000,
                            help="0 表示不限制，获取全部\n设置上限可避免数据过多",
                            key="max_market_limit"
                        )
                
                with col_market3:
                    if fetch_mode == "限制数量":
                        st.info(f"""
                        **快速模式**：
                        - 获取最近 {market_trade_limit} 笔
                        - 加载快速
                        - 适合快速查看
                        """)
                    else:
                        st.warning(f"""
                        **完整模式**：
                        - 🔥 分页获取所有交易
                        - ⏰ 可能需要1-5分钟
                        - 💾 适合已关闭市场
                        - {"🚫 不限制数量" if max_limit == 0 else f"📊 最多 {max_limit:,} 笔"}
                        """)
                
                # 获取市场所有交易
                if fetch_mode == "限制数量":
                    with st.spinner(f"正在获取市场数据（最多 {market_trade_limit} 笔）..."):
                        all_trades = asyncio.run(get_market_all_trades(condition_id, limit=market_trade_limit))
                else:
                    max_trades_param = None if max_limit == 0 else max_limit
                    spinner_text = "正在分页获取市场所有交易..." if max_limit == 0 else f"正在分页获取市场交易（最多 {max_limit:,} 笔）..."
                    
                    with st.spinner(spinner_text):
                        # 显示进度提示
                        progress_placeholder = st.empty()
                        progress_placeholder.info("📊 开始分页获取... 每批1000笔")
                        
                        all_trades = asyncio.run(get_market_all_trades_paginated(
                            condition_id, 
                            max_trades=max_trades_param
                        ))
                        
                        progress_placeholder.success(f"✓ 分页获取完成！共 {len(all_trades):,} 笔交易")
                    
                    if all_trades:
                        # 显示统计信息
                        all_traders = set(t.proxy_wallet for t in all_trades)
                        buy_count = len([t for t in all_trades if t.side == 'BUY'])
                        sell_count = len([t for t in all_trades if t.side == 'SELL'])
                        
                        # 统计当前追踪地址的交易
                        tracked_wallets = set(analysis['proxy_wallets'])
                        my_trades_in_market = [t for t in all_trades if t.proxy_wallet in tracked_wallets]
                        my_trades_count = len(my_trades_in_market)
                        
                        st.success(f"✓ 获取到该市场的 {len(all_trades)} 笔交易（其中 ⭐ 你的交易：{my_trades_count} 笔）")
                        
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            st.metric("总交易数", len(all_trades))
                        with col2:
                            st.metric("交易者数", len(all_traders))
                        with col3:
                            st.metric("买入交易", buy_count)
                        with col4:
                            st.metric("卖出交易", sell_count)
                        with col5:
                            st.metric("⭐ 你的交易", my_trades_count)
                        
                        # 市场数据统计
                        with st.expander("📊 市场交易详细统计", expanded=False):
                            # 价格范围
                            prices = [t.price for t in all_trades]
                            st.markdown(f"""
                            **价格统计**：
                            - 最低价：${min(prices):.3f}
                            - 最高价：${max(prices):.3f}
                            - 平均价：${sum(prices)/len(prices):.3f}
                            """)
                            
                            # 交易量统计
                            total_volume = sum(t.value for t in all_trades)
                            buy_volume = sum(t.value for t in all_trades if t.side == 'BUY')
                            sell_volume = sum(t.value for t in all_trades if t.side == 'SELL')
                            
                            st.markdown(f"""
                            **交易量统计**：
                            - 总交易额：${total_volume:,.2f}
                            - 买入总额：${buy_volume:,.2f}
                            - 卖出总额：${sell_volume:,.2f}
                            """)
                            
                            # 时间范围
                            timestamps = [t.timestamp for t in all_trades]
                            from datetime import datetime
                            start_time = datetime.fromtimestamp(min(timestamps))
                            end_time = datetime.fromtimestamp(max(timestamps))
                            duration = max(timestamps) - min(timestamps)
                            
                            st.markdown(f"""
                            **时间范围**：
                            - 开始：{start_time.strftime('%Y-%m-%d %H:%M:%S')}
                            - 结束：{end_time.strftime('%Y-%m-%d %H:%M:%S')}
                            - 持续：{duration//60:.0f} 分钟
                            """)
                        
                        # 导出数据功能
                        st.markdown("---")
                        st.subheader("📥 导出市场数据")
                        
                        # 准备CSV数据
                        import pandas as pd
                        tracked_wallets = set(analysis['proxy_wallets'])
                        export_data = []
                        for t in all_trades:
                            is_mine = t.proxy_wallet in tracked_wallets
                            export_data.append({
                                '时间': datetime.fromtimestamp(t.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                                '方向': t.side,
                                '价格': t.price,
                                '数量': t.size,
                                '金额': t.value,
                                '是否为追踪地址': '⭐ 是' if is_mine else '否',
                                '钱包地址': t.proxy_wallet,
                                '市场标题': t.title,
                                '市场链接': t.market_url
                            })
                        
                        df_export = pd.DataFrame(export_data)
                        
                        csv = df_export.to_csv(index=False).encode('utf-8-sig')  # 使用 utf-8-sig 支持中文
                        
                        st.download_button(
                            label=f"📥 下载 CSV ({len(all_trades)} 笔交易)",
                            data=csv,
                            file_name=f"market_{condition_id[:8]}_trades.csv",
                            mime="text/csv",
                            help="下载该市场的所有交易数据为CSV文件",
                            use_container_width=True
                        )
                        
                        st.markdown("---")
                        
                        # 传入追踪地址的代理钱包，用于标记
                        tracked_wallets = set(analysis['proxy_wallets'])
                        create_market_comparison_chart(
                            trades,
                            all_trades,
                            condition_id,
                            market_title,
                            tracked_wallets
                        )
                    else:
                        st.warning("无法获取市场数据")


if __name__ == "__main__":
    display_address_tracking_with_charts()


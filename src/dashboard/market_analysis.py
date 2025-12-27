"""
市场分析 Dashboard
新逻辑：搜索市场 → 获取所有交易 → 标记目标地址
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from typing import List, Dict, Optional, Set
import asyncio

from ..market.market_searcher import MarketSearcher, MarketInfo
from ..market.address_tracker import AddressTracker, Trade


def create_all_trades_chart_with_highlight(
    all_trades: List[Trade],
    market_title: str,
    tracked_address: Optional[str] = None,
    tracked_proxy_wallets: Optional[Set[str]] = None
):
    """
    创建市场所有交易图表，高亮显示目标地址的交易
    
    Args:
        all_trades: 所有交易列表
        market_title: 市场标题
        tracked_address: 追踪的地址（用于显示）
        tracked_proxy_wallets: 追踪地址的代理钱包集合
    """
    if not all_trades:
        st.warning("没有交易数据")
        return
    
    # 创建数据框
    df = pd.DataFrame([
        {
            'time': datetime.fromtimestamp(t.timestamp),
            'price': t.price,
            'size': t.size,
            'side': t.side,
            'value': t.value,
            'proxy_wallet': t.proxy_wallet,
            'is_tracked': tracked_proxy_wallets is not None and t.proxy_wallet in tracked_proxy_wallets
        }
        for t in all_trades
    ])
    
    # 判断 YES/NO
    df['outcome'] = df['price'].apply(lambda p: 'YES' if p > 0.5 else 'NO')
    
    # 创建图表
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('交易价格随时间变化', '交易数量随时间变化'),
        vertical_spacing=0.15,
        row_heights=[0.65, 0.35]
    )
    
    # 分离交易类型
    buy_yes = df[(df['side'] == 'BUY') & (df['outcome'] == 'YES')]
    buy_no = df[(df['side'] == 'BUY') & (df['outcome'] == 'NO')]
    sell_yes = df[(df['side'] == 'SELL') & (df['outcome'] == 'YES')]
    sell_no = df[(df['side'] == 'SELL') & (df['outcome'] == 'NO')]
    
    # 分别添加四种交易类型到图表（买入YES、买入NO、卖出YES、卖出NO）
    
    # 1. 买入 YES
    if not buy_yes.empty:
        others = buy_yes[~buy_yes['is_tracked']]
        tracked = buy_yes[buy_yes['is_tracked']]
        
        # 其他人的买入YES
        if not others.empty:
            fig.add_trace(
                go.Scatter(
                    x=others['time'],
                    y=others['price'],
                    mode='markers',  # 只有散点，没有线
                    name='买入 YES',
                    marker=dict(
                        size=8,
                        color='#00CC00',  # 亮绿色
                        symbol='triangle-up',
                        opacity=0.4,
                        line=dict(width=0)  # 无边框
                    ),
                    text=[f"<b>买入 YES</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(others['size'], others['price'], others['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    showlegend=True
                ),
                row=1, col=1
            )
        
        # 目标地址的买入YES
        if not tracked.empty:
            fig.add_trace(
                go.Scatter(
                    x=tracked['time'],
                    y=tracked['price'],
                    mode='markers',
                    name='⭐ 买入 YES (目标)',
                    marker=dict(
                        size=14,
                        color='#00CC00',
                        symbol='triangle-up',
                        opacity=1.0,
                        line=dict(width=2, color='black')
                    ),
                    text=[f"<b>⭐ 买入 YES (目标)</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(tracked['size'], tracked['price'], tracked['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    showlegend=True
                ),
                row=1, col=1
            )
    
    # 2. 买入 NO
    if not buy_no.empty:
        others = buy_no[~buy_no['is_tracked']]
        tracked = buy_no[buy_no['is_tracked']]
        
        # 其他人的买入NO
        if not others.empty:
            fig.add_trace(
                go.Scatter(
                    x=others['time'],
                    y=others['price'],
                    mode='markers',
                    name='买入 NO',
                    marker=dict(
                        size=8,
                        color='#90EE90',  # 浅绿色
                        symbol='circle',
                        opacity=0.4,
                        line=dict(width=0)
                    ),
                    text=[f"<b>买入 NO</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(others['size'], others['price'], others['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    showlegend=True
                ),
                row=1, col=1
            )
        
        # 目标地址的买入NO
        if not tracked.empty:
            fig.add_trace(
                go.Scatter(
                    x=tracked['time'],
                    y=tracked['price'],
                    mode='markers',
                    name='⭐ 买入 NO (目标)',
                    marker=dict(
                        size=14,
                        color='#90EE90',
                        symbol='circle',
                        opacity=1.0,
                        line=dict(width=2, color='black')
                    ),
                    text=[f"<b>⭐ 买入 NO (目标)</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(tracked['size'], tracked['price'], tracked['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    showlegend=True
                ),
                row=1, col=1
            )
    
    # 3. 卖出 YES
    if not sell_yes.empty:
        others = sell_yes[~sell_yes['is_tracked']]
        tracked = sell_yes[sell_yes['is_tracked']]
        
        # 其他人的卖出YES
        if not others.empty:
            fig.add_trace(
                go.Scatter(
                    x=others['time'],
                    y=others['price'],
                    mode='markers',
                    name='卖出 YES',
                    marker=dict(
                        size=8,
                        color='#FF0000',  # 红色
                        symbol='triangle-down',
                        opacity=0.4,
                        line=dict(width=0)
                    ),
                    text=[f"<b>卖出 YES</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(others['size'], others['price'], others['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    showlegend=True
                ),
                row=1, col=1
            )
        
        # 目标地址的卖出YES
        if not tracked.empty:
            fig.add_trace(
                go.Scatter(
                    x=tracked['time'],
                    y=tracked['price'],
                    mode='markers',
                    name='⭐ 卖出 YES (目标)',
                    marker=dict(
                        size=14,
                        color='#FF0000',
                        symbol='triangle-down',
                        opacity=1.0,
                        line=dict(width=2, color='black')
                    ),
                    text=[f"<b>⭐ 卖出 YES (目标)</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(tracked['size'], tracked['price'], tracked['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    showlegend=True
                ),
                row=1, col=1
            )
    
    # 4. 卖出 NO
    if not sell_no.empty:
        others = sell_no[~sell_no['is_tracked']]
        tracked = sell_no[sell_no['is_tracked']]
        
        # 其他人的卖出NO
        if not others.empty:
            fig.add_trace(
                go.Scatter(
                    x=others['time'],
                    y=others['price'],
                    mode='markers',
                    name='卖出 NO',
                    marker=dict(
                        size=8,
                        color='#FFB6C1',  # 粉红色
                        symbol='square',
                        opacity=0.4,
                        line=dict(width=0)
                    ),
                    text=[f"<b>卖出 NO</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(others['size'], others['price'], others['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    showlegend=True
                ),
                row=1, col=1
            )
        
        # 目标地址的卖出NO
        if not tracked.empty:
            fig.add_trace(
                go.Scatter(
                    x=tracked['time'],
                    y=tracked['price'],
                    mode='markers',
                    name='⭐ 卖出 NO (目标)',
                    marker=dict(
                        size=14,
                        color='#FFB6C1',
                        symbol='square',
                        opacity=1.0,
                        line=dict(width=2, color='black')
                    ),
                    text=[f"<b>⭐ 卖出 NO (目标)</b><br>数量: {s:.0f} shares<br>价格: ${p:.3f}<br>金额: ${v:.2f}" 
                          for s, p, v in zip(tracked['size'], tracked['price'], tracked['value'])],
                    hovertemplate='%{text}<br>时间: %{x}<extra></extra>',
                    showlegend=True
                ),
                row=1, col=1
            )
    
    # 添加数量图（柱状图）
    for trade_type, trade_df, color, name in [
        ('buy_yes', buy_yes, '#00CC00', '买入 YES'),
        ('buy_no', buy_no, '#90EE90', '买入 NO'),
        ('sell_yes', sell_yes, '#FF0000', '卖出 YES'),
        ('sell_no', sell_no, '#FFB6C1', '卖出 NO'),
    ]:
        if not trade_df.empty:
            others = trade_df[~trade_df['is_tracked']]
            tracked = trade_df[trade_df['is_tracked']]
            
            if not others.empty:
                fig.add_trace(
                    go.Bar(
                        x=others['time'],
                        y=others['size'],
                        name=name,
                        marker=dict(color=color, opacity=0.4),
                        showlegend=False,
                        hovertemplate=f'{name}<br>数量: %{{y:.0f}}<br>时间: %{{x}}<extra></extra>'
                    ),
                    row=2, col=1
                )
            
            if not tracked.empty:
                fig.add_trace(
                    go.Bar(
                        x=tracked['time'],
                        y=tracked['size'],
                        name=f'⭐ {name} (目标)',
                        marker=dict(color=color, opacity=1.0, line=dict(width=1, color='black')),
                        showlegend=False,
                        hovertemplate=f'⭐ {name}<br>数量: %{{y:.0f}}<br>时间: %{{x}}<extra></extra>'
                    ),
                    row=2, col=1
                )
    
    # 更新布局
    fig.update_layout(
        title=dict(
            text=f"{market_title}<br><sub>所有交易（⭐ 高亮标记目标地址）</sub>",
            x=0.5,
            xanchor='center'
        ),
        height=800,
        hovermode='closest',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        barmode='stack'
    )
    
    fig.update_xaxes(title_text="时间", row=2, col=1)
    fig.update_yaxes(title_text="价格 ($)", row=1, col=1)
    fig.update_yaxes(title_text="数量 (shares)", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)


def display_market_analysis():
    """显示市场分析界面"""
    st.title("📊 市场交易分析")
    st.markdown("**新逻辑**：搜索市场 → 获取所有交易 → 标记目标地址")
    st.markdown("---")
    
    # 默认追踪地址
    DEFAULT_ADDRESS = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"
    
    # 步骤1: 搜索市场
    st.subheader("🔍 步骤1: 搜索市场")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_mode = st.radio(
            "搜索模式",
            options=["🔥 从地址交易中提取", "🔍 自定义关键词"],
            index=0,
            horizontal=True,
            help="推荐：从地址交易中提取市场（可获取最新的12月市场）"
        )
    
    with col2:
        if search_mode == "🔥 从地址交易中提取":
            crypto_type = st.selectbox(
                "加密货币",
                options=["BTC", "ETH", "SOL", "XRP"],
                index=0
            )
        else:
            market_status = st.radio(
                "市场状态",
                options=["🔴 已关闭", "🟢 活跃"],
                index=0,
                horizontal=True
            )
            closed = (market_status == "🔴 已关闭")
    
    with col3:
        if search_mode == "🔥 从地址交易中提取":
            time_range = st.selectbox(
                "时间范围",
                options=["最近1小时", "最近3小时", "最近6小时", "最近12小时", "最近24小时"],
                index=0,
                help="获取最近N小时内的交易"
            )
            # 转换为小时数
            hours_map = {
                "最近1小时": 1,
                "最近3小时": 3,
                "最近6小时": 6,
                "最近12小时": 12,
                "最近24小时": 24
            }
            hours = hours_map[time_range]
    
    # 参考地址输入（如果是从地址交易中提取）
    if search_mode == "🔥 从地址交易中提取":
        tracker_address = st.text_input(
            "参考地址",
            value=DEFAULT_ADDRESS,
            help="从这个地址的交易中提取市场"
        )
    
    if search_mode == "🔍 自定义关键词":
        keyword = st.text_input(
            "搜索关键词",
            value="BTC",
            placeholder="输入关键词，如 BTC, ETH, Trump 等"
        )
    else:
        keyword = None
    
    if st.button("🔍 搜索市场", use_container_width=True):
        with st.spinner("正在搜索市场..."):
            async def fetch_markets():
                async with MarketSearcher() as searcher:
                    if search_mode == "🔥 从地址交易中提取":
                        # 新方法：从地址交易中提取市场
                        return await searcher.get_markets_from_address_trades(
                            tracker_address,
                            crypto=crypto_type,
                            limit=50,
                            hours=hours
                        )
                    else:
                        # 旧方法：关键词搜索
                        return await searcher.search_markets_by_keyword(keyword, closed=closed, limit=100)
            
            markets = asyncio.run(fetch_markets())
            
            if markets:
                st.session_state.markets = markets
                if search_mode == "🔥 从地址交易中提取":
                    st.success(f"✓ 从地址最近 {hours} 小时的交易中提取到 {len(markets)} 个 {crypto_type} 15分钟市场")
                else:
                    st.success(f"✓ 找到 {len(markets)} 个市场")
            else:
                st.warning("未找到符合条件的市场")
    
    # 步骤2: 选择市场
    if 'markets' in st.session_state and st.session_state.markets:
        st.markdown("---")
        st.subheader("📋 步骤2: 选择市场")
        
        markets = st.session_state.markets
        
        # 显示市场列表
        market_options = []
        for m in markets:
            # 格式化结束时间
            if m.end_date:
                try:
                    from datetime import datetime
                    end_dt = datetime.fromisoformat(m.end_date.replace('Z', '+00:00'))
                    time_str = end_dt.strftime(' [%m-%d %H:%M]')
                except:
                    time_str = ''
            else:
                time_str = ''
            
            option = f"{m.status_text} {m.question[:70]}{time_str}"
            market_options.append(option)
        
        selected_idx = st.selectbox(
            "选择要分析的市场",
            range(len(market_options)),
            format_func=lambda i: market_options[i],
            key="market_selector"
        )
        
        selected_market = markets[selected_idx]
        
        # 显示市场详情
        with st.expander("📋 市场详情", expanded=False):
            # 格式化结束时间
            if selected_market.end_date:
                try:
                    from datetime import datetime
                    end_dt = datetime.fromisoformat(selected_market.end_date.replace('Z', '+00:00'))
                    end_time_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 计算距今时间
                    now = datetime.now(end_dt.tzinfo)
                    delta = now - end_dt
                    if delta.days > 0:
                        time_ago = f"{delta.days} 天前"
                    elif delta.seconds > 3600:
                        time_ago = f"{delta.seconds // 3600} 小时前"
                    elif delta.seconds > 60:
                        time_ago = f"{delta.seconds // 60} 分钟前"
                    else:
                        time_ago = "刚刚"
                    
                    end_time_display = f"{end_time_str} ({time_ago})"
                except:
                    end_time_display = selected_market.end_date
            else:
                end_time_display = "未知"
            
            st.markdown(f"""
            **问题**: {selected_market.question}
            
            **Condition ID**: `{selected_market.condition_id}`
            
            **状态**: {selected_market.status_text}
            
            **结束时间**: {end_time_display}
            
            **链接**: [在 Polymarket 上查看]({selected_market.market_url})
            """)
        
        # 步骤3: 输入目标地址并获取交易
        st.markdown("---")
        st.subheader("🎯 步骤3: 获取交易并标记目标地址")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            target_address = st.text_input(
                "目标地址（可选，用于高亮标记）",
                value=DEFAULT_ADDRESS,
                placeholder="0x... (留空则不标记)"
            )
        
        with col2:
            st.write("")
            st.write("")
            fetch_button = st.button("📊 获取并分析", use_container_width=True)
        
        st.caption("💡 输入地址后点击按钮，系统会获取该市场的所有交易，并高亮标记目标地址的交易")
        
        if fetch_button:
            with st.spinner("正在获取市场所有交易..."):
                # 获取所有交易
                async def fetch_all_trades():
                    async with AddressTracker() as tracker:
                        return await tracker.get_all_market_trades(
                            selected_market.condition_id,
                            max_trades=None,  # 获取全部
                            batch_size=1000
                        )
                
                all_trades = asyncio.run(fetch_all_trades())
                
                if all_trades:
                    st.session_state.all_trades = all_trades
                    st.session_state.selected_market = selected_market
                    st.session_state.target_address = target_address
                    
                    # 如果有目标地址，获取其代理钱包
                    tracked_wallets = None
                    if target_address and target_address.startswith("0x"):
                        with st.spinner("正在获取目标地址的代理钱包..."):
                            async def get_proxy_wallets():
                                async with AddressTracker() as tracker:
                                    trades = await tracker.get_address_trades(target_address, limit=100)
                                    analysis = tracker.analyze_trades(trades)
                                    return set(analysis['proxy_wallets'])
                            
                            tracked_wallets = asyncio.run(get_proxy_wallets())
                            st.session_state.tracked_wallets = tracked_wallets
                    
                    st.success(f"✓ 获取到 {len(all_trades):,} 笔交易")
                else:
                    st.warning("该市场没有交易数据")
        
        # 步骤4: 显示分析结果
        if 'all_trades' in st.session_state and st.session_state.all_trades:
            st.markdown("---")
            st.subheader("📊 步骤4: 交易分析")
            
            all_trades = st.session_state.all_trades
            selected_market = st.session_state.selected_market
            target_address = st.session_state.target_address
            tracked_wallets = st.session_state.get('tracked_wallets', None)
            
            # 统计信息
            all_traders = set(t.proxy_wallet for t in all_trades)
            buy_count = len([t for t in all_trades if t.side == 'BUY'])
            sell_count = len([t for t in all_trades if t.side == 'SELL'])
            
            # 统计目标地址的交易
            target_trades_count = 0
            if tracked_wallets:
                target_trades_count = len([t for t in all_trades if t.proxy_wallet in tracked_wallets])
            
            # 显示统计
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("总交易数", f"{len(all_trades):,}")
            with col2:
                st.metric("交易者数", len(all_traders))
            with col3:
                st.metric("买入交易", buy_count)
            with col4:
                st.metric("卖出交易", sell_count)
            with col5:
                if target_trades_count > 0:
                    st.metric("⭐ 目标地址", target_trades_count)
                else:
                    st.metric("目标地址", "未输入")
            
            # 显示目标地址信息
            if tracked_wallets and target_trades_count > 0:
                st.success(f"✓ 在 {len(all_trades):,} 笔交易中找到目标地址的 {target_trades_count} 笔交易")
                
                with st.expander("🎯 目标地址信息", expanded=False):
                    st.markdown(f"""
                    **主地址**: `{target_address}`
                    
                    **关联的代理钱包** ({len(tracked_wallets)} 个):
                    """)
                    for wallet in tracked_wallets:
                        st.code(wallet, language=None)
            elif target_address and target_address.startswith("0x"):
                st.info("ℹ️ 该地址在此市场没有交易记录")
            
            # 详细统计
            with st.expander("📊 市场交易详细统计", expanded=False):
                # 价格统计
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
                start_time = datetime.fromtimestamp(min(timestamps))
                end_time = datetime.fromtimestamp(max(timestamps))
                duration = (max(timestamps) - min(timestamps)) // 60
                
                st.markdown(f"""
                **时间范围**：
                - 开始：{start_time.strftime('%Y-%m-%d %H:%M:%S')}
                - 结束：{end_time.strftime('%Y-%m-%d %H:%M:%S')}
                - 持续：{duration:.0f} 分钟
                """)
                
                # 目标地址统计
                if tracked_wallets and target_trades_count > 0:
                    target_trades = [t for t in all_trades if t.proxy_wallet in tracked_wallets]
                    target_buy = len([t for t in target_trades if t.side == 'BUY'])
                    target_sell = len([t for t in target_trades if t.side == 'SELL'])
                    target_volume = sum(t.value for t in target_trades)
                    
                    st.markdown(f"""
                    **目标地址统计**：
                    - 总交易：{target_trades_count} 笔
                    - 买入：{target_buy} 笔
                    - 卖出：{target_sell} 笔
                    - 交易额：${target_volume:,.2f}
                    - 占比：{target_trades_count/len(all_trades)*100:.2f}%
                    """)
            
            # 图表
            st.markdown("---")
            st.subheader("📈 交易时间序列")
            
            create_all_trades_chart_with_highlight(
                all_trades,
                selected_market.question,
                target_address,
                tracked_wallets
            )
            
            # 导出功能
            st.markdown("---")
            st.subheader("📥 导出数据")
            
            export_data = []
            for t in all_trades:
                is_target = tracked_wallets is not None and t.proxy_wallet in tracked_wallets
                export_data.append({
                    '时间': datetime.fromtimestamp(t.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                    '方向': t.side,
                    '价格': t.price,
                    '数量': t.size,
                    '金额': t.value,
                    '是否为目标地址': '⭐ 是' if is_target else '否',
                    '钱包地址': t.proxy_wallet,
                    '市场标题': t.title,
                    '市场链接': t.market_url
                })
            
            df_export = pd.DataFrame(export_data)
            csv = df_export.to_csv(index=False).encode('utf-8-sig')
            
            st.download_button(
                label=f"📥 下载 CSV ({len(all_trades):,} 笔交易)",
                data=csv,
                file_name=f"market_{selected_market.condition_id[:8]}_all_trades.csv",
                mime="text/csv",
                help="下载该市场的所有交易数据为CSV文件（包含目标地址标记）",
                use_container_width=True
            )


if __name__ == "__main__":
    display_market_analysis()


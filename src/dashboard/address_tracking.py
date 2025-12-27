"""
地址追踪 Dashboard 组件
显示特定地址的交易历史和分析
"""
import streamlit as st
import asyncio
from datetime import datetime
from typing import Optional
import pandas as pd

from ..market.address_tracker import AddressTracker


def format_timestamp(ts: int) -> str:
    """格式化时间戳"""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def display_address_tracking():
    """显示地址追踪界面"""
    st.title("🔍 地址追踪")
    st.markdown("---")
    
    # 默认地址
    DEFAULT_ADDRESS = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"
    
    # 输入地址
    col1, col2 = st.columns([3, 1])
    
    with col1:
        address = st.text_input(
            "输入要追踪的以太坊地址",
            value=DEFAULT_ADDRESS,
            placeholder="0x...",
            help="输入以太坊地址（0x开头）来追踪其在 Polymarket 的交易活动"
        )
    
    with col2:
        st.write("")  # 占位
        st.write("")  # 占位
        track_button = st.button("🔍 追踪", use_container_width=True)
    
    # 示例地址
    st.caption("💡 已填充默认地址，点击追踪按钮开始分析")
    
    # 如果点击追踪按钮
    if track_button and address:
        if not address.startswith("0x") or len(address) != 42:
            st.error("❌ 请输入有效的以太坊地址（0x开头，42字符）")
            return
        
        # 显示加载状态
        with st.spinner(f"正在获取地址 {address} 的交易数据..."):
            # 运行异步任务
            try:
                trades = asyncio.run(fetch_trades(address))
                
                if not trades:
                    st.warning("❌ 未找到该地址的交易记录")
                    return
                
                # 分析交易数据
                tracker = AddressTracker()
                analysis = tracker.analyze_trades(trades)
                
                # 显示统计信息
                st.success(f"✓ 找到 {analysis['total_trades']} 笔交易")
                
                # 显示概览卡片
                display_overview(analysis, address)
                
                st.markdown("---")
                
                # 显示最近交易
                display_recent_trades(trades)
                
                st.markdown("---")
                
                # 显示按市场分组的统计
                display_market_stats(analysis)
                
            except Exception as e:
                st.error(f"❌ 获取数据失败: {e}")
                import traceback
                st.code(traceback.format_exc())


async def fetch_trades(address: str):
    """异步获取交易数据"""
    async with AddressTracker() as tracker:
        trades = await tracker.get_address_trades(address, limit=100)
        return trades


def display_overview(analysis: dict, address: str):
    """显示概览信息"""
    st.subheader("📊 交易概览")
    
    # 第一行：基本统计
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="总交易数",
            value=f"{analysis['total_trades']}",
            help="总交易笔数"
        )
    
    with col2:
        st.metric(
            label="买入交易",
            value=f"{analysis['buy_trades']}",
            delta=f"{analysis['buy_trades']/analysis['total_trades']*100:.1f}%",
            help="买入交易数量和占比"
        )
    
    with col3:
        st.metric(
            label="卖出交易",
            value=f"{analysis['sell_trades']}",
            delta=f"{analysis['sell_trades']/analysis['total_trades']*100:.1f}%",
            help="卖出交易数量和占比"
        )
    
    with col4:
        st.metric(
            label="涉及市场",
            value=f"{analysis['markets_count']}",
            help="参与交易的市场数量"
        )
    
    # 第二行：交易金额
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="买入总额",
            value=f"${analysis['total_buy_volume']:,.2f}",
            help="所有买入交易的总金额"
        )
    
    with col2:
        st.metric(
            label="卖出总额",
            value=f"${analysis['total_sell_volume']:,.2f}",
            help="所有卖出交易的总金额"
        )
    
    with col3:
        net_volume = analysis['net_volume']
        delta_color = "normal" if net_volume >= 0 else "inverse"
        st.metric(
            label="净投入",
            value=f"${abs(net_volume):,.2f}",
            delta="买入" if net_volume >= 0 else "卖出",
            delta_color=delta_color,
            help="买入金额 - 卖出金额"
        )
    
    # 代理钱包信息
    if analysis.get('proxy_wallets'):
        with st.expander("📋 代理钱包地址"):
            for wallet in analysis['proxy_wallets']:
                st.code(wallet, language=None)


def display_recent_trades(trades: list):
    """显示最近的交易"""
    st.subheader("📝 最近的交易")
    
    # 限制显示数量
    display_count = min(20, len(trades))
    st.caption(f"显示最近 {display_count} 笔交易")
    
    # 创建表格数据
    table_data = []
    for trade in trades[:display_count]:
        side_emoji = "🟢" if trade.side == "BUY" else "🔴"
        
        table_data.append({
            "时间": format_timestamp(trade.timestamp),
            "方向": f"{side_emoji} {trade.side}",
            "市场": trade.title[:50] + "..." if len(trade.title) > 50 else trade.title,
            "数量": f"{trade.size:,.0f}",
            "价格": f"${trade.price:.3f}",
            "金额": f"${trade.value:,.2f}",
            "链接": trade.market_url
        })
    
    # 显示表格
    df = pd.DataFrame(table_data)
    
    # 使用 st.dataframe 以便可以点击链接
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "链接": st.column_config.LinkColumn(
                "市场链接",
                display_text="查看"
            )
        }
    )


def display_market_stats(analysis: dict):
    """显示按市场分组的统计"""
    st.subheader("📈 按市场统计")
    
    markets = analysis.get('markets', {})
    
    if not markets:
        st.info("没有市场数据")
        return
    
    st.caption(f"共 {len(markets)} 个市场")
    
    # 按交易次数排序
    sorted_markets = sorted(
        markets.items(),
        key=lambda x: len(x[1]['trades']),
        reverse=True
    )
    
    # 限制显示数量
    display_count = min(10, len(sorted_markets))
    
    # 创建表格数据
    table_data = []
    for i, (condition_id, market_info) in enumerate(sorted_markets[:display_count], 1):
        table_data.append({
            "#": i,
            "市场": market_info['title'][:50] + "..." if len(market_info['title']) > 50 else market_info['title'],
            "交易次数": len(market_info['trades']),
            "买入": f"{market_info['buy_count']} (${market_info['buy_volume']:,.2f})",
            "卖出": f"{market_info['sell_count']} (${market_info['sell_volume']:,.2f})",
            "净值": f"${market_info['buy_volume'] - market_info['sell_volume']:,.2f}",
            "链接": f"https://polymarket.com/event/{market_info['slug']}"
        })
    
    df = pd.DataFrame(table_data)
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "链接": st.column_config.LinkColumn(
                "市场链接",
                display_text="查看"
            )
        }
    )
    
    if len(sorted_markets) > display_count:
        st.caption(f"还有 {len(sorted_markets) - display_count} 个市场未显示")


if __name__ == "__main__":
    # 用于测试
    display_address_tracking()


"""
地址追踪使用示例
演示如何使用 AddressTracker 模块
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.market.address_tracker import AddressTracker

# 默认追踪地址
DEFAULT_ADDRESS = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"


async def example_basic_tracking():
    """示例 1: 基本的地址追踪"""
    print("=" * 80)
    print("示例 1: 基本的地址追踪")
    print("=" * 80)
    
    address = DEFAULT_ADDRESS
    
    async with AddressTracker() as tracker:
        # 获取交易历史
        trades = await tracker.get_address_trades(address, limit=50)
        
        if trades:
            print(f"\n✓ 找到 {len(trades)} 笔交易")
            
            # 显示最近 5 笔交易
            print(f"\n最近 5 笔交易:")
            for i, trade in enumerate(trades[:5], 1):
                side_emoji = "🟢" if trade.side == "BUY" else "🔴"
                print(f"\n{i}. {side_emoji} {trade.side}")
                print(f"   市场: {trade.title[:60]}")
                print(f"   数量: {trade.size:,.0f} @ ${trade.price:.3f} = ${trade.value:,.2f}")
                print(f"   时间: {trade.datetime}")
        else:
            print("❌ 未找到交易记录")


async def example_trade_analysis():
    """示例 2: 交易数据分析"""
    print("\n\n" + "=" * 80)
    print("示例 2: 交易数据分析")
    print("=" * 80)
    
    address = DEFAULT_ADDRESS
    
    async with AddressTracker() as tracker:
        # 获取交易历史
        trades = await tracker.get_address_trades(address)
        
        if trades:
            # 分析交易数据
            analysis = tracker.analyze_trades(trades)
            
            print(f"\n📊 交易统计:")
            print(f"   总交易数: {analysis['total_trades']}")
            print(f"   买入交易: {analysis['buy_trades']} 笔")
            print(f"   卖出交易: {analysis['sell_trades']} 笔")
            print(f"\n💰 交易金额:")
            print(f"   买入总额: ${analysis['total_buy_volume']:,.2f}")
            print(f"   卖出总额: ${analysis['total_sell_volume']:,.2f}")
            print(f"   净投入: ${analysis['net_volume']:,.2f}")
            print(f"\n🎯 市场分布:")
            print(f"   涉及市场数: {analysis['markets_count']}")
            
            # 显示前 3 个交易最多的市场
            markets = analysis['markets']
            sorted_markets = sorted(
                markets.items(),
                key=lambda x: len(x[1]['trades']),
                reverse=True
            )
            
            print(f"\n   交易最多的 3 个市场:")
            for i, (condition_id, market_info) in enumerate(sorted_markets[:3], 1):
                print(f"\n   {i}. {market_info['title'][:60]}")
                print(f"      交易次数: {len(market_info['trades'])}")
                print(f"      买入: {market_info['buy_count']} 笔 (${market_info['buy_volume']:,.2f})")
                print(f"      卖出: {market_info['sell_count']} 笔 (${market_info['sell_volume']:,.2f})")
            
            # 最新交易
            if analysis['latest_trade']:
                latest = analysis['latest_trade']
                print(f"\n⏰ 最新交易:")
                print(f"   市场: {latest.title[:60]}")
                print(f"   方向: {latest.side}")
                print(f"   数量: {latest.size:,.0f} @ ${latest.price:.3f}")
                print(f"   时间: {latest.datetime}")


async def example_market_comparison():
    """示例 3: 市场交易对比（自己 vs 其他人）"""
    print("\n\n" + "=" * 80)
    print("示例 3: 市场交易对比")
    print("=" * 80)
    
    address = DEFAULT_ADDRESS
    
    async with AddressTracker() as tracker:
        # 1. 获取自己的交易
        my_trades = await tracker.get_address_trades(address, limit=100)
        
        if not my_trades:
            print("❌ 未找到交易记录")
            return
        
        # 分析自己的交易
        my_analysis = tracker.analyze_trades(my_trades)
        
        # 2. 选择一个市场，获取该市场的所有交易
        if my_analysis['markets']:
            # 选择交易最多的市场
            sorted_markets = sorted(
                my_analysis['markets'].items(),
                key=lambda x: len(x[1]['trades']),
                reverse=True
            )
            
            condition_id, my_market_info = sorted_markets[0]
            
            print(f"\n🎯 分析市场: {my_market_info['title'][:60]}")
            print(f"   Condition ID: {condition_id[:20]}...")
            
            # 获取该市场的所有交易
            market_trades = await tracker.get_market_trades(condition_id, limit=100)
            
            if market_trades:
                print(f"\n✓ 该市场共有 {len(market_trades)} 笔交易（最近100笔）")
                
                # 统计所有交易者
                traders = {}
                for trade in market_trades:
                    wallet = trade.proxy_wallet
                    if wallet not in traders:
                        traders[wallet] = {
                            'buy_count': 0,
                            'sell_count': 0,
                            'buy_volume': 0,
                            'sell_volume': 0
                        }
                    
                    if trade.side == "BUY":
                        traders[wallet]['buy_count'] += 1
                        traders[wallet]['buy_volume'] += trade.value
                    else:
                        traders[wallet]['sell_count'] += 1
                        traders[wallet]['sell_volume'] += trade.value
                
                print(f"\n📊 市场统计:")
                print(f"   总交易者数: {len(traders)}")
                print(f"   总交易笔数: {len(market_trades)}")
                
                # 找到自己的代理钱包
                my_wallet = None
                for trade in my_trades:
                    if trade.condition_id == condition_id:
                        my_wallet = trade.proxy_wallet
                        break
                
                if my_wallet and my_wallet in traders:
                    my_stats = traders[my_wallet]
                    
                    print(f"\n💼 你的交易:")
                    print(f"   代理钱包: {my_wallet}")
                    print(f"   买入: {my_stats['buy_count']} 笔 (${my_stats['buy_volume']:,.2f})")
                    print(f"   卖出: {my_stats['sell_count']} 笔 (${my_stats['sell_volume']:,.2f})")
                    
                    # 计算排名
                    sorted_buyers = sorted(
                        traders.items(),
                        key=lambda x: x[1]['buy_volume'],
                        reverse=True
                    )
                    
                    my_rank = next(
                        (i for i, (w, _) in enumerate(sorted_buyers, 1) if w == my_wallet),
                        None
                    )
                    
                    if my_rank:
                        print(f"\n🏆 排名:")
                        print(f"   买入金额排名: 第 {my_rank} / {len(traders)}")
                        
                        # 显示前 3 名
                        print(f"\n   买入金额排行榜 (前3名):")
                        for i, (wallet, stats) in enumerate(sorted_buyers[:3], 1):
                            is_me = "⭐ (你)" if wallet == my_wallet else ""
                            print(f"   {i}. {wallet[:10]}... ${stats['buy_volume']:,.2f} {is_me}")


async def example_filter_trades():
    """示例 4: 筛选特定类型的交易"""
    print("\n\n" + "=" * 80)
    print("示例 4: 筛选特定类型的交易")
    print("=" * 80)
    
    address = DEFAULT_ADDRESS
    
    async with AddressTracker() as tracker:
        trades = await tracker.get_address_trades(address)
        
        if trades:
            # 筛选 BTC 相关市场的交易
            btc_trades = [
                t for t in trades
                if 'bitcoin' in t.title.lower() or 'btc' in t.title.lower()
            ]
            
            print(f"\n📊 BTC 相关交易: {len(btc_trades)} 笔")
            
            if btc_trades:
                btc_analysis = tracker.analyze_trades(btc_trades)
                print(f"   买入: {btc_analysis['buy_trades']} 笔 (${btc_analysis['total_buy_volume']:,.2f})")
                print(f"   卖出: {btc_analysis['sell_trades']} 笔 (${btc_analysis['total_sell_volume']:,.2f})")
            
            # 筛选大额交易（>$50）
            large_trades = [t for t in trades if t.value > 50]
            
            print(f"\n💰 大额交易 (>$50): {len(large_trades)} 笔")
            
            if large_trades:
                total_large_value = sum(t.value for t in large_trades)
                print(f"   总金额: ${total_large_value:,.2f}")
                print(f"   占比: {total_large_value / sum(t.value for t in trades) * 100:.1f}%")
            
            # 筛选最近 1 小时的交易
            import time
            one_hour_ago = int(time.time()) - 3600
            recent_trades = [t for t in trades if t.timestamp > one_hour_ago]
            
            print(f"\n⏰ 最近 1 小时的交易: {len(recent_trades)} 笔")
            
            if recent_trades:
                for i, trade in enumerate(recent_trades[:3], 1):
                    print(f"\n   {i}. {trade.side} - {trade.title[:50]}")
                    print(f"      ${trade.value:,.2f} - {trade.datetime}")


async def main():
    """主函数 - 运行所有示例"""
    print("\n" + "🔍" * 40)
    print("Polymarket 地址追踪 - 使用示例")
    print("🔍" * 40)
    
    try:
        # 运行所有示例
        await example_basic_tracking()
        await example_trade_analysis()
        await example_market_comparison()
        await example_filter_trades()
        
        print("\n\n" + "=" * 80)
        print("✅ 所有示例运行完成！")
        print("=" * 80)
        
        print("""
💡 提示：
1. 修改代码中的地址来追踪其他用户
2. 调整 limit 参数来获取更多或更少的交易
3. 使用 analyze_trades() 来分析任何交易列表
4. 可以将这些功能集成到你的交易策略中
        """)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())


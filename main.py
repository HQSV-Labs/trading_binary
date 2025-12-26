"""
主程序：15分钟预测市场双边对冲套利 Bot
连接真实的 Polymarket API 检测 BTC/ETH 15分钟涨跌市场
"""
import asyncio
import logging
from rich.live import Live
from rich.console import Console

from config import Config
from src.core.position import PairPosition
from src.market.polymarket_api import PolymarketAPI
from src.market.event_detector import EventDetector
from src.monitor.price_monitor import PriceMonitor
from src.execution.order_manager import OrderManager
from src.rebalancing.balancer import Rebalancer
from src.dashboard.display import Dashboard
from src.dashboard.market_selector import MarketSelector
from src.market.demo_data import create_demo_markets, create_demo_orderbook, update_demo_orderbook
from typing import Optional

# 配置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingBot:
    """交易机器人主类"""
    
    def __init__(self):
        self.position = PairPosition()
        self.api = PolymarketAPI(api_key=Config.POLYMARKET_API_KEY)
        self.event_detector = EventDetector(self.api)
        self.order_manager: Optional[OrderManager] = None
        self.monitor = PriceMonitor(
            entry_price_min=Config.ENTRY_PRICE_MIN,
            entry_price_max=Config.ENTRY_PRICE_MAX,
            callback=self.on_price_alert
        )
        self.rebalancer = Rebalancer(imbalance_threshold=Config.IMBALANCE_THRESHOLD)
        self.dashboard = Dashboard(self.position, self.event_detector, order_manager=None)
        self.console = Console()
        self.is_trading = True
        self.current_market = None
        
    def on_price_alert(self, side: str, price: float, order_book):
        """价格预警回调"""
        if not self.is_trading or not self.order_manager:
            return
        
        # 检查是否已锁定利润
        if self.position.is_profitable():
            self.is_trading = False
            self.dashboard.add_trade_log("✅ 利润已锁定！停止交易")
            return
        
        # 检查准入条件
        qty = Config.DEFAULT_ORDER_SIZE
        if not self.position.can_buy(side, qty, price):
            self.dashboard.add_trade_log(f"⚠️  {side} 价格 {price:.4f} 不满足准入条件")
            return
        
        # 计算目标价格
        opposite_side = "NO" if side == "YES" else "YES"
        opposite_avg = getattr(self.position, opposite_side.lower()).avg_price
        target_price = self.order_manager.calculate_target_price(side, opposite_avg)
        
        # 记录交易日志
        self.dashboard.add_trade_log(f"🟢 触发买入信号: {side} @ ${price:.4f} (目标价: ${target_price:.4f})")
        
        # 模拟下单
        asyncio.create_task(
            self._place_order_with_log(side, qty, target_price)
        )
    
    async def _place_order_with_log(self, side: str, qty: float, max_price: float):
        """下单并记录日志"""
        if not self.order_manager:
            return
        
        order = await self.order_manager.place_limit_order(side, qty, max_price)
        if order and order.status.value == "filled":
            self.dashboard.add_trade_log(
                f"✅ 模拟成交: {side} {order.filled_qty:.2f} @ ${order.filled_price:.4f} "
                f"(成本: ${order.filled_qty * order.filled_price:.2f})"
            )
    
    async def on_orderbook_update(self, orderbook):
        """订单簿更新回调"""
        # 更新订单管理器
        if self.order_manager:
            self.order_manager.update_orderbook(orderbook)
        
        # 监控价格
        self.monitor.check_price(orderbook)
        
        # 更新 Dashboard
        self.dashboard.current_orderbook = orderbook
    
    async def trading_loop(self):
        """主交易循环"""
        while self.is_trading:
            if not self.order_manager or not self.order_manager.current_orderbook:
                await asyncio.sleep(0.1)
                continue
            
            order_book = self.order_manager.current_orderbook
            
            # 检查利润锁定
            if self.position.is_profitable():
                self.is_trading = False
                await self.order_manager.cancel_all_orders()
                break
            
            # 动态平衡
            if self.rebalancer.should_rebalance(self.position):
                priority_side = self.rebalancer.get_priority_side(self.position)
                price = order_book.yes_mid_price if priority_side == "YES" else order_book.no_mid_price
                
                if Config.ENTRY_PRICE_MIN <= price <= Config.ENTRY_PRICE_MAX:
                    qty = Config.REBALANCE_ORDER_SIZE
                    opposite_side = "NO" if priority_side == "YES" else "YES"
                    opposite_avg = getattr(self.position, opposite_side.lower()).avg_price
                    target_price = self.order_manager.calculate_target_price(priority_side, opposite_avg)
                    
                    if self.position.can_buy(priority_side, qty, price):
                        self.dashboard.add_trade_log(f"⚖️  平衡交易: {priority_side} @ ${price:.4f}")
                        order = await self.order_manager.place_limit_order(priority_side, qty, target_price)
                        if order and order.status.value == "filled":
                            self.dashboard.add_trade_log(
                                f"✅ 平衡成交: {priority_side} {order.filled_qty:.2f} @ ${order.filled_price:.4f}"
                            )
            
            await asyncio.sleep(0.1)  # 100ms 循环
    
    async def run(self, demo_mode: bool = False):
        """
        运行机器人
        
        Args:
            demo_mode: 如果为 True，使用演示数据（当 API 不可用时）
        """
        self.console.print("[bold blue]🚀 启动交易机器人...[/bold blue]")
        
        if demo_mode:
            self.console.print("[yellow]⚠️  演示模式：使用模拟数据展示可视化界面[/yellow]")
            markets = create_demo_markets()
        else:
            async with self.api:
                # 检测 BTC/ETH 15分钟涨跌市场
                self.console.print("[cyan]正在检测 BTC/ETH 15分钟涨跌市场...[/cyan]")
                markets = await self.event_detector.detect_btc_eth_markets()
                
                if not markets:
                    self.console.print("[yellow]⚠️  API 无法访问，切换到演示模式...[/yellow]")
                    demo_mode = True
                    markets = create_demo_markets()
        
        if not markets:
            self.console.print("[red]❌ 未找到符合条件的市场[/red]")
            return
        
        # 使用市场选择器让用户选择
        selector = MarketSelector(self.console)
        self.current_market = selector.display_markets(markets)
        
        if not self.current_market:
            self.console.print("[red]❌ 未选择市场，退出程序[/red]")
            return
        
        self.console.print(f"[cyan]市场 ID: {self.current_market.market_id}[/cyan]")
        if demo_mode:
            self.console.print("[yellow]📊 演示模式：使用模拟订单簿数据[/yellow]")
        self.console.print("[dim]正在加载市场数据...[/dim]\n")
        
        # 初始化订单管理器
        self.order_manager = OrderManager(
            self.api,
            self.current_market.condition_id,
            self.position
        )
            
        # 更新 Dashboard 的 order_manager 引用
        self.dashboard.order_manager = self.order_manager
        self.dashboard.add_trade_log(f"✅ 已选择市场: {self.current_market.question}")
        self.dashboard.add_trade_log("🔶 模拟交易模式已启动 - 不会真实下单")
        
        # 启动交易循环
        trading_task = asyncio.create_task(self.trading_loop())
        
        # 启动 Dashboard
        if demo_mode:
            # 使用演示数据
            initial_orderbook = create_demo_orderbook()
        else:
            async with self.api:
                initial_orderbook = await self.api.get_orderbook(self.current_market.condition_id)
        
        if not initial_orderbook and not demo_mode:
            self.console.print("[yellow]⚠️  无法获取订单簿，切换到演示模式...[/yellow]")
            demo_mode = True
            initial_orderbook = create_demo_orderbook()
        
        if initial_orderbook:
            self.dashboard.current_orderbook = initial_orderbook
            self.order_manager.update_orderbook(initial_orderbook)
        
        with Live(
            self.dashboard.create_layout(initial_orderbook or self.dashboard.current_orderbook),
            refresh_per_second=10
        ) as live:
                monitor_task = None
                try:
                    # 监控市场订单簿
                    if demo_mode:
                        # 演示模式：模拟订单簿更新
                        async def demo_orderbook_updater():
                            while self.is_trading:
                                updated_orderbook = update_demo_orderbook(self.dashboard.current_orderbook)
                                await self.on_orderbook_update(updated_orderbook)
                                await asyncio.sleep(0.5)  # 每0.5秒更新一次
                        
                        monitor_task = asyncio.create_task(demo_orderbook_updater())
                    else:
                        monitor_task = asyncio.create_task(
                            self.event_detector.monitor_market(
                                self.current_market,
                                self.on_orderbook_update,
                                update_interval=0.1
                            )
                        )
                    
                    # 更新 Dashboard
                    while self.is_trading:
                        if self.dashboard.current_orderbook:
                            layout = await self.dashboard.update(self.dashboard.current_orderbook)
                            live.update(layout)
                        await asyncio.sleep(0.1)
                        
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]⚠️  用户中断[/yellow]")
                finally:
                    self.is_trading = False
                    if trading_task and not trading_task.done():
                        trading_task.cancel()
                    if monitor_task and not monitor_task.done():
                        monitor_task.cancel()
                    
                    try:
                        tasks = [t for t in [trading_task, monitor_task] if t]
                        if tasks:
                            await asyncio.gather(*tasks, return_exceptions=True)
                    except:
                        pass
                    
                    # 显示最终结果
                    self.console.print("\n[bold]📊 最终结果:[/bold]")
                    self.console.print(f"YES 持仓: {self.position.yes.qty:.2f} @ ${self.position.yes.avg_price:.4f}")
                    self.console.print(f"NO 持仓: {self.position.no.qty:.2f} @ ${self.position.no.avg_price:.4f}")
                    self.console.print(f"总成本: ${self.position.total_cost:.2f}")
                    self.console.print(f"配对成本: {self.position.pair_cost:.4f}")
                    self.console.print(f"利润状态: {'✅ 已锁定' if self.position.is_profitable() else '❌ 未锁定'}")


async def main():
    """主函数"""
    import sys
    
    # 检查是否使用演示模式
    demo_mode = "--demo" in sys.argv or "-d" in sys.argv
    
    bot = TradingBot()
    await bot.run(demo_mode=demo_mode)


if __name__ == "__main__":
    asyncio.run(main())

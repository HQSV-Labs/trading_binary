"""
实时监控面板：显示 Pair Cost 等关键指标
"""
import asyncio
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from src.core.position import PairPosition
from src.market.polymarket_api import OrderBook
from src.market.event_detector import EventDetector
from src.execution.order_manager import OrderManager
from typing import List


class Dashboard:
    """监控面板"""
    
    def __init__(self, position: PairPosition, event_detector: EventDetector, order_manager: Optional[OrderManager] = None):
        self.position = position
        self.event_detector = event_detector
        self.order_manager = order_manager
        self.console = Console()
        self.history = []  # 存储历史数据用于图表
        self.current_orderbook: Optional[OrderBook] = None
        self.trade_logs: List[str] = []  # 交易日志
        self.price_history: List[dict] = []  # 价格历史（用于图表）
    
    def create_layout(self, order_book: OrderBook) -> Layout:
        """创建布局"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=8)
        )
        
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        layout["left"].split_column(
            Layout(name="price_chart", size=12),
            Layout(name="position", size=12),
            Layout(name="trades")
        )
        
        layout["right"].split_column(
            Layout(name="market", size=10),
            Layout(name="params", size=10),
            Layout(name="logs")
        )
        
        # Header
        market_info = self.event_detector.get_market_info()
        header_text = Text("📊 15分钟预测市场双边对冲套利 Bot [模拟模式]", style="bold blue")
        if market_info:
            header_text.append(f" | {market_info['question'][:60]}", style="cyan")
        layout["header"].update(Panel(header_text, border_style="blue"))
        
        # Price Chart Panel
        price_chart = self._create_price_chart(order_book)
        layout["price_chart"].update(Panel(price_chart, title="📈 实时价格", border_style="cyan"))
        
        # Position Panel
        pos_table = self._create_position_table()
        layout["position"].update(Panel(pos_table, title="💼 持仓信息", border_style="green"))
        
        # Trades Panel
        trades_table = self._create_trades_table()
        layout["trades"].update(Panel(trades_table, title="🔄 交易历史", border_style="yellow"))
        
        # Market Panel
        market_table = self._create_market_table(order_book)
        layout["market"].update(Panel(market_table, title="📊 市场行情", border_style="blue"))
        
        # Parameters Panel
        params_table = self._create_parameters_table()
        layout["params"].update(Panel(params_table, title="⚙️  执行参数", border_style="magenta"))
        
        # Logs Panel
        logs_text = self._create_logs_text()
        layout["logs"].update(Panel(logs_text, title="📝 实时日志", border_style="dim"))
        
        # Footer
        footer_text = self._create_footer_text()
        layout["footer"].update(Panel(footer_text, title="⚡ 状态", border_style="yellow"))
        
        return layout
    
    def _create_position_table(self) -> Table:
        """创建持仓表格"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("项目", style="cyan")
        table.add_column("YES", justify="right")
        table.add_column("NO", justify="right")
        table.add_column("总计", justify="right")
        
        table.add_row(
            "持仓数量",
            f"{self.position.yes.qty:.2f}",
            f"{self.position.no.qty:.2f}",
            f"{self.position.yes.qty + self.position.no.qty:.2f}"
        )
        
        table.add_row(
            "总成本 ($)",
            f"${self.position.yes.cost:.2f}",
            f"${self.position.no.cost:.2f}",
            f"${self.position.total_cost:.2f}"
        )
        
        table.add_row(
            "平均价格",
            f"{self.position.yes.avg_price:.4f}",
            f"{self.position.no.avg_price:.4f}",
            "-"
        )
        
        pair_cost = self.position.pair_cost
        table.add_row(
            "配对成本",
            "-",
            "-",
            f"{pair_cost:.4f}",
            style="bold green" if pair_cost < 0.98 else "bold red"
        )
        
        min_qty = self.position.min_qty
        total_cost = self.position.total_cost
        profit_status = "✅ 已锁定利润" if self.position.is_profitable() else "⏳ 等待中"
        table.add_row(
            "利润状态",
            f"最小持仓: {min_qty:.2f}",
            f"总成本: ${total_cost:.2f}",
            profit_status,
            style="bold green" if self.position.is_profitable() else "yellow"
        )
        
        imbalance = self.position.get_imbalance_ratio() * 100
        table.add_row(
            "不平衡度",
            "-",
            "-",
            f"{imbalance:.1f}%",
            style="yellow" if imbalance > 20 else "green"
        )
        
        return table
    
    def _create_market_table(self, order_book: OrderBook) -> Table:
        """创建市场行情表格"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("方向", style="cyan")
        table.add_column("中间价", justify="right")
        table.add_column("最佳买价", justify="right")
        table.add_column("最佳卖价", justify="right")
        table.add_column("状态", justify="center")
        
        yes_mid = order_book.yes_mid_price
        no_mid = order_book.no_mid_price
        yes_best_ask = order_book.yes_asks[0].price if order_book.yes_asks else 0.0
        no_best_ask = order_book.no_asks[0].price if order_book.no_asks else 0.0
        yes_best_bid = order_book.yes_bids[0].price if order_book.yes_bids else 0.0
        no_best_bid = order_book.no_bids[0].price if order_book.no_bids else 0.0
        
        # YES 状态
        yes_status = "🟢 可买入" if 0.35 <= yes_mid <= 0.50 else "⚪ 等待"
        table.add_row(
            "YES",
            f"{yes_mid:.4f}",
            f"{yes_best_bid:.4f}",
            f"{yes_best_ask:.4f}",
            yes_status
        )
        
        # NO 状态
        no_status = "🟢 可买入" if 0.35 <= no_mid <= 0.50 else "⚪ 等待"
        table.add_row(
            "NO",
            f"{no_mid:.4f}",
            f"{no_best_bid:.4f}",
            f"{no_best_ask:.4f}",
            no_status
        )
        
        return table
    
    def _create_trades_table(self) -> Table:
        """创建交易历史表格"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("时间", style="cyan", width=8)
        table.add_column("方向", justify="center", width=4)
        table.add_column("数量", justify="right", width=8)
        table.add_column("价格", justify="right", width=8)
        table.add_column("成本", justify="right", width=10)
        
        if self.order_manager and self.order_manager.filled_orders:
            # 显示最近10笔交易
            recent_trades = self.order_manager.filled_orders[-10:]
            for order in reversed(recent_trades):
                time_str = order.timestamp.strftime("%H:%M:%S")
                side_emoji = "🟢" if order.side == "YES" else "🔴"
                table.add_row(
                    time_str,
                    f"{side_emoji} {order.side}",
                    f"{order.filled_qty:.2f}",
                    f"${order.filled_price:.4f}",
                    f"${order.filled_qty * order.filled_price:.2f}",
                    style="green" if order.side == "YES" else "red"
                )
        else:
            table.add_row("暂无交易", "-", "-", "-", "-", style="dim")
        
        return table
    
    def _create_logs_text(self) -> Text:
        """创建日志文本"""
        text = Text()
        
        if self.trade_logs:
            # 显示最近15条日志
            for log in self.trade_logs[-15:]:
                text.append(log + "\n")
        else:
            text.append("等待交易信号...\n", style="dim")
        
        return text
    
    def add_trade_log(self, message: str):
        """添加交易日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.trade_logs.append(log_entry)
        # 保持最多100条日志
        if len(self.trade_logs) > 100:
            self.trade_logs.pop(0)
    
    def _create_footer_text(self) -> Text:
        """创建底部状态文本"""
        text = Text()
        
        # 模拟模式提示
        text.append("🔶 模拟交易模式 - 不会真实下单", style="bold yellow")
        text.append("\n")
        
        if self.position.is_profitable():
            text.append("✅ 利润已锁定！停止买入，等待结算", style="bold green")
        else:
            text.append("⏳ 持续监控中...", style="yellow")
        
        text.append("\n")
        text.append(f"配对成本: {self.position.pair_cost:.4f} ", style="cyan")
        if self.position.pair_cost < 0.98:
            text.append("(安全)", style="green")
        else:
            text.append("(风险)", style="red")
        
        # 显示交易统计
        if self.order_manager:
            total_trades = len(self.order_manager.filled_orders)
            text.append(f" | 总交易数: {total_trades}", style="cyan")
        
        return text
    
    def _create_price_chart(self, order_book: OrderBook) -> Text:
        """创建价格图表（ASCII 风格）"""
        # 记录价格历史
        timestamp = datetime.now()
        current_yes = order_book.yes_mid_price
        current_no = order_book.no_mid_price
        
        # 只有当价格变化时才添加新点（避免重复）
        if not self.price_history or \
           self.price_history[-1]["yes"] != current_yes or \
           self.price_history[-1]["no"] != current_no:
            self.price_history.append({
                "time": timestamp,
                "yes": current_yes,
                "no": current_no
            })
        
        # 保持最近30个数据点
        if len(self.price_history) > 30:
            self.price_history.pop(0)
        
        if len(self.price_history) < 2:
            return Text("等待数据...", style="dim")
        
        # 创建简单的 ASCII 图表
        text = Text()
        
        # YES 价格
        yes_prices = [p["yes"] for p in self.price_history]
        yes_min, yes_max = min(yes_prices), max(yes_prices)
        yes_range = yes_max - yes_min if yes_max != yes_min else 0.01
        
        text.append("YES: ", style="green bold")
        if len(yes_prices) >= 2:
            # 简单的趋势指示
            if yes_prices[-1] > yes_prices[-2]:
                text.append("📈 ", style="green")
            elif yes_prices[-1] < yes_prices[-2]:
                text.append("📉 ", style="red")
            else:
                text.append("➡️  ", style="yellow")
        text.append(f"${order_book.yes_mid_price:.4f}", style="green")
        text.append(f" (范围: ${yes_min:.4f} - ${yes_max:.4f})\n", style="dim")
        
        # NO 价格
        no_prices = [p["no"] for p in self.price_history]
        no_min, no_max = min(no_prices), max(no_prices)
        no_range = no_max - no_min if no_max != no_min else 0.01
        
        text.append("NO:  ", style="red bold")
        if len(no_prices) >= 2:
            if no_prices[-1] > no_prices[-2]:
                text.append("📈 ", style="green")
            elif no_prices[-1] < no_prices[-2]:
                text.append("📉 ", style="red")
            else:
                text.append("➡️  ", style="yellow")
        text.append(f"${order_book.no_mid_price:.4f}", style="red")
        text.append(f" (范围: ${no_min:.4f} - ${no_max:.4f})\n", style="dim")
        
        # 配对成本
        pair_cost = self.position.pair_cost
        text.append("\n配对成本: ", style="cyan")
        text.append(f"${pair_cost:.4f}", style="bold cyan")
        if pair_cost < 0.98:
            text.append(" ✅ 安全", style="green")
        else:
            text.append(" ⚠️  风险", style="red")
        
        # 价格变化百分比
        if len(self.price_history) >= 2:
            yes_change = ((yes_prices[-1] - yes_prices[0]) / yes_prices[0]) * 100 if yes_prices[0] > 0 else 0
            no_change = ((no_prices[-1] - no_prices[0]) / no_prices[0]) * 100 if no_prices[0] > 0 else 0
            
            text.append(f"\n\n变化: YES {yes_change:+.2f}% | NO {no_change:+.2f}%", style="dim")
        
        return text
    
    def _create_parameters_table(self) -> Table:
        """创建执行参数表格"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("参数", style="cyan", width=20)
        table.add_column("值", justify="right", width=15)
        
        from config import Config
        
        # 准入条件
        entry_min = Config.ENTRY_PRICE_MIN
        entry_max = Config.ENTRY_PRICE_MAX
        table.add_row("买入价格区间", f"${entry_min:.2f} - ${entry_max:.2f}")
        
        # 订单大小
        default_size = Config.DEFAULT_ORDER_SIZE
        rebalance_size = Config.REBALANCE_ORDER_SIZE
        table.add_row("默认订单大小", f"{default_size:.0f} 份")
        table.add_row("平衡订单大小", f"{rebalance_size:.0f} 份")
        
        # 不平衡阈值
        imbalance_threshold = Config.IMBALANCE_THRESHOLD * 100
        table.add_row("不平衡阈值", f"{imbalance_threshold:.0f}%")
        
        # 准入判定
        pair_cost = self.position.pair_cost
        can_buy_yes = self.position.can_buy("YES", 100, 0.45) if self.current_orderbook else False
        can_buy_no = self.position.can_buy("NO", 100, 0.45) if self.current_orderbook else False
        
        table.add_row("准入判定阈值", "< 0.98 (考虑 2% 手续费)")
        table.add_row("当前配对成本", f"${pair_cost:.4f}")
        table.add_row("YES 可买入", "✅" if can_buy_yes else "❌")
        table.add_row("NO 可买入", "✅" if can_buy_no else "❌")
        
        # 利润锁定
        is_profitable = self.position.is_profitable()
        table.add_row("利润锁定状态", "✅ 已锁定" if is_profitable else "⏳ 未锁定")
        
        return table
    
    async def update(self, order_book: OrderBook):
        """更新面板"""
        self.current_orderbook = order_book
        layout = self.create_layout(order_book)
        return layout


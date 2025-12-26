"""
市场选择界面
"""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from typing import List, Optional
from src.market.polymarket_api import Market


class MarketSelector:
    """市场选择器"""
    
    def __init__(self, console: Console):
        self.console = console
    
    def display_markets(self, markets: List[Market]) -> Optional[Market]:
        """
        显示市场列表并让用户选择
        
        Args:
            markets: 市场列表
        
        Returns:
            选中的市场，如果取消则返回 None
        """
        if not markets:
            self.console.print("[red]❌ 未找到符合条件的市场[/red]")
            return None
        
        # 创建市场表格
        table = Table(title="📊 可用的 BTC 15分钟预测市场", show_header=True, header_style="bold magenta")
        table.add_column("序号", style="cyan", width=6, justify="center")
        table.add_column("问题", style="yellow", width=60)
        table.add_column("市场ID", style="dim", width=20)
        table.add_column("状态", justify="center", width=10)
        
        for idx, market in enumerate(markets[:20], 1):  # 最多显示20个
            status = "🟢 活跃" if market.is_active else "⚪ 非活跃"
            table.add_row(
                str(idx),
                market.question[:58] + "..." if len(market.question) > 58 else market.question,
                market.market_id[:18] + "..." if len(market.market_id) > 18 else market.market_id,
                status
            )
        
        self.console.print(table)
        
        # 让用户选择
        try:
            choice = Prompt.ask(
                f"\n[cyan]请选择市场 (1-{min(len(markets), 20)})，或按 Enter 选择第一个[/cyan]",
                default="1"
            )
            
            choice_num = int(choice)
            if 1 <= choice_num <= min(len(markets), 20):
                selected = markets[choice_num - 1]
                self.console.print(f"\n[green]✅ 已选择市场: {selected.question}[/green]")
                return selected
            else:
                self.console.print("[red]❌ 无效的选择[/red]")
                return None
        except (ValueError, KeyboardInterrupt):
            # 如果用户直接按 Enter 或中断，选择第一个
            if markets:
                selected = markets[0]
                self.console.print(f"\n[green]✅ 已选择第一个市场: {selected.question}[/green]")
                return selected
            return None


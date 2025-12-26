"""
演示数据：用于展示可视化界面（当 API 不可用时）
"""
from datetime import datetime, timedelta
from src.market.polymarket_api import Market, OrderBook, OrderBookLevel
import random


def create_demo_markets() -> list:
    """创建演示市场数据 - 只创建 BTC/ETH 15分钟市场（匹配实际格式）"""
    markets = []
    import time
    
    # 创建几个演示的 BTC/ETH 15分钟市场，匹配实际 Polymarket 格式
    demo_markets_data = [
        {
            "question": "Bitcoin Up or Down - December 23, 11:30-11:45AM ET",
            "slug": "btc-updown-15m-1766507400"
        },
        {
            "question": "Bitcoin Up or Down - December 23, 11:45-12:00PM ET",
            "slug": "btc-updown-15m-1766508300"
        },
        {
            "question": "Ethereum Up or Down - December 23, 11:30-11:45AM ET",
            "slug": "eth-updown-15m-1766507400"
        },
        {
            "question": "Ethereum Up or Down - December 23, 11:45-12:00PM ET",
            "slug": "eth-updown-15m-1766508300"
        },
        {
            "question": "Bitcoin Up or Down - December 23, 12:00-12:15PM ET",
            "slug": "btc-updown-15m-1766509200"
        }
    ]
    
    for i, data in enumerate(demo_markets_data):
        market = Market(
            market_id=f"demo-market-{i+1}",
            question=data["question"],
            condition_id=f"demo-condition-{i+1}",
            slug=data["slug"],
            is_active=True
        )
        markets.append(market)
    
    return markets


def create_demo_orderbook() -> OrderBook:
    """创建演示订单簿数据"""
    # 生成随机价格（在合理范围内）
    yes_price = random.uniform(0.35, 0.65)
    no_price = 1.0 - yes_price
    
    # YES 订单簿
    yes_bids = []
    yes_asks = []
    spread = 0.01
    
    for i in range(5):
        bid_price = yes_price - spread * (i + 1) - 0.005 * i
        ask_price = yes_price + spread * (i + 1) + 0.005 * i
        if bid_price > 0:
            yes_bids.append(OrderBookLevel(bid_price, random.uniform(50, 200)))
        if ask_price < 1:
            yes_asks.append(OrderBookLevel(ask_price, random.uniform(50, 200)))
    
    # NO 订单簿
    no_bids = []
    no_asks = []
    for i in range(5):
        bid_price = no_price - spread * (i + 1) - 0.005 * i
        ask_price = no_price + spread * (i + 1) + 0.005 * i
        if bid_price > 0:
            no_bids.append(OrderBookLevel(bid_price, random.uniform(50, 200)))
        if ask_price < 1:
            no_asks.append(OrderBookLevel(ask_price, random.uniform(50, 200)))
    
    # 排序
    yes_bids.sort(key=lambda x: x.price, reverse=True)
    yes_asks.sort(key=lambda x: x.price)
    no_bids.sort(key=lambda x: x.price, reverse=True)
    no_asks.sort(key=lambda x: x.price)
    
    return OrderBook(
        yes_bids=yes_bids,
        yes_asks=yes_asks,
        no_bids=no_bids,
        no_asks=no_asks,
        timestamp=datetime.now()
    )


def update_demo_orderbook(orderbook: OrderBook, volatility: float = 0.02) -> OrderBook:
    """更新演示订单簿（模拟价格波动）"""
    # 随机游走
    yes_mid = orderbook.yes_mid_price
    change = random.gauss(0, volatility)
    new_yes_price = max(0.1, min(0.9, yes_mid + change))
    
    # 重新生成订单簿
    return create_demo_orderbook()


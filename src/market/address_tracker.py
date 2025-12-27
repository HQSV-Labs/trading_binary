"""
地址追踪模块
追踪特定以太坊地址在 Polymarket 上的交易活动
"""
import asyncio
import httpx
import logging
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """交易记录"""
    proxy_wallet: str
    side: str  # BUY or SELL
    asset: str
    condition_id: str
    size: float
    price: float
    timestamp: int
    title: str
    slug: str
    
    @property
    def value(self) -> float:
        """交易金额"""
        return self.size * self.price
    
    @property
    def datetime(self) -> datetime:
        """交易时间"""
        return datetime.fromtimestamp(self.timestamp)
    
    @property
    def market_url(self) -> str:
        """市场URL"""
        return f"https://polymarket.com/event/{self.slug}"


class AddressTracker:
    """地址追踪器"""
    
    DATA_API_BASE = "https://data-api.polymarket.com"
    
    def __init__(self):
        """初始化追踪器"""
        self.client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.client = httpx.AsyncClient(timeout=30.0, verify=False)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.client:
            await self.client.aclose()
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """确保客户端存在"""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0, verify=False)
        return self.client
    
    async def get_address_trades(
        self, 
        address: str, 
        limit: Optional[int] = None
    ) -> List[Trade]:
        """
        获取指定地址的交易历史
        
        Args:
            address: 以太坊地址（0x开头）
            limit: 限制返回数量（可选）
        
        Returns:
            交易列表
        """
        client = await self._ensure_client()
        
        url = f"{self.DATA_API_BASE}/trades"
        params = {"address": address}
        
        if limit:
            params["limit"] = limit
        
        try:
            logger.info(f"获取地址 {address} 的交易历史...")
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                trades_data = response.json()
                
                if isinstance(trades_data, list):
                    trades = []
                    for trade_data in trades_data:
                        try:
                            trade = Trade(
                                proxy_wallet=trade_data.get("proxyWallet", ""),
                                side=trade_data.get("side", ""),
                                asset=trade_data.get("asset", ""),
                                condition_id=trade_data.get("conditionId", ""),
                                size=float(trade_data.get("size", 0)),
                                price=float(trade_data.get("price", 0)),
                                timestamp=int(trade_data.get("timestamp", 0)),
                                title=trade_data.get("title", "Unknown"),
                                slug=trade_data.get("slug", "")
                            )
                            trades.append(trade)
                        except Exception as e:
                            logger.warning(f"解析交易数据失败: {e}")
                            continue
                    
                    logger.info(f"✓ 获取到 {len(trades)} 笔交易")
                    return trades
                else:
                    logger.warning(f"API 返回格式错误: {type(trades_data)}")
                    return []
            else:
                logger.error(f"API 请求失败: HTTP {response.status_code}")
                logger.error(f"响应: {response.text[:200]}")
                return []
        
        except Exception as e:
            logger.error(f"获取交易历史失败: {e}")
            return []
    
    async def get_all_address_trades(
        self,
        address: str,
        max_trades: Optional[int] = None,
        batch_size: int = 500
    ) -> List[Trade]:
        """
        获取地址的所有交易（通过分页突破单次500笔限制）
        
        Args:
            address: 以太坊地址（0x开头）
            max_trades: 最大获取数量（None表示不限制）
            batch_size: 每批获取的数量（API限制最大500）
        
        Returns:
            所有交易列表
        """
        all_trades = []
        offset = 0
        client = await self._ensure_client()
        
        # 确保 batch_size 不超过 API 限制
        batch_size = min(batch_size, 500)
        
        logger.info(f"开始分页获取地址 {address[:10]}... 的所有交易...")
        
        while True:
            try:
                url = f"{self.DATA_API_BASE}/trades"
                params = {
                    "address": address,
                    "limit": batch_size,
                    "offset": offset
                }
                
                logger.info(f"  获取第 {offset//batch_size + 1} 批（offset={offset}）...")
                response = await client.get(url, params=params)
                
                if response.status_code != 200:
                    logger.error(f"API 请求失败: {response.status_code}")
                    break
                
                trades_data = response.json()
                
                if not isinstance(trades_data, list) or len(trades_data) == 0:
                    logger.info(f"  没有更多数据，已获取完毕")
                    break
                
                # 解析交易数据
                batch_trades = []
                for trade_data in trades_data:
                    try:
                        trade = Trade(
                            proxy_wallet=trade_data.get("proxyWallet", ""),
                            side=trade_data.get("side", ""),
                            asset=trade_data.get("asset", ""),
                            condition_id=trade_data.get("conditionId", ""),
                            size=float(trade_data.get("size", 0)),
                            price=float(trade_data.get("price", 0)),
                            timestamp=int(trade_data.get("timestamp", 0)),
                            title=trade_data.get("title", "Unknown"),
                            slug=trade_data.get("slug", "")
                        )
                        batch_trades.append(trade)
                    except Exception as e:
                        logger.warning(f"解析交易数据失败: {e}")
                        continue
                
                all_trades.extend(batch_trades)
                logger.info(f"  ✓ 获取 {len(batch_trades)} 笔，累计 {len(all_trades)} 笔")
                
                # 检查是否达到最大数量
                if max_trades and len(all_trades) >= max_trades:
                    logger.info(f"  已达到最大数量限制 {max_trades}")
                    all_trades = all_trades[:max_trades]
                    break
                
                # 检查是否获取完毕（返回数量 < batch_size 表示没有更多数据）
                if len(trades_data) < batch_size:
                    logger.info(f"  返回数据少于批次大小，已获取完毕")
                    break
                
                offset += batch_size
                
                # 添加短暂延迟，避免请求过快
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"获取交易数据失败: {e}")
                break
        
        logger.info(f"✓ 分页获取完成，共获取 {len(all_trades)} 笔交易")
        return all_trades
    
    async def get_market_trades(
        self,
        condition_id: str,
        limit: Optional[int] = None
    ) -> List[Trade]:
        """
        获取指定市场的所有交易
        
        Args:
            condition_id: 市场条件ID
            limit: 限制返回数量（可选）
        
        Returns:
            交易列表
        """
        client = await self._ensure_client()
        
        url = f"{self.DATA_API_BASE}/trades"
        params = {"market": condition_id}
        
        if limit:
            params["limit"] = limit
        
        try:
            logger.info(f"获取市场 {condition_id[:10]}... 的交易历史...")
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                trades_data = response.json()
                
                if isinstance(trades_data, list):
                    trades = []
                    for trade_data in trades_data:
                        try:
                            trade = Trade(
                                proxy_wallet=trade_data.get("proxyWallet", ""),
                                side=trade_data.get("side", ""),
                                asset=trade_data.get("asset", ""),
                                condition_id=trade_data.get("conditionId", ""),
                                size=float(trade_data.get("size", 0)),
                                price=float(trade_data.get("price", 0)),
                                timestamp=int(trade_data.get("timestamp", 0)),
                                title=trade_data.get("title", "Unknown"),
                                slug=trade_data.get("slug", "")
                            )
                            trades.append(trade)
                        except Exception as e:
                            logger.warning(f"解析交易数据失败: {e}")
                            continue
                    
                    logger.info(f"✓ 获取到 {len(trades)} 笔交易")
                    return trades
                else:
                    logger.warning(f"API 返回格式错误: {type(trades_data)}")
                    return []
            else:
                logger.error(f"API 请求失败: HTTP {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"获取市场交易历史失败: {e}")
            return []
    
    def analyze_trades(self, trades: List[Trade]) -> Dict:
        """
        分析交易数据
        
        Args:
            trades: 交易列表
        
        Returns:
            分析结果字典
        """
        if not trades:
            return {
                "total_trades": 0,
                "buy_trades": 0,
                "sell_trades": 0,
                "total_buy_volume": 0,
                "total_sell_volume": 0,
                "markets_count": 0,
                "markets": {}
            }
        
        buy_trades = [t for t in trades if t.side == "BUY"]
        sell_trades = [t for t in trades if t.side == "SELL"]
        
        total_buy_volume = sum(t.value for t in buy_trades)
        total_sell_volume = sum(t.value for t in sell_trades)
        
        # 按市场分组
        markets = {}
        for trade in trades:
            condition_id = trade.condition_id
            
            if condition_id not in markets:
                markets[condition_id] = {
                    "title": trade.title,
                    "slug": trade.slug,
                    "trades": [],
                    "buy_count": 0,
                    "sell_count": 0,
                    "buy_volume": 0,
                    "sell_volume": 0
                }
            
            market = markets[condition_id]
            market["trades"].append(trade)
            
            if trade.side == "BUY":
                market["buy_count"] += 1
                market["buy_volume"] += trade.value
            else:
                market["sell_count"] += 1
                market["sell_volume"] += trade.value
        
        return {
            "total_trades": len(trades),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "total_buy_volume": total_buy_volume,
            "total_sell_volume": total_sell_volume,
            "net_volume": total_buy_volume - total_sell_volume,
            "markets_count": len(markets),
            "markets": markets,
            "latest_trade": trades[0] if trades else None,
            "proxy_wallets": list(set(t.proxy_wallet for t in trades))
        }
    
    async def get_all_market_trades(
        self,
        condition_id: str,
        max_trades: Optional[int] = None,
        batch_size: int = 1000
    ) -> List[Trade]:
        """
        获取市场的所有交易（通过分页突破单次限制）
        
        Args:
            condition_id: 市场条件ID
            max_trades: 最大获取数量（None表示不限制）
            batch_size: 每批获取的数量（建议1000）
        
        Returns:
            所有交易列表
        """
        all_trades = []
        offset = 0
        client = await self._ensure_client()
        
        logger.info(f"开始分页获取市场 {condition_id[:10]}... 的所有交易...")
        
        while True:
            try:
                url = f"{self.DATA_API_BASE}/trades"
                params = {
                    "market": condition_id,
                    "limit": batch_size,
                    "offset": offset
                }
                
                logger.info(f"  获取第 {offset//batch_size + 1} 批（offset={offset}）...")
                response = await client.get(url, params=params)
                
                if response.status_code != 200:
                    logger.error(f"API 请求失败: {response.status_code}")
                    break
                
                trades_data = response.json()
                
                if not isinstance(trades_data, list) or len(trades_data) == 0:
                    logger.info(f"  没有更多数据，已获取完毕")
                    break
                
                # 解析交易数据
                batch_trades = []
                for trade_data in trades_data:
                    try:
                        trade = Trade(
                            proxy_wallet=trade_data.get("proxyWallet", ""),
                            side=trade_data.get("side", ""),
                            asset=trade_data.get("asset", ""),
                            condition_id=trade_data.get("conditionId", ""),
                            size=float(trade_data.get("size", 0)),
                            price=float(trade_data.get("price", 0)),
                            timestamp=int(trade_data.get("timestamp", 0)),
                            title=trade_data.get("title", "Unknown"),
                            slug=trade_data.get("slug", "")
                        )
                        batch_trades.append(trade)
                    except Exception as e:
                        logger.warning(f"解析交易数据失败: {e}")
                        continue
                
                all_trades.extend(batch_trades)
                logger.info(f"  ✓ 获取 {len(batch_trades)} 笔，累计 {len(all_trades)} 笔")
                
                # 检查是否达到最大数量
                if max_trades and len(all_trades) >= max_trades:
                    logger.info(f"  已达到最大数量限制 {max_trades}")
                    all_trades = all_trades[:max_trades]
                    break
                
                # 检查是否获取完毕（返回数量 < batch_size 表示没有更多数据）
                if len(trades_data) < batch_size:
                    logger.info(f"  返回数据少于批次大小，已获取完毕")
                    break
                
                offset += batch_size
                
                # 添加短暂延迟，避免请求过快
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"获取交易数据失败: {e}")
                break
        
        logger.info(f"✓ 分页获取完成，共获取 {len(all_trades)} 笔交易")
        return all_trades
    
    async def get_market_status(self, slug: str) -> Optional[Dict]:
        """
        获取市场状态信息
        
        Args:
            slug: 市场 slug
        
        Returns:
            市场状态信息（包括是否关闭、是否活跃等）
        """
        GAMMA_API_BASE = "https://gamma-api.polymarket.com"
        client = await self._ensure_client()
        
        try:
            url = f"{GAMMA_API_BASE}/events?slug={slug}"
            response = await client.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    event = data[0]
                    markets = event.get("markets", [])
                    if markets and len(markets) > 0:
                        market = markets[0]
                        return {
                            "active": market.get("active", False),
                            "closed": market.get("closed", True),
                            "acceptingOrders": market.get("acceptingOrders", False),
                            "endDate": market.get("endDate"),
                        }
            return None
        except Exception as e:
            logger.warning(f"获取市场状态失败: {e}")
            return None
    
    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None


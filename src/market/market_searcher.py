"""
市场搜索模块
用于搜索和筛选 Polymarket 市场
"""
import asyncio
import logging
from typing import List, Optional, Dict
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class MarketInfo:
    """市场信息"""
    def __init__(
        self,
        condition_id: str,
        question: str,
        slug: str,
        end_date: Optional[str] = None,
        closed: bool = False,
        active: bool = False,
        accepting_orders: bool = False
    ):
        self.condition_id = condition_id
        self.question = question
        self.slug = slug
        self.end_date = end_date
        self.closed = closed
        self.active = active
        self.accepting_orders = accepting_orders
        
    @property
    def market_url(self) -> str:
        """市场链接"""
        return f"https://polymarket.com/event/{self.slug}"
    
    @property
    def status_text(self) -> str:
        """状态文本"""
        if self.closed:
            return "🔴 已关闭"
        elif self.active and self.accepting_orders:
            return "🟢 活跃"
        else:
            return "🟡 未激活"


class MarketSearcher:
    """市场搜索器"""
    
    GAMMA_API_BASE = "https://gamma-api.polymarket.com"
    DATA_API_BASE = "https://data-api.polymarket.com"
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def _ensure_client(self):
        """确保客户端存在"""
        if not self.client:
            self.client = httpx.AsyncClient()
        return self.client
    
    async def get_markets_from_address_trades(
        self,
        address: str,
        crypto: str = "BTC",
        limit: int = 50,
        hours: int = 1
    ) -> List[MarketInfo]:
        """
        从地址的最近交易中提取15分钟市场（新方法，绕过 tag_id 问题）
        
        Args:
            address: 以太坊地址
            crypto: 加密货币名称（BTC, ETH, SOL, XRP等）
            limit: 返回市场数量限制
            hours: 获取最近几小时的交易（默认1小时）
        
        Returns:
            市场信息列表（按结束时间从新到旧排序）
        """
        from datetime import datetime, timedelta
        
        client = await self._ensure_client()
        
        try:
            logger.info(f"从地址 {address[:10]}... 的最近 {hours} 小时交易中提取 {crypto} 15分钟市场...")
            
            # 计算时间阈值（最近N小时）
            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            # 获取地址的最近交易（增加 limit 以覆盖更长时间）
            url = f"{self.DATA_API_BASE}/trades"
            params = {
                "address": address,
                "limit": 3000  # 增加到3000以覆盖更多交易
            }
            
            response = await client.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                logger.error(f"API 请求失败: {response.status_code}")
                return []
            
            trades_data = response.json()
            
            if not isinstance(trades_data, list):
                return []
            
            logger.info(f"获取到 {len(trades_data)} 笔交易")
            
            # 筛选最近N小时的交易
            recent_trades = []
            for trade in trades_data:
                trade_timestamp = trade.get('timestamp', 0)
                if trade_timestamp >= cutoff_timestamp:
                    recent_trades.append(trade)
            
            logger.info(f"其中最近 {hours} 小时内的交易: {len(recent_trades)} 笔")
            
            # 提取市场信息
            seen_markets = {}  # 用 conditionId 去重
            
            for trade in recent_trades:
                try:
                    title = trade.get('title', '')
                    slug = trade.get('slug', '')
                    condition_id = trade.get('conditionId', '')
                    
                    # 筛选15分钟市场
                    if not condition_id or condition_id in seen_markets:
                        continue
                    
                    # 检查是否是指定加密货币的15分钟市场
                    crypto_upper = crypto.upper()
                    crypto_keywords = {
                        'BTC': ['BTC', 'BITCOIN'],
                        'ETH': ['ETH', 'ETHEREUM'],
                        'SOL': ['SOL', 'SOLANA'],
                        'XRP': ['XRP', 'RIPPLE']
                    }
                    
                    keywords = crypto_keywords.get(crypto_upper, [crypto_upper])
                    if not any(kw in title.upper() for kw in keywords):
                        continue
                    
                    # 检查是否包含15分钟的特征
                    # 新格式: "Bitcoin Up or Down - December 26, 10:30AM-10:45AM ET"
                    # 旧格式: "Bitcoin Up or Down - September 15, 10:30AM-10:45AM ET"
                    if 'AM-' not in title and 'PM-' not in title:
                        continue
                    
                    # 尝试获取完整市场信息（包括 closed 状态和 endDate）
                    # 如果失败，使用基本信息
                    end_date = None
                    closed = False
                    active = False
                    accepting_orders = False
                    
                    try:
                        market_url = f"{self.GAMMA_API_BASE}/events?slug={slug}"
                        market_response = await client.get(market_url, timeout=3)
                        
                        if market_response.status_code == 200:
                            market_data = market_response.json()
                            if market_data and len(market_data) > 0:
                                event = market_data[0]
                                markets = event.get('markets', [])
                                
                                if markets and len(markets) > 0:
                                    market = markets[0]
                                    end_date = market.get('endDate')
                                    closed = market.get('closed', False)
                                    active = market.get('active', False)
                                    accepting_orders = market.get('acceptingOrders', False)
                    except:
                        pass  # 如果获取失败，继续使用基本信息
                    
                    market_info = MarketInfo(
                        condition_id=condition_id,
                        question=title,
                        slug=slug,
                        end_date=end_date,
                        closed=closed,
                        active=active,
                        accepting_orders=accepting_orders
                    )
                    
                    seen_markets[condition_id] = market_info
                    
                    if len(seen_markets) >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(f"处理交易数据失败: {e}")
                    continue
            
            # 转换为列表并排序
            markets = list(seen_markets.values())
            markets.sort(
                key=lambda m: m.end_date if m.end_date else '',
                reverse=True
            )
            
            logger.info(f"✓ 从交易中提取到 {len(markets)} 个 {crypto} 15分钟市场")
            
            return markets
            
        except Exception as e:
            logger.error(f"搜索市场失败: {e}")
            return []
    
    async def get_recent_closed_btc_15min_markets(
        self,
        days: int = 7,
        limit: int = 20
    ) -> List[MarketInfo]:
        """
        获取最近关闭的 BTC 15分钟市场（优先获取最新的）
        
        Args:
            days: 最近几天内（默认7天，0表示不限制）
            limit: 返回数量限制
        
        Returns:
            市场信息列表（按关闭时间从新到旧排序）
        """
        from datetime import datetime, timedelta
        
        client = await self._ensure_client()
        
        url = f"{self.GAMMA_API_BASE}/markets"
        params = {
            "tag_id": "102467",  # BTC/ETH 15分钟市场标签
            "closed": "true",
            "limit": 500  # 增加到500以获取更多市场
        }
        
        try:
            logger.info(f"搜索最近 {days if days > 0 else '所有'} 天内关闭的 BTC 15分钟市场...")
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"API 请求失败: {response.status_code}")
                return []
            
            data = response.json()
            markets_data = data if isinstance(data, list) else []
            
            logger.info(f"API 返回 {len(markets_data)} 个市场")
            
            # 调试：显示前几个和最后几个市场的日期
            if markets_data:
                logger.info(f"第一个市场: {markets_data[0].get('question', 'N/A')[:50]}, endDate: {markets_data[0].get('endDate')}")
                if len(markets_data) > 1:
                    logger.info(f"最后一个市场: {markets_data[-1].get('question', 'N/A')[:50]}, endDate: {markets_data[-1].get('endDate')}")
            
            # 计算时间阈值
            if days > 0:
                cutoff_time = datetime.now() - timedelta(days=days)
                cutoff_timestamp = cutoff_time.timestamp()
            else:
                cutoff_timestamp = 0
            
            # 解析并筛选市场
            markets = []
            for m in markets_data:
                try:
                    question = m.get('question', '')
                    
                    # 筛选 BTC 相关
                    if 'BTC' not in question.upper() and 'BITCOIN' not in question.upper():
                        continue
                    
                    # 筛选 15分钟相关
                    if '15' not in question and 'fifteen' not in question.lower():
                        continue
                    
                    # 解析结束时间
                    end_date = m.get('endDate')
                    
                    # 如果设置了时间限制，筛选最近的
                    if days > 0 and end_date:
                        try:
                            # endDate 格式: "2025-09-13T05:30:00.000Z"
                            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                            if end_datetime.timestamp() < cutoff_timestamp:
                                continue  # 太旧，跳过
                        except:
                            pass  # 解析失败，保留该市场
                    
                    market = MarketInfo(
                        condition_id=m.get('conditionId', ''),
                        question=question,
                        slug=m.get('slug', ''),
                        end_date=end_date,
                        closed=m.get('closed', False),
                        active=m.get('active', False),
                        accepting_orders=m.get('acceptingOrders', False)
                    )
                    
                    if market.condition_id:
                        markets.append(market)
                        
                except Exception as e:
                    logger.warning(f"解析市场数据失败: {e}")
                    continue
            
            # 按结束时间排序（最新的在前）
            markets.sort(
                key=lambda m: m.end_date if m.end_date else '',
                reverse=True
            )
            
            # 限制返回数量
            markets = markets[:limit]
            
            logger.info(f"✓ 找到 {len(markets)} 个最近关闭的 BTC 15分钟市场")
            
            return markets
            
        except Exception as e:
            logger.error(f"搜索市场失败: {e}")
            return []
    
    async def search_btc_15min_markets(
        self,
        closed: bool = True,
        limit: int = 100
    ) -> List[MarketInfo]:
        """
        搜索 BTC 15分钟市场
        
        Args:
            closed: True=只搜索已关闭市场, False=只搜索活跃市场
            limit: 返回数量限制
        
        Returns:
            市场信息列表
        """
        client = await self._ensure_client()
        
        url = f"{self.GAMMA_API_BASE}/markets"
        params = {
            "tag_id": "102467",  # BTC/ETH 15分钟市场标签
            "closed": "true" if closed else "false",
            "limit": limit
        }
        
        try:
            logger.info(f"搜索 BTC 15分钟市场（closed={closed}）...")
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"API 请求失败: {response.status_code}")
                return []
            
            data = response.json()
            markets_data = data if isinstance(data, list) else []
            
            logger.info(f"找到 {len(markets_data)} 个市场")
            
            # 解析市场信息
            markets = []
            for m in markets_data:
                try:
                    # 只筛选 BTC 相关的市场
                    question = m.get('question', '')
                    if 'BTC' not in question.upper() and 'BITCOIN' not in question.upper():
                        continue
                    
                    # 只筛选 15分钟相关的市场
                    if '15' not in question and 'fifteen' not in question.lower():
                        continue
                    
                    market = MarketInfo(
                        condition_id=m.get('conditionId', ''),
                        question=question,
                        slug=m.get('slug', ''),
                        end_date=m.get('endDate'),
                        closed=m.get('closed', False),
                        active=m.get('active', False),
                        accepting_orders=m.get('acceptingOrders', False)
                    )
                    
                    if market.condition_id:  # 确保有 condition_id
                        markets.append(market)
                        
                except Exception as e:
                    logger.warning(f"解析市场数据失败: {e}")
                    continue
            
            # 按结束时间排序（最新的在前）
            markets.sort(
                key=lambda m: m.end_date if m.end_date else '',
                reverse=True
            )
            
            logger.info(f"✓ 筛选后剩余 {len(markets)} 个 BTC 15分钟市场")
            
            return markets
            
        except Exception as e:
            logger.error(f"搜索市场失败: {e}")
            return []
    
    async def search_markets_by_keyword(
        self,
        keyword: str,
        closed: bool = True,
        limit: int = 100
    ) -> List[MarketInfo]:
        """
        通过关键词搜索市场
        
        Args:
            keyword: 搜索关键词（如 "BTC", "ETH", "Trump" 等）
            closed: True=只搜索已关闭市场, False=只搜索活跃市场
            limit: 返回数量限制
        
        Returns:
            市场信息列表
        """
        client = await self._ensure_client()
        
        # 使用 Gamma API 搜索
        url = f"{self.GAMMA_API_BASE}/markets"
        params = {
            "closed": "true" if closed else "false",
            "limit": limit
        }
        
        try:
            logger.info(f"搜索包含关键词 '{keyword}' 的市场（closed={closed}）...")
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"API 请求失败: {response.status_code}")
                return []
            
            data = response.json()
            markets_data = data if isinstance(data, list) else []
            
            logger.info(f"获取到 {len(markets_data)} 个市场，开始筛选...")
            
            # 关键词筛选
            keyword_upper = keyword.upper()
            markets = []
            
            for m in markets_data:
                try:
                    question = m.get('question', '')
                    
                    # 关键词匹配
                    if keyword_upper not in question.upper():
                        continue
                    
                    market = MarketInfo(
                        condition_id=m.get('conditionId', ''),
                        question=question,
                        slug=m.get('slug', ''),
                        end_date=m.get('endDate'),
                        closed=m.get('closed', False),
                        active=m.get('active', False),
                        accepting_orders=m.get('acceptingOrders', False)
                    )
                    
                    if market.condition_id:
                        markets.append(market)
                        
                except Exception as e:
                    logger.warning(f"解析市场数据失败: {e}")
                    continue
            
            # 按结束时间排序
            markets.sort(
                key=lambda m: m.end_date if m.end_date else '',
                reverse=True
            )
            
            logger.info(f"✓ 筛选后剩余 {len(markets)} 个包含 '{keyword}' 的市场")
            
            return markets
            
        except Exception as e:
            logger.error(f"搜索市场失败: {e}")
            return []


async def main():
    """测试函数"""
    async with MarketSearcher() as searcher:
        # 测试1: 获取最近关闭的市场（120天内）
        print("=" * 80)
        print("测试1: 获取最近120天内关闭的 BTC 15分钟市场（使用 tag_id）")
        print("=" * 80)
        
        recent_markets = await searcher.get_recent_closed_btc_15min_markets(days=120, limit=20)
        
        print(f"\n找到 {len(recent_markets)} 个最近关闭的市场\n")
        
        if recent_markets:
            print("前10个:")
            for i, market in enumerate(recent_markets[:10], 1):
                print(f"{i}. {market.status_text} {market.question[:60]}")
                print(f"   结束时间: {market.end_date}")
                print()
        
        # 测试1b: 用关键词搜索（不用tag_id）
        print("\n" + "=" * 80)
        print("测试1b: 用关键词搜索 BTC 已关闭市场（不用 tag_id）")
        print("=" * 80)
        
        keyword_markets = await searcher.search_markets_by_keyword("BTC", closed=True, limit=200)
        
        # 筛选15分钟市场
        btc_15_markets = [m for m in keyword_markets if '15' in m.question or 'fifteen' in m.question.lower()]
        
        print(f"\n找到 {len(btc_15_markets)} 个包含 BTC 和 15 的市场\n")
        
        if btc_15_markets:
            # 按时间排序
            btc_15_markets.sort(key=lambda m: m.end_date if m.end_date else '', reverse=True)
            
            print("最新的10个:")
            for i, market in enumerate(btc_15_markets[:10], 1):
                print(f"{i}. {market.status_text} {market.question[:60]}")
                print(f"   结束时间: {market.end_date}")
                print()
        
        # 测试2: 搜索所有已关闭市场
        print("\n" + "=" * 80)
        print("测试2: 搜索所有 BTC 15分钟已关闭市场")
        print("=" * 80)
        
        all_markets = await searcher.search_btc_15min_markets(closed=True, limit=50)
        
        print(f"\n找到 {len(all_markets)} 个市场")
        print(f"(显示前5个)\n")
        
        for i, market in enumerate(all_markets[:5], 1):
            print(f"{i}. {market.status_text} {market.question}")
            print(f"   Condition ID: {market.condition_id[:20]}...")
            print()


if __name__ == "__main__":
    asyncio.run(main())


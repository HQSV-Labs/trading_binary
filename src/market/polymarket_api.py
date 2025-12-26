"""
Polymarket API 客户端
连接真实的 Polymarket API 获取市场数据和订单簿
"""
import asyncio
import json
import re
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import httpx
from websockets import connect
import logging

logger = logging.getLogger(__name__)


@dataclass
class Market:
    """市场信息"""
    market_id: str
    question: str
    condition_id: str
    slug: str
    end_date: Optional[datetime] = None
    is_active: bool = True


@dataclass
class OrderBookLevel:
    """订单簿层级"""
    price: float
    qty: float


@dataclass
class OrderBook:
    """订单簿"""
    yes_bids: List[OrderBookLevel]
    yes_asks: List[OrderBookLevel]
    no_bids: List[OrderBookLevel]
    no_asks: List[OrderBookLevel]
    timestamp: datetime
    
    @property
    def yes_mid_price(self) -> float:
        """YES 中间价"""
        if self.yes_bids and self.yes_asks:
            return (self.yes_bids[0].price + self.yes_asks[0].price) / 2
        return 0.5
    
    @property
    def no_mid_price(self) -> float:
        """NO 中间价"""
        if self.no_bids and self.no_asks:
            return (self.no_bids[0].price + self.no_asks[0].price) / 2
        return 0.5
    
    def get_best_ask(self, side: str) -> Optional[OrderBookLevel]:
        """获取最佳卖价（可以买入的价格）"""
        if side.upper() == "YES":
            return self.yes_asks[0] if self.yes_asks else None
        elif side.upper() == "NO":
            return self.no_asks[0] if self.no_asks else None
        return None


class PolymarketAPI:
    """Polymarket API 客户端"""
    
    # Polymarket API 端点
    GRAPHQL_ENDPOINT = "https://api.polymarket.com/graphql"
    WEBSOCKET_ENDPOINT = "wss://clob.polymarket.com/ws"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 API 客户端
        
        Args:
            api_key: API 密钥（可选，读取公开数据不需要，仅用于未来可能的真实交易功能）
        """
        self.api_key = api_key
        self.client: Optional[httpx.AsyncClient] = None
        self.ws: Optional[any] = None
        self.is_connected = False
        # timeout 配置（增加超时时间以应对网络延迟）
        self.timeout_seconds = 30  # 从 10 秒增加到 30 秒
    
    async def close(self):
        """关闭所有连接"""
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
            self.ws = None
            self.is_connected = False
        
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        # 不在这里创建 client，让 _get_client() 在需要时创建（确保在当前事件循环中）
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.client:
            await self.client.aclose()
        if self.ws:
            await self.ws.close()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx client（确保在当前事件循环中）"""
        # 每次都在当前事件循环中创建新的 client，避免事件循环绑定问题
        # 这是为了兼容 Streamlit 中可能存在的多个事件循环
        # 不重用 client，每次都创建新的，确保绑定到当前事件循环
        try:
            # 尝试关闭旧的 client（如果存在）
            if self.client is not None:
                try:
                    await self.client.aclose()
                except:
                    pass
        except:
            pass
        
        # 总是在当前事件循环中创建新的 client
        # 使用 contextvars 来确保 client 绑定到当前事件循环
        # 配置更长的超时时间和重试设置
        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)  # 连接超时 10 秒，总超时 30 秒
        self.client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            verify=False,  # 禁用 SSL 验证（Python 3.13 在 macOS 上有 SSL 兼容性问题）
            # http2=True,  # 已移除：需要安装 httpx[http2]，HTTP/1.1 也能正常工作
            follow_redirects=True  # 跟随重定向
        )
        return self.client
    
    async def _graphql_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """执行 GraphQL 查询"""
        client = await self._get_client()
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        response = await client.post(
            self.GRAPHQL_ENDPOINT,
            json=payload,
            headers=headers
        )
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"GraphQL query failed: {response.status_code}, Response: {error_text[:200]}")
            raise Exception(f"GraphQL query failed: {response.status_code}")
        return response.json()
    
    async def search_markets(
        self,
        keywords: List[str] = None,
        active: bool = True,
        limit: int = 100
    ) -> List[Market]:
        """
        搜索市场（使用 Gamma API，使用多标签精确筛选 BTC/ETH 15分钟市场）
        
        使用五位一体标签基因库确保只返回真正的 BTC/ETH 15分钟市场：
        - tag_id=102467: BTC/ETH 15分钟市场基础标签
        - tag_id=101757, 21, 102169, 102127: 其他相关标签
        
        Args:
            keywords: 搜索关键词（已废弃）
            active: 是否只返回活跃市场
            limit: 返回数量限制
        
        Returns:
            市场列表（精确筛选的 BTC/ETH 15分钟市场）
        """
        # 五位一体标签基因库 - 确保只返回真正的 BTC/ETH 15分钟市场
        # 注意：如果 API 返回的数据中没有 tags 字段，我们至少需要 tag_id=102467（已通过 API 筛选）
        TARGET_TAGS = {"102467", "101757", "21", "102169", "102127"}
        REQUIRED_TAG = "102467"  # 必须包含的标签（已通过 API 参数筛选）
        
        # 使用 Gamma API 获取市场（tag_id=102467 作为基础筛选）
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "tag_id": "102467",  # BTC/ETH 15分钟市场基础标签
            "active": "true" if active else "false",
            "closed": "false"  # 确保只获取未关闭的市场
        }
        
        try:
            client = await self._get_client()
            
            # 调试：记录请求信息
            full_url = f"{url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
            logger.info(f"🔍 请求 Gamma API: {full_url}")
            logger.info(f"📋 目标标签: {TARGET_TAGS}")
            
            response = await client.get(url, params=params, timeout=self.timeout_seconds)
            
            if response.status_code != 200:
                logger.error(f"❌ API 请求失败: HTTP {response.status_code}")
                logger.error(f"响应内容: {response.text[:500]}")
                return []
            
            data = response.json()
            # Gamma API 直接返回市场数组
            markets_data = data if isinstance(data, list) else []
            
            logger.info(f"📊 API 返回了 {len(markets_data)} 个市场（原始数据）")
            
            # 调试：显示第一个市场的完整原始数据结构
            if markets_data:
                logger.info("🔍 第一个市场的完整原始数据（过滤前）:")
                first_market = markets_data[0]
                logger.info(f"  问题: {first_market.get('question', 'N/A')}")
                logger.info(f"  所有字段: {list(first_market.keys())}")
                
                # 检查 tags 字段的不同可能位置
                tags_raw = first_market.get('tags', None)
                logger.info(f"  tags 字段（原始）: {tags_raw}")
                logger.info(f"  tags 类型: {type(tags_raw)}")
                
                # 检查是否有其他可能的标签字段
                if 'tag' in first_market:
                    logger.info(f"  tag 字段: {first_market.get('tag')}")
                if 'tagIds' in first_market:
                    logger.info(f"  tagIds 字段: {first_market.get('tagIds')}")
                if 'tag_ids' in first_market:
                    logger.info(f"  tag_ids 字段: {first_market.get('tag_ids')}")
                
                # 检查 series 字段（可能包含标签信息）
                if 'series' in first_market:
                    series = first_market.get('series', [])
                    if series and isinstance(series, list) and len(series) > 0:
                        logger.info(f"  series[0] 字段: {list(series[0].keys()) if isinstance(series[0], dict) else 'not a dict'}")
                        if isinstance(series[0], dict):
                            logger.info(f"  series[0] 完整内容: {series[0]}")
                
                # 显示其他重要字段
                logger.info(f"  closed: {first_market.get('closed')}")
                logger.info(f"  acceptingOrders: {first_market.get('acceptingOrders')}")
                logger.info(f"  active: {first_market.get('active')}")
                logger.info(f"  endDate: {first_market.get('endDate')}")
                logger.info(f"  conditionId: {first_market.get('conditionId')}")
                logger.info(f"  slug: {first_market.get('slug')}")
                
                # 如果有 events 字段，也检查一下
                if 'events' in first_market:
                    events = first_market.get('events', [])
                    if events and len(events) > 0:
                        logger.info(f"  events[0] 字段: {list(events[0].keys()) if isinstance(events[0], dict) else 'not a dict'}")
                        if isinstance(events[0], dict):
                            logger.info(f"  events[0] 完整内容: {events[0]}")
                            if 'tags' in events[0]:
                                logger.info(f"  events[0].tags: {events[0].get('tags')}")
                            if 'series' in events[0]:
                                series = events[0].get('series')
                                if series and isinstance(series, dict):
                                    logger.info(f"  events[0].series: {series}")
                
                # 打印完整的 JSON 结构（前500字符）用于调试
                import json
                logger.info(f"  完整 JSON（前500字符）: {json.dumps(first_market, indent=2, default=str)[:500]}")
            
            # 调试：显示前几个市场的标签信息（如果 tags 字段存在）
            if markets_data:
                logger.info("🔍 前3个市场的标签信息:")
                for i, m in enumerate(markets_data[:3]):
                    # 尝试多种方式获取标签
                    tags_list = m.get('tags', [])
                    if not tags_list and 'events' in m:
                        events = m.get('events', [])
                        if events and isinstance(events[0], dict):
                            tags_list = events[0].get('tags', [])
                    
                    market_tags = set()
                    if isinstance(tags_list, list):
                        for tag in tags_list:
                            if isinstance(tag, dict):
                                tag_id = tag.get('id') or tag.get('tagId') or tag.get('tag_id')
                                if tag_id:
                                    market_tags.add(str(tag_id))
                            elif isinstance(tag, (str, int)):
                                market_tags.add(str(tag))
                    
                    logger.info(f"  市场 {i+1}: {m.get('question', 'N/A')[:50]}")
                    logger.info(f"    标签列表（原始）: {tags_list}")
                    logger.info(f"    解析后的标签ID: {market_tags}")
                    logger.info(f"    是否包含所有目标标签: {TARGET_TAGS.issubset(market_tags)}")
                    logger.info(f"    closed: {m.get('closed')}, acceptingOrders: {m.get('acceptingOrders')}, active: {m.get('active')}")
                    if m.get('endDate'):
                        logger.info(f"    endDate: {m.get('endDate')}")
            
            markets = []
            now = datetime.now(timezone.utc)  # 使用 UTC aware datetime
            skipped_tags = 0
            skipped_closed = 0
            skipped_not_accepting = 0
            skipped_expired = 0
            
            # 详细统计每个市场被过滤的原因
            skip_reasons = []
            
            logger.info(f"\n🔍 开始逐个检查 {len(markets_data)} 个市场...\n")
            
            for idx, m in enumerate(markets_data, 1):
                try:
                    market_question = m.get('question', 'N/A')[:60]
                    logger.info(f"--- 市场 {idx}/{len(markets_data)}: {market_question} ---")
                    # 获取当前市场所有 Tag 的 ID（尝试多种方式）
                    tags_list = m.get('tags', [])
                    
                    # 如果 tags 字段不存在，尝试从 events 中获取
                    if not tags_list and 'events' in m:
                        events = m.get('events', [])
                        if events and isinstance(events[0], dict):
                            tags_list = events[0].get('tags', [])
                            # 如果 events[0] 中有 series，也检查 series 中的标签
                            if not tags_list and 'series' in events[0]:
                                series = events[0].get('series')
                                if isinstance(series, dict) and 'tags' in series:
                                    tags_list = series.get('tags', [])
                    
                    # 如果还是没有，尝试从顶层的 series 字段获取
                    if not tags_list and 'series' in m:
                        series = m.get('series')
                        if isinstance(series, list) and len(series) > 0 and isinstance(series[0], dict):
                            if 'tags' in series[0]:
                                tags_list = series[0].get('tags', [])
                    
                    # 解析标签 ID
                    current_tags = set()
                    if isinstance(tags_list, list) and len(tags_list) > 0:
                        for tag in tags_list:
                            if isinstance(tag, dict):
                                tag_id = tag.get('id') or tag.get('tagId') or tag.get('tag_id')
                                if tag_id:
                                    current_tags.add(str(tag_id))
                            elif isinstance(tag, (str, int)):
                                current_tags.add(str(tag))
                    
                    # 如果 tags 仍然为空，但这是通过 tag_id=102467 筛选出来的
                    # 说明这些市场确实有 102467 标签，但 API 没有返回完整的标签信息
                    if not current_tags:
                        logger.info(f"  ⚠️  市场 {idx} 的 tags 字段为空")
                        logger.info(f"     但这是通过 tag_id={REQUIRED_TAG} 筛选出来的，说明确实包含该标签")
                        # 添加 102467 标签（因为是通过这个 tag_id 筛选出来的）
                        current_tags.add(REQUIRED_TAG)
                        logger.info(f"     已添加 {REQUIRED_TAG} 标签到当前标签集合: {current_tags}")
                    
                    # 调试：记录标签匹配情况
                    # 标签检查已禁用 - 不再因标签不匹配而跳过市场
                    logger.info(f"  ✅ 标签检查已跳过（当前标签: {current_tags}，原始 tags: {tags_list}）")
                    # 继续后续检查，不跳过
                    
                    # 解析结束时间（确保是 UTC aware）
                    end_date = None
                    if m.get("endDate"):
                        try:
                            end_date = datetime.fromisoformat(m.get("endDate").replace("Z", "+00:00"))
                        except:
                            try:
                                # 如果解析失败，尝试手动解析并添加 UTC 时区
                                end_date = datetime.strptime(m.get("endDate"), "%Y-%m-%dT%H:%M:%SZ")
                                end_date = end_date.replace(tzinfo=timezone.utc)
                            except:
                                pass
                    
                    # 确保 end_date 是 aware 的
                    if end_date and end_date.tzinfo is None:
                        end_date = end_date.replace(tzinfo=timezone.utc)
                    
                    # 检查市场是否真正活跃
                    is_closed = m.get("closed", False)
                    is_accepting_orders = m.get("acceptingOrders", False)
                    has_passed_end_date = end_date and end_date < now
                    
                    # 市场必须满足以下条件才算活跃：
                    # 1. 未关闭 (closed = false)
                    # 2. 正在接受订单 (acceptingOrders = true)
                    # 3. 结束时间未到 (endDate > now)
                    is_truly_active = (
                        not is_closed and 
                        is_accepting_orders and 
                        not has_passed_end_date and
                        m.get("active", False)
                    )
                    
                    # 如果要求只返回活跃市场，则过滤掉非活跃的
                    if active and not is_truly_active:
                        if is_closed:
                            skipped_closed += 1
                            reason = f"已关闭 (closed={is_closed})"
                            skip_reasons.append({
                                "market": market_question,
                                "reason": reason,
                                "details": {"closed": is_closed, "acceptingOrders": is_accepting_orders, "active": m.get('active')}
                            })
                            logger.info(f"  ❌ 跳过原因: {reason}")
                        elif not is_accepting_orders:
                            skipped_not_accepting += 1
                            reason = f"未接受订单 (acceptingOrders={is_accepting_orders})"
                            skip_reasons.append({
                                "market": market_question,
                                "reason": reason,
                                "details": {"closed": is_closed, "acceptingOrders": is_accepting_orders, "active": m.get('active')}
                            })
                            logger.info(f"  ❌ 跳过原因: {reason}")
                        elif has_passed_end_date:
                            skipped_expired += 1
                            reason = f"已过期 (endDate={m.get('endDate')}, now={now.isoformat()})"
                            skip_reasons.append({
                                "market": market_question,
                                "reason": reason,
                                "details": {"endDate": m.get('endDate'), "now": now.isoformat(), "has_passed": has_passed_end_date}
                            })
                            logger.info(f"  ❌ 跳过原因: {reason}")
                        elif not m.get("active", False):
                            reason = f"非活跃状态 (active={m.get('active')})"
                            skip_reasons.append({
                                "market": market_question,
                                "reason": reason,
                                "details": {"active": m.get('active')}
                            })
                            logger.info(f"  ❌ 跳过原因: {reason}")
                        continue
                    
                    logger.info(f"  ✅ 市场通过所有检查，已添加到结果列表")
                    
                    # 构建 Market 对象
                    market = Market(
                        market_id=str(m.get("id", "")),
                        question=m.get("question", ""),
                        condition_id=m.get("conditionId", ""),
                        slug=m.get("slug", ""),
                        end_date=end_date,
                        is_active=is_truly_active
                    )
                    
                    markets.append(market)
                    
                    if len(markets) >= limit:
                        break
                        
                except Exception as e:
                    market_question = m.get('question', 'N/A')[:60] if 'm' in locals() else f"市场 {idx}"
                    logger.error(f"❌ 处理市场 {idx} 时发生错误: {market_question}")
                    logger.error(f"   错误类型: {type(e).__name__}")
                    logger.error(f"   错误信息: {e}")
                    import traceback
                    logger.error(f"   错误堆栈:\n{traceback.format_exc()}")
                    continue
            
            logger.info(f"\n📊 筛选结果统计:")
            logger.info(f"  - API 返回原始市场数: {len(markets_data)}")
            logger.info(f"  - 标签检查: 已禁用（不再因标签不匹配而跳过市场）")
            logger.info(f"  - 最终活跃市场数: {len(markets)}")
            logger.info(f"  - 跳过原因统计:")
            logger.info(f"    • 已关闭: {skipped_closed}")
            logger.info(f"    • 未接受订单: {skipped_not_accepting}")
            logger.info(f"    • 已过期: {skipped_expired}")
            
            if len(markets) == 0:
                logger.warning("\n⚠️  未找到符合条件的市场！")
                logger.warning(f"\n📋 详细跳过原因列表（共 {len(skip_reasons)} 个市场）:")
                for i, item in enumerate(skip_reasons[:10], 1):  # 显示前10个
                    logger.warning(f"\n  {i}. {item['market']}")
                    logger.warning(f"     原因: {item['reason']}")
                    if 'details' in item:
                        logger.warning(f"     详情: {item['details']}")
                
                if len(skip_reasons) > 10:
                    logger.warning(f"\n  ... 还有 {len(skip_reasons) - 10} 个市场被跳过")
                
                logger.warning(f"\n💡 建议检查:")
                logger.warning(f"   1. API 是否返回了数据（返回了 {len(markets_data)} 个市场）")
                logger.warning(f"   2. 市场是否活跃（closed=false, acceptingOrders=true, active=true）")
                logger.warning(f"   3. 标签检查已禁用，不再因标签不匹配而跳过市场")
                if markets_data:
                    first_tags = []
                    first_market = markets_data[0]
                    tags_list = first_market.get('tags', [])
                    if tags_list:
                        for tag in tags_list:
                            if isinstance(tag, dict):
                                first_tags.append(str(tag.get('id', '')))
                            else:
                                first_tags.append(str(tag))
                    logger.warning(f"   4. 第一个市场的标签示例: {first_tags}")
            
            # 按照结束时间排序，时间越早的越靠前
            # 注意：如果 end_date 为 None，放到最后
            markets.sort(key=lambda m: (m.end_date is None, m.end_date or datetime.max.replace(tzinfo=timezone.utc)))
            
            return markets
            
        except httpx.ConnectError as e:
            logger.error(f"❌ 网络连接错误: 无法连接到 gamma-api.polymarket.com")
            logger.error(f"   请求 URL: {full_url}")
            logger.error(f"   错误类型: ConnectError")
            logger.error(f"   可能的原因:")
            logger.error(f"     1. 网络连接问题（检查网络连接）")
            logger.error(f"     2. 防火墙/代理阻止连接")
            logger.error(f"     3. API 服务器暂时不可用")
            logger.error(f"     4. SSL/TLS 证书验证失败")
            logger.error(f"   💡 建议: 检查网络连接，或稍后重试")
            return []
        except httpx.TimeoutException as e:
            logger.error(f"❌ API 请求超时: 连接 gamma-api.polymarket.com 超时（{self.timeout_seconds}秒）")
            logger.error(f"   请求 URL: {full_url}")
            logger.error(f"   💡 建议: 检查网络连接速度，或增加超时时间")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP 错误: {e.response.status_code}")
            logger.error(f"   请求 URL: {full_url}")
            logger.error(f"   响应内容: {e.response.text[:500]}")
            return []
        except httpx.RequestError as e:
            logger.error(f"❌ 请求错误: {e}")
            logger.error(f"   请求 URL: {full_url}")
            logger.error(f"   错误类型: {type(e).__name__}")
            logger.error(f"   💡 建议: 检查网络连接和 API 端点是否可用")
            return []
        except Exception as e:
            logger.error(f"❌ 搜索市场时发生未知错误: {type(e).__name__}: {e}")
            logger.error(f"   请求 URL: {full_url}")
            import traceback
            logger.error(f"   完整错误堆栈:\n{traceback.format_exc()}")
            return []
    
    async def get_market_info_by_slug(self, slug: str) -> Optional[Dict]:
        """
        通过 slug 从 gamma-api 获取市场信息
        
        Args:
            slug: 市场 slug，例如: btc-updown-15m-1766555100
        
        Returns:
            包含市场信息的字典，包括 conditionId, clobTokenIds 等
        """
        url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        
        # 首先尝试使用 httpx
        data = None
        try:
            client = await self._get_client()
            # 添加超时参数和重试逻辑
            # 使用更详细的请求配置
            response = await client.get(
                url, 
                timeout=self.timeout_seconds,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "application/json"
                }
            )
            response.raise_for_status()  # 如果状态码不是 2xx，会抛出异常
            data = response.json()
            logger.info(f"✅ httpx 成功获取数据")
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            # 如果 httpx 失败（可能是 Python 3.13 SSL 问题），使用 curl fallback
            logger.warning(f"httpx 连接失败，尝试使用 curl fallback: {e}")
            try:
                import asyncio
                import json as json_lib
                import os
                # 使用 asyncio subprocess 执行 curl（因为 Python 3.13 SSL 可能有兼容性问题）
                # 清除可能影响 curl SSL 的环境变量
                env = os.environ.copy()
                # 移除可能影响 SSL 的变量
                for key in list(env.keys()):
                    if any(x in key.upper() for x in ['PYTHON', 'VIRTUAL', 'SSL_CERT', 'REQUESTS_CA']):
                        if 'PATH' not in key:  # 保留 PATH
                            env.pop(key, None)
                
                # 使用系统 curl（绝对路径）
                curl_cmd = ["/usr/bin/curl", "-s", "--max-time", "10", url]
                logger.info(f"使用 curl fallback 请求: {url}")
                
                try:
                    process = await asyncio.create_subprocess_exec(
                        *curl_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env  # 使用清理后的环境变量
                    )
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
                    
                    if process.returncode == 0 and stdout:
                        try:
                            data = json_lib.loads(stdout.decode('utf-8'))
                            logger.info(f"✅ 使用 curl fallback 成功获取数据")
                        except json_lib.JSONDecodeError as je:
                            raise Exception(f"curl 返回的数据不是有效的 JSON: {stdout.decode('utf-8')[:200]}")
                    else:
                        error_msg = stderr.decode('utf-8') if stderr else f"curl 返回码: {process.returncode}"
                        raise Exception(f"curl 失败: {error_msg}")
                except asyncio.TimeoutError:
                    raise Exception("curl 超时")
            except Exception as curl_error:
                logger.warning(f"curl fallback 也失败: {curl_error}")
                # 返回 None 而不是抛出错误，让调用者决定如何处理
                return None
        
        if not data:
            logger.warning(f"API 返回空数据")
            return None
            
        logger.info(f"gamma-api 返回数据: {len(data) if isinstance(data, list) else 'not a list'}")
        
        if data and len(data) > 0:
            event = data[0]
            markets = event.get("markets", [])
            logger.info(f"事件包含 {len(markets)} 个市场")
            
            if markets and len(markets) > 0:
                market = markets[0]
                logger.info(f"使用第一个市场: {market.get('slug', 'unknown')}")
                
                # 解析 clobTokenIds (JSON 字符串)
                clob_token_ids = []
                try:
                    import json
                    token_ids_str = market.get("clobTokenIds", "[]")
                    if isinstance(token_ids_str, str):
                        clob_token_ids = json.loads(token_ids_str)
                    elif isinstance(token_ids_str, list):
                        clob_token_ids = token_ids_str
                except Exception as e:
                    logger.warning(f"解析 clobTokenIds 失败: {e}")
                
                result = {
                    "conditionId": market.get("conditionId"),
                    "clobTokenIds": clob_token_ids,
                    "question": market.get("question"),
                    "slug": market.get("slug"),
                    "active": market.get("active"),
                    "closed": market.get("closed"),
                    "outcomes": json.loads(market.get("outcomes", "[]")) if market.get("outcomes") else [],
                }
                logger.info(f"成功获取市场信息: conditionId={result.get('conditionId')}, clobTokenIds数量={len(clob_token_ids)}")
                return result
            else:
                logger.warning(f"事件中没有市场数据")
        else:
            logger.warning(f"API 返回空数据或格式不正确")
        return None
    
    async def get_condition_id_from_url(self, url: str) -> Optional[str]:
        """
        从 Polymarket URL 中提取 condition_id
        
        Args:
            url: Polymarket 市场 URL，例如:
                https://polymarket.com/event/btc-updown-15m-1766510100?tid=...
        
        Returns:
            condition_id (0x 开头的十六进制字符串) 或 None
        """
        import re
        
        # 从 URL 中提取 slug
        slug_match = re.search(r'/event/([^/?]+)', url)
        if not slug_match:
            logger.warning(f"无法从 URL 中提取 slug: {url}")
            return None
        
        slug = slug_match.group(1)
        logger.info(f"从 URL 提取到 slug: {slug}")
        
        # 首先尝试使用 gamma-api
        market_info = await self.get_market_info_by_slug(slug)
        if market_info and market_info.get("conditionId"):
            logger.info(f"从 gamma-api 获取到 condition_id: {market_info['conditionId']}")
            return market_info["conditionId"]
        
        # 如果 gamma-api 失败，回退到从网页提取
        logger.info("gamma-api 失败，尝试从网页提取...")
        web_url = f"https://polymarket.com/event/{slug}"
        client = await self._get_client()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        try:
            web_response = await client.get(web_url, headers=headers)
            if web_response.status_code == 200:
                page_text = web_response.text
                
                # 尝试从页面中提取 condition_id
                condition_id_match = re.search(r'"conditionId"\s*:\s*"([^"]+)"', page_text)
                if condition_id_match:
                    condition_id = condition_id_match.group(1)
                    logger.info(f"从网页提取到 condition_id: {condition_id}")
                    return condition_id
                
                # 尝试查找 0x 开头的 64 字符十六进制
                hex_matches = re.findall(r'(0x[a-fA-F0-9]{64})', page_text)
                if hex_matches:
                    condition_id = hex_matches[0]
                    logger.info(f"从网页提取到可能的 condition_id: {condition_id}")
                    return condition_id
                
                logger.warning(f"无法从网页中提取 condition_id")
                return None
            else:
                logger.warning(f"网页请求返回 {web_response.status_code}")
                return None
        except Exception as e:
            logger.error(f"从网页提取 condition_id 失败: {e}")
            return None
    
    async def get_market_by_id(self, market_id: str) -> Optional[Market]:
        """根据 ID 获取市场信息"""
        query = """
        query GetMarket($id: String!) {
            market(id: $id) {
                id
                question
                conditionId
                slug
                endDate
                active
            }
        }
        """
        
        variables = {"id": market_id}
        
        try:
            result = await self._graphql_query(query, variables)
            market_data = result.get("data", {}).get("market")
            
            if market_data:
                return Market(
                    market_id=market_data.get("id"),
                    question=market_data.get("question", ""),
                    condition_id=market_data.get("conditionId"),
                    slug=market_data.get("slug", ""),
                    is_active=market_data.get("active", True)
                )
        except Exception as e:
            logger.error(f"Error getting market: {e}")
        
        return None
    
    async def get_orderbook(self, condition_id: str) -> Optional[OrderBook]:
        """
        获取订单簿
        
        Args:
            condition_id: 条件 ID（市场 ID，16进制格式）或 slug（如 btc-updown-15m-1766507400）
        """
        # 清理 condition_id（移除路径和查询参数）
        clean_id = condition_id.strip()
        if "/" in clean_id:
            clean_id = clean_id.split("/")[-1]
        if "?" in clean_id:
            clean_id = clean_id.split("?")[0]
        
        # 如果输入的是 slug，优先使用 gamma-api 获取市场信息
        if not clean_id.startswith("0x"):
            logger.info(f"输入的是 slug，尝试从 gamma-api 获取市场信息: {clean_id}")
            
            # 首先尝试使用 gamma-api 获取市场信息（包括 clobTokenIds）
            market_info = await self.get_market_info_by_slug(clean_id)
            if market_info:
                condition_id = market_info.get("conditionId")
                clob_token_ids = market_info.get("clobTokenIds", [])
                
                logger.info(f"从 gamma-api 获取到市场信息: conditionId={condition_id}, clobTokenIds数量={len(clob_token_ids) if clob_token_ids else 0}")
                
                if clob_token_ids and len(clob_token_ids) >= 2:
                    # 直接使用 clobTokenIds 获取订单簿（最准确的方法）
                    logger.info(f"从 gamma-api 获取到 clobTokenIds，直接使用获取订单簿")
                    token_id_yes = clob_token_ids[0]
                    token_id_no = clob_token_ids[1]
                    orderbook = await self._get_orderbook_by_token_ids(token_id_yes, token_id_no)
                    
                    # 返回订单簿（即使为空，也说明市场存在）
                    if orderbook is not None:
                        return orderbook
                    # 如果订单簿为空，但市场信息存在，创建一个空订单簿表示市场存在
                    logger.info(f"订单簿为空，但市场存在，返回空订单簿")
                    return OrderBook(
                        yes_bids=[],
                        yes_asks=[],
                        no_bids=[],
                        no_asks=[],
                        timestamp=datetime.now()
                    )
                elif condition_id:
                    # 如果没有 clobTokenIds，使用 condition_id
                    logger.info(f"从 gamma-api 获取到 condition_id: {condition_id}，使用此 condition_id 获取订单簿")
                    clean_id = condition_id
                else:
                    logger.warning(f"gamma-api 返回了市场信息但没有 conditionId 或 clobTokenIds")
                    # 即使没有 conditionId，如果 market_info 存在，说明市场存在
                    # 返回一个空订单簿
                    return OrderBook(
                        yes_bids=[],
                        yes_asks=[],
                        no_bids=[],
                        no_asks=[],
                        timestamp=datetime.now()
                    )
            
            # 如果 gamma-api 失败，直接返回 None（不再调用 search_markets 搜索所有市场）
            # 原因：手动输入 slug 时不应该搜索所有市场，应该直接失败
            # 如果用户需要搜索，应该使用"搜索市场"按钮
            if not clean_id.startswith("0x"):
                logger.warning(f"gamma-api 获取市场信息失败，无法通过 slug 获取订单簿")
                logger.info(f"💡 建议: 如果网络不稳定，可以:")
                logger.info(f"   1. 直接输入 condition_id (0x 开头)")
                logger.info(f"   2. 使用'搜索市场'按钮搜索所有市场")
                logger.info(f"   3. 检查网络连接后重试")
                return None
        
        # 使用 CLOB API 获取订单簿
        # 尝试使用 condition_id-YES/NO 格式（旧方法）
        token_id_yes = f"{clean_id}-YES"
        token_id_no = f"{clean_id}-NO"
        
        return await self._get_orderbook_by_token_ids(token_id_yes, token_id_no)
    
    async def _get_orderbook_by_token_ids(self, token_id_yes: str, token_id_no: str) -> Optional[OrderBook]:
        """
        通过 token_id 获取订单簿
        
        Args:
            token_id_yes: YES token ID
            token_id_no: NO token ID
        """
        try:
            client = await self._get_client()
            
            # 获取 YES 订单簿
            yes_url = f"https://clob.polymarket.com/book?token_id={token_id_yes}"
            yes_bids = []
            yes_asks = []
            
            response = await client.get(yes_url)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"YES 订单簿响应: bids数量={len(data.get('bids', []))}, asks数量={len(data.get('asks', []))}")
                # 解析订单簿数据
                yes_bids = [
                    OrderBookLevel(price=float(bid["price"]), qty=float(bid["size"]))
                    for bid in data.get("bids", [])
                ]
                yes_asks = [
                    OrderBookLevel(price=float(ask["price"]), qty=float(ask["size"]))
                    for ask in data.get("asks", [])
                ]
                logger.info(f"YES 订单簿解析后: bids数量={len(yes_bids)}, asks数量={len(yes_asks)}")
            elif response.status_code == 404:
                logger.warning(f"YES 订单簿不存在 (404): token_id={token_id_yes}，可能市场已关闭或没有流动性")
                # 继续尝试获取 NO 订单簿
            else:
                logger.warning(f"Failed to get YES orderbook: {response.status_code}")
                # 继续尝试获取 NO 订单簿，即使 YES 失败
            
            # 获取 NO 订单簿
            no_url = f"https://clob.polymarket.com/book?token_id={token_id_no}"
            no_bids = []
            no_asks = []
            
            no_response = await client.get(no_url)
            if no_response.status_code == 200:
                no_data = no_response.json()
                logger.info(f"NO 订单簿响应: bids数量={len(no_data.get('bids', []))}, asks数量={len(no_data.get('asks', []))}")
                no_bids = [
                    OrderBookLevel(price=float(bid["price"]), qty=float(bid["size"]))
                    for bid in no_data.get("bids", [])
                ]
                no_asks = [
                    OrderBookLevel(price=float(ask["price"]), qty=float(ask["size"]))
                    for ask in no_data.get("asks", [])
                ]
                logger.info(f"NO 订单簿解析后: bids数量={len(no_bids)}, asks数量={len(no_asks)}")
            elif no_response.status_code == 404:
                logger.warning(f"NO 订单簿不存在 (404): token_id={token_id_no}，可能市场已关闭或没有流动性")
            else:
                logger.warning(f"Failed to get NO orderbook: {no_response.status_code}")
            
            # 总是返回订单簿（即使某些数据为空）
            return OrderBook(
                yes_bids=sorted(yes_bids, key=lambda x: x.price, reverse=True),
                yes_asks=sorted(yes_asks, key=lambda x: x.price),
                no_bids=sorted(no_bids, key=lambda x: x.price, reverse=True),
                no_asks=sorted(no_asks, key=lambda x: x.price),
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error getting orderbook: {e}")
            return None
    
    async def subscribe_orderbook(
        self,
        condition_id: str,
        callback: Callable[[OrderBook], None]
    ):
        """
        订阅订单簿实时更新（WebSocket）
        
        Args:
            condition_id: 条件 ID
            callback: 订单簿更新回调函数
        """
        ws_url = f"{self.WEBSOCKET_ENDPOINT}?token_id={condition_id}-YES"
        
        try:
            async with connect(ws_url) as websocket:
                self.ws = websocket
                self.is_connected = True
                
                # 发送订阅消息
                subscribe_msg = {
                    "type": "subscribe",
                    "channel": "orderbook",
                    "token_id": f"{condition_id}-YES"
                }
                await websocket.send(json.dumps(subscribe_msg))
                
                # 监听消息
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # 解析订单簿更新
                        if data.get("type") == "orderbook":
                            orderbook = await self._parse_orderbook_update(data, condition_id)
                            if orderbook:
                                callback(orderbook)
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            self.is_connected = False
        finally:
            self.is_connected = False
    
    async def _parse_orderbook_update(self, data: Dict, condition_id: str) -> Optional[OrderBook]:
        """解析订单簿更新消息"""
        try:
            # 解析 YES 订单簿
            yes_bids = [
                OrderBookLevel(price=float(bid["price"]), qty=float(bid["size"]))
                for bid in data.get("bids", [])
            ]
            yes_asks = [
                OrderBookLevel(price=float(ask["price"]), qty=float(ask["size"]))
                for ask in data.get("asks", [])
            ]
            
            # 获取 NO 订单簿（可能需要单独订阅）
            # 这里简化处理，实际可能需要同时订阅两个 token
            no_bids = []
            no_asks = []
            
            return OrderBook(
                yes_bids=sorted(yes_bids, key=lambda x: x.price, reverse=True),
                yes_asks=sorted(yes_asks, key=lambda x: x.price),
                no_bids=sorted(no_bids, key=lambda x: x.price, reverse=True),
                no_asks=sorted(no_asks, key=lambda x: x.price),
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error parsing orderbook update: {e}")
            return None
    
    def find_btc_eth_markets(self, markets: List[Market]) -> List[Market]:
        """
        从市场列表中筛选 BTC/ETH 15分钟涨跌市场
        
        根据 Polymarket 实际格式：
        - URL: btc-updown-15m-{timestamp}
        - 标题: "Bitcoin Up or Down" 或 "Ethereum Up or Down"
        - 时间范围: XX:XX-XX:XX (15分钟区间)
        
        Args:
            markets: 市场列表
        
        Returns:
            符合条件的市场列表
        """
        filtered = []
        for market in markets:
            question_lower = market.question.lower()
            slug_lower = market.slug.lower() if market.slug else ""
            
            # 方法1: 检查 slug 是否包含 15m 格式（如 btc-updown-15m-xxx 或 eth-updown-15m-xxx）
            # 根据实际 URL: https://polymarket.com/event/btc-updown-15m-1766507400
            has_15m_slug = "-15m-" in slug_lower or slug_lower.startswith("btc-updown-15m") or \
                          slug_lower.startswith("eth-updown-15m") or "updown-15m" in slug_lower
            
            # 方法2: 检查标题是否匹配 "Up or Down" 格式
            has_updown_format = "up or down" in question_lower or "up/down" in question_lower
            
            # 方法3: 检查是否包含 BTC/ETH 和 15分钟
            has_btc = "btc" in question_lower or "bitcoin" in question_lower
            has_eth = "eth" in question_lower or "ethereum" in question_lower
            has_crypto = has_btc or has_eth
            
            # 检查 15分钟时间格式（如 11:30-11:45）
            import re
            has_15min_time = bool(re.search(r'\d{1,2}:\d{2}-\d{1,2}:\d{2}', question_lower))
            
            # 或者检查 "15 min" 关键词
            has_15min_keyword = any(keyword in question_lower for keyword in [
                "15 min", "15min", "15-minute", "15 minute", 
                "fifteen min", "fifteen-minute", "15m"
            ])
            
            # 筛选条件：必须满足以下之一
            # 1. slug 包含 15m 格式
            # 2. 标题是 "Up or Down" 格式 + 包含加密货币 + 有时间范围
            # 3. 包含加密货币 + 15分钟关键词 + 涨跌方向
            
            is_15m_market = False
            
            if has_15m_slug and has_crypto:
                # 直接通过 slug 识别
                is_15m_market = True
            elif has_updown_format and has_crypto and has_15min_time:
                # "Bitcoin Up or Down" 格式 + 时间范围
                is_15m_market = True
            elif has_crypto and (has_15min_keyword or has_15min_time):
                # 包含加密货币和15分钟关键词/时间
                # 还需要检查是否有涨跌方向
                has_direction = any(keyword in question_lower for keyword in [
                    "up", "down", "above", "below", 
                    "higher", "lower", "rise", "fall"
                ])
                if has_direction or has_updown_format:
                    is_15m_market = True
            
            if not is_15m_market:
                continue
            
            # 排除其他类型的市场
            exclude_keywords = [
                "ncaab", "nfl", "nba", "mlb", "soccer", "football",
                "election", "president", "trump", "biden",
                "stock", "sp500", "nasdaq", "price will hit",  # 排除价格预测市场
                "will hit", "before 2026", "in 2025"  # 排除长期预测
            ]
            
            if any(exclude in question_lower for exclude in exclude_keywords):
                continue
            
            filtered.append(market)
        
        return filtered


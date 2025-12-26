"""
测试特定 slug 的调试脚本
测试: btc-updown-15m-1766588400
"""
import asyncio
import logging
from src.market.polymarket_api import PolymarketAPI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_slug(slug: str):
    """测试特定 slug"""
    logger.info(f"=" * 80)
    logger.info(f"开始测试 slug: {slug}")
    logger.info(f"=" * 80)
    
    api = PolymarketAPI()
    
    try:
        # 1. 获取市场信息（metadata）
        logger.info("\n" + "=" * 80)
        logger.info("步骤 1: 获取市场 metadata (conditionId, tokenId 等)")
        logger.info("=" * 80)
        
        market_info = await api.get_market_info_by_slug(slug)
        
        if market_info:
            logger.info("✅ 成功获取市场信息:")
            logger.info(f"  - conditionId: {market_info.get('conditionId')}")
            logger.info(f"  - slug: {market_info.get('slug')}")
            logger.info(f"  - question: {market_info.get('question')}")
            logger.info(f"  - active: {market_info.get('active')}")
            logger.info(f"  - closed: {market_info.get('closed')}")
            logger.info(f"  - clobTokenIds: {market_info.get('clobTokenIds')}")
            logger.info(f"  - outcomes: {market_info.get('outcomes')}")
            
            condition_id = market_info.get('conditionId')
            clob_token_ids = market_info.get('clobTokenIds', [])
            
            if clob_token_ids and len(clob_token_ids) >= 2:
                logger.info(f"\n  Token IDs:")
                logger.info(f"    - YES Token ID: {clob_token_ids[0]}")
                logger.info(f"    - NO Token ID: {clob_token_ids[1]}")
        else:
            logger.error("❌ 无法获取市场信息")
            return
        
        # 2. 获取订单簿
        logger.info("\n" + "=" * 80)
        logger.info("步骤 2: 获取订单簿（价格信息）")
        logger.info("=" * 80)
        
        orderbook = await api.get_orderbook(slug)
        
        if orderbook:
            logger.info("✅ 成功获取订单簿:")
            logger.info(f"  - YES 买单数量: {len(orderbook.yes_bids)}")
            logger.info(f"  - YES 卖单数量: {len(orderbook.yes_asks)}")
            logger.info(f"  - NO 买单数量: {len(orderbook.no_bids)}")
            logger.info(f"  - NO 卖单数量: {len(orderbook.no_asks)}")
            
            if orderbook.yes_bids:
                logger.info(f"\n  YES 最佳买单 (前5个):")
                for i, bid in enumerate(orderbook.yes_bids[:5], 1):
                    logger.info(f"    {i}. 价格: {bid.price:.4f}, 数量: {bid.qty:.2f}")
            
            if orderbook.yes_asks:
                logger.info(f"\n  YES 最佳卖单 (前5个):")
                for i, ask in enumerate(orderbook.yes_asks[:5], 1):
                    logger.info(f"    {i}. 价格: {ask.price:.4f}, 数量: {ask.qty:.2f}")
            
            if orderbook.no_bids:
                logger.info(f"\n  NO 最佳买单 (前5个):")
                for i, bid in enumerate(orderbook.no_bids[:5], 1):
                    logger.info(f"    {i}. 价格: {bid.price:.4f}, 数量: {bid.qty:.2f}")
            
            if orderbook.no_asks:
                logger.info(f"\n  NO 最佳卖单 (前5个):")
                for i, ask in enumerate(orderbook.no_asks[:5], 1):
                    logger.info(f"    {i}. 价格: {ask.price:.4f}, 数量: {ask.qty:.2f}")
            
            logger.info(f"\n  中间价:")
            logger.info(f"    - YES 中间价: {orderbook.yes_mid_price:.4f}")
            logger.info(f"    - NO 中间价: {orderbook.no_mid_price:.4f}")
        else:
            logger.error("❌ 无法获取订单簿")
            
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
    finally:
        await api.close()


async def main():
    slug = "btc-updown-15m-1766588400"
    await test_slug(slug)


if __name__ == "__main__":
    asyncio.run(main())


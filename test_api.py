"""
测试 Polymarket API 端点
检查哪些端点可以正常工作
"""
import asyncio
import aiohttp
import json


async def test_endpoint(url: str, method: str = "GET", headers: dict = None, data: dict = None):
    """测试 API 端点"""
    print(f"\n{'='*60}")
    print(f"测试: {method} {url}")
    print(f"{'='*60}")
    
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json"
        }
    
    try:
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers) as response:
                    print(f"状态码: {response.status}")
                    print(f"响应头: {dict(response.headers)}")
                    if response.status == 200:
                        try:
                            data = await response.json()
                            print(f"响应数据 (前500字符): {str(data)[:500]}")
                        except:
                            text = await response.text()
                            print(f"响应文本 (前500字符): {text[:500]}")
                    else:
                        text = await response.text()
                        print(f"错误响应 (前500字符): {text[:500]}")
            elif method == "POST":
                async with session.post(url, headers=headers, json=data) as response:
                    print(f"状态码: {response.status}")
                    if response.status == 200:
                        try:
                            data = await response.json()
                            print(f"响应数据 (前500字符): {str(data)[:500]}")
                        except:
                            text = await response.text()
                            print(f"响应文本 (前500字符): {text[:500]}")
                    else:
                        text = await response.text()
                        print(f"错误响应 (前500字符): {text[:500]}")
    except Exception as e:
        print(f"❌ 错误: {e}")


async def main():
    """测试不同的 API 端点"""
    
    print("🔍 开始测试 Polymarket API 端点...\n")
    
    # 测试 1: GraphQL API
    graphql_url = "https://api.polymarket.com/graphql"
    graphql_query = {
        "query": """
        query {
            markets(active: true, limit: 5) {
                id
                question
                conditionId
            }
        }
        """
    }
    await test_endpoint(
        graphql_url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        },
        data=graphql_query
    )
    
    # 测试 2: CLOB API - 订单簿
    # 需要先找到一个有效的 token_id，这里用一个示例
    clob_url = "https://clob.polymarket.com/book"
    await test_endpoint(f"{clob_url}?token_id=0x123-YES")  # 示例 token
    
    # 测试 3: 尝试其他可能的端点
    endpoints_to_test = [
        "https://clob.polymarket.com/markets",
        "https://clob.polymarket.com/tokens",
        "https://api.polymarket.com/markets",
        "https://polymarket.com/api/markets",
    ]
    
    for endpoint in endpoints_to_test:
        await test_endpoint(endpoint)
        await asyncio.sleep(0.5)  # 避免请求过快
    
    # 测试 4: 尝试使用不同的 GraphQL 查询
    alternative_query = {
        "query": """
        query GetMarkets {
            markets {
                id
                question
            }
        }
        """
    }
    await test_endpoint(
        graphql_url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        },
        data=alternative_query
    )


if __name__ == "__main__":
    asyncio.run(main())


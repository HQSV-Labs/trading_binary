#!/usr/bin/env python3
"""
从 Polymarket URL 获取 condition_id 的工具

用法:
    python get_condition_id.py "https://polymarket.com/event/btc-updown-15m-1766510100"
    python get_condition_id.py btc-updown-15m-1766510100
"""
import asyncio
import sys
from src.market.polymarket_api import PolymarketAPI


async def main():
    if len(sys.argv) < 2:
        print("用法: python get_condition_id.py <URL 或 slug>")
        print("示例: python get_condition_id.py https://polymarket.com/event/btc-updown-15m-1766510100")
        sys.exit(1)
    
    input_str = sys.argv[1].strip()
    
    # 如果是 URL，直接使用；如果是 slug，构造 URL
    if input_str.startswith("http"):
        url = input_str
    else:
        url = f"https://polymarket.com/event/{input_str}"
    
    print(f"正在从 URL 获取 condition_id...")
    print(f"URL: {url}\n")
    
    api = PolymarketAPI()
    try:
        condition_id = await api.get_condition_id_from_url(url)
        
        if condition_id:
            print(f"✅ 成功获取 condition_id:")
            print(f"   {condition_id}")
            print(f"\n💡 你可以在 Dashboard 中直接使用这个 condition_id")
        else:
            print(f"❌ 无法获取 condition_id")
            print(f"   可能的原因:")
            print(f"   1. 市场已关闭")
            print(f"   2. URL 不正确")
            print(f"   3. 网络问题")
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())


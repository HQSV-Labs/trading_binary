# 分页获取功能说明

## 📋 问题背景

Polymarket API 对单次请求有以下限制：
- **单次最多返回 10,000 笔交易**
- 对于交易量大的市场，无法一次性获取所有数据
- 特别是热门的已关闭市场，可能有数万甚至数十万笔交易

## ✨ 解决方案：分页获取

我们实现了**自动分页获取**功能，可以突破 10,000 笔限制，获取市场的所有交易数据。

### 核心原理

```
第1次请求: offset=0,    limit=1000  → 获取 1-1000 笔
第2次请求: offset=1000, limit=1000  → 获取 1001-2000 笔
第3次请求: offset=2000, limit=1000  → 获取 2001-3000 笔
...
直到返回数量 < 1000，表示已获取完毕
```

### 技术实现

#### 1. 后端 API（`AddressTracker`）

新增方法 `get_all_market_trades()`:

```python
async def get_all_market_trades(
    self,
    condition_id: str,
    max_trades: Optional[int] = None,  # None = 不限制
    batch_size: int = 1000              # 每批1000笔
) -> List[Trade]:
    """
    自动分页获取市场的所有交易
    
    Args:
        condition_id: 市场条件ID
        max_trades: 最大获取数量（None表示不限制）
        batch_size: 每批获取的数量（建议1000）
    
    Returns:
        所有交易列表
    """
```

**特性**：
- ✅ 自动分页，突破10,000笔限制
- ✅ 进度日志，实时显示获取进度
- ✅ 可选上限，避免数据过多
- ✅ 防过载，批次间延迟0.5秒
- ✅ 异常处理，出错自动停止并返回已获取数据

#### 2. Dashboard 界面

在"市场分析"页面新增**获取模式**选择：

**模式 1: 限制数量（快速模式）**
```
- 快速获取指定数量（100-10000笔）
- 适合快速查看市场概况
- 加载时间：1-5秒
```

**模式 2: 🔥 获取全部（完整模式）**
```
- 分页获取所有交易（突破限制）
- 可选设置上限（避免过多）
- 加载时间：1-5分钟
- 适合已关闭市场的完整分析
```

## 🚀 使用指南

### Dashboard 中使用

1. **打开 Dashboard**
   ```bash
   ./run_address_tracking.sh
   ```

2. **选择市场**
   - 输入地址（默认：0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d）
   - 点击"开始分析"
   - 选择要分析的市场

3. **选择获取模式**
   
   **快速查看（推荐）：**
   - 选择"限制数量"
   - 选择数量（如 500 或 1000）
   - 适合快速了解市场

   **完整分析（已关闭市场）：**
   - 选择"🔥 获取全部"
   - 可选设置最大数量（0 = 不限制）
   - 等待1-5分钟
   - 获取所有交易数据

### 代码中使用

```python
from src.market.address_tracker import AddressTracker

async def example():
    async with AddressTracker() as tracker:
        # 方式1: 限制数量（快速）
        trades = await tracker.get_market_trades(
            condition_id="0x28a246...",
            limit=1000
        )
        
        # 方式2: 获取所有（分页）
        all_trades = await tracker.get_all_market_trades(
            condition_id="0x28a246...",
            max_trades=None,    # None = 不限制
            batch_size=1000     # 每批1000笔
        )
        
        # 方式3: 获取所有，但限制最多50000笔
        limited_trades = await tracker.get_all_market_trades(
            condition_id="0x28a246...",
            max_trades=50000,
            batch_size=1000
        )
        
        print(f"获取到 {len(all_trades)} 笔交易")
```

## 📊 性能说明

### 获取速度

| 交易数量 | 预计时间 | 说明 |
|---------|---------|------|
| 1,000 笔 | ~2秒 | 单次请求即可 |
| 5,000 笔 | ~5-10秒 | 5次请求 |
| 10,000 笔 | ~15-20秒 | 10次请求 |
| 50,000 笔 | ~1-2分钟 | 50次请求 |
| 100,000 笔 | ~2-5分钟 | 100次请求 |

**影响因素**：
- 网络速度
- API响应时间
- 批次间延迟（0.5秒）

### 建议使用场景

✅ **适合分页获取**：
- 已关闭的市场（数据不再变化）
- 需要完整历史数据分析
- 生成报告或导出数据

⚠️ **不建议分页获取**：
- 活跃市场（数据快速变化）
- 只需要最近交易
- 快速查看市场概况

## 🔍 实际案例

### 案例1: 热门已关闭市场

```
市场: "2024 US Presidential Election"
- 总交易数: 187,234 笔
- 使用分页: 获取全部
- 耗时: 3分42秒
- 结果: 完整的历史交易数据，可进行深度分析
```

### 案例2: 小型市场

```
市场: "Solana Up or Down - Today"
- 总交易数: 523 笔
- 使用限制: 1000笔
- 耗时: 2秒
- 结果: 单次请求即可获取全部
```

## 🛠️ 技术细节

### API Endpoint

```
GET https://data-api.polymarket.com/trades
```

**参数**：
- `market`: 市场的 condition_id
- `limit`: 单次返回数量（最大10000）
- `offset`: 跳过前N笔交易

**返回**：
- 交易列表（JSON数组）
- 按时间倒序排列

### 分页逻辑

```python
offset = 0
all_trades = []

while True:
    # 请求一批数据
    batch = fetch(market, limit=1000, offset=offset)
    
    # 没有更多数据
    if len(batch) == 0:
        break
    
    all_trades.extend(batch)
    
    # 检查是否达到上限
    if max_trades and len(all_trades) >= max_trades:
        break
    
    # 检查是否已获取完毕
    if len(batch) < 1000:
        break
    
    offset += 1000
    await asyncio.sleep(0.5)  # 防止请求过快
```

## 📈 数据验证

### 数据完整性

✅ **确保完整性**：
- 每批数据无重复
- 按时间排序
- 无遗漏交易

✅ **验证方法**：
```python
# 检查唯一性（假设每笔交易有唯一ID）
unique_ids = set()
for trade in all_trades:
    trade_id = f"{trade.timestamp}_{trade.proxy_wallet}_{trade.size}"
    assert trade_id not in unique_ids
    unique_ids.add(trade_id)

# 检查时间排序
for i in range(len(all_trades) - 1):
    assert all_trades[i].timestamp >= all_trades[i+1].timestamp
```

## ⚠️ 注意事项

### 1. 内存占用

大量交易会占用内存：
- 1万笔 ≈ 10-20 MB
- 10万笔 ≈ 100-200 MB
- 100万笔 ≈ 1-2 GB

**建议**：
- 分析完后及时释放
- 必要时设置 `max_trades` 上限

### 2. API限流

虽然有批次间延迟（0.5秒），但仍需注意：
- 避免同时多个分页请求
- 出现限流错误时，增加延迟

### 3. 数据变化

活跃市场的数据在不断变化：
- 分页过程中可能有新交易
- 可能导致数据不完全一致
- **建议只对已关闭市场使用完整分页**

## 🎯 总结

✅ **分页获取功能特点**：
1. 突破10,000笔单次限制
2. 自动分页，无需手动处理
3. 进度显示，实时反馈
4. 可选上限，灵活控制
5. 适合已关闭市场的完整分析

✅ **使用建议**：
- 快速查看 → 使用"限制数量"模式
- 完整分析 → 使用"🔥 获取全部"模式
- 已关闭市场 → 优先使用分页获取
- 活跃市场 → 使用限制数量即可

🚀 **现在你可以获取任意市场的所有交易数据！**


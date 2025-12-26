# Bug Report: Timeout context manager should be used inside a task

## 问题描述

在使用 `aiohttp` 进行 HTTP 请求时，遇到以下错误：
```
RuntimeError: Timeout context manager should be used inside a task
```

## 环境信息

- Python 版本: 3.11+ (需要确认具体版本)
- aiohttp 版本: >=3.8.0 (当前 requirements.txt)
- 操作系统: macOS (darwin 24.6.0)
- 使用场景: Streamlit Dashboard 中通过 `run_async()` 函数运行异步代码

## 问题复现

1. 在 Streamlit 中使用 `run_async()` 函数调用异步函数
2. `run_async()` 使用 `loop.run_until_complete()` 运行协程
3. 在异步函数中创建 `aiohttp.ClientSession()` 并发送请求
4. 错误发生在 `session.get()` 调用时

## 已尝试的解决方案

1. ✅ 移除所有 `ClientSession` 创建时的 timeout 配置
2. ✅ 移除所有 `session.get()` 调用中的 timeout 参数
3. ✅ 使用 `timeout=None` 显式禁用 timeout
4. ✅ 使用 `asyncio.wait_for` 和 `asyncio.create_task` 包装请求
5. ✅ 在 `run_async()` 中使用 `asyncio.create_task()` 包装协程
6. ❌ 以上方案均未解决问题

## 相关代码

### run_async 函数 (dashboard.py)
```python
def run_async(coro):
    """在 Streamlit 中安全地运行异步函数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # 包装协程为 task，以支持 asyncio.timeout()（Python 3.11+ 需要 task 上下文）
        async def run_in_task():
            task = asyncio.create_task(coro)
            return await task
        
        return loop.run_until_complete(run_in_task())
    except Exception as e:
        raise
```

### ClientSession 创建 (polymarket_api.py)
```python
# 当前代码
self.session = aiohttp.ClientSession(timeout=None)
```

### 请求代码
```python
async with self.session.get(page_url) as response:
    # ...
```

## 相关 Issue

- [aiohttp GitHub Issue #7542](https://github.com/aio-libs/aiohttp/issues/7542)
- [aiohttp GitHub Issue #10153](https://github.com/aio-libs/aiohttp/issues/10153)

## 问题分析

根据 GitHub issues，这个问题与 Python 3.11+ 中 `asyncio.timeout()` 的实现有关。即使不传递 timeout 参数，`aiohttp` 在内部可能仍然使用了 `asyncio.timeout()`，而这个 context manager 需要在 task 上下文中运行。

`loop.run_until_complete()` 虽然启动了事件循环，但可能没有提供正确的 task 上下文。

## 可能的解决方案（需要验证）

1. **升级 aiohttp 到最新版本** - 可能已经修复
2. **使用 `asyncio.run()` 而不是 `loop.run_until_complete()`** - 但 Streamlit 环境可能不支持
3. **使用 `nest_asyncio` 的不同配置**
4. **降级 Python 版本到 3.10**
5. **使用 `httpx` 替代 `aiohttp`**

## 需要帮助的问题

1. 是否有已知的 workaround？
2. 在 Streamlit + Python 3.11+ 环境中如何正确使用 aiohttp？
3. 是否有其他 HTTP 异步库推荐？


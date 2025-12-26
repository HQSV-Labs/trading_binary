# 15分钟预测市场双边对冲套利 Bot

基于 Polymarket BTC/ETH 15分钟预测市场的双边对冲套利交易系统。

**🔶 模拟交易模式：连接真实的 Polymarket 数据，但不会真实下单，仅在系统内展示和可视化交易操作**

## 项目结构

```
trading_binary/
├── docs/
│   └── strategy.md          # 策略文档
├── src/
│   ├── core/                # 核心数学模型
│   │   └── position.py      # 持仓成本跟踪和判定逻辑
│   ├── market/              # 市场数据
│   │   ├── polymarket_api.py # Polymarket API 客户端
│   │   └── event_detector.py # 事件检测器（BTC/ETH 15分钟市场）
│   ├── monitor/             # 监控模块
│   │   └── price_monitor.py # 高频价格监控
│   ├── execution/           # 执行模块
│   │   └── order_manager.py # 异步下单和限价单管理
│   ├── rebalancing/         # 平衡模块
│   │   └── balancer.py      # 动态平衡算法
│   └── dashboard/           # 监控面板
│       └── display.py       # 实时 Dashboard
├── main.py                  # 主程序入口
├── test_strategy.py         # 策略测试用例
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量示例
├── .gitignore              # Git 忽略文件
└── venv/                   # 虚拟环境目录（不提交到 Git）
```

## 环境要求

- Python 3.8 或更高版本
- pip（Python 包管理器）

## 快速开始

### 1. 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate

# Windows:
# venv\Scripts\activate
```

> **提示**：激活虚拟环境后，命令行提示符前会显示 `(venv)` 标识

### 2. 安装依赖

```bash
# 确保虚拟环境已激活后，安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量（可选）

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件（可选配置）
# POLYMARKET_API_KEY=your_api_key_here  # 可选，读取公开数据不需要
# LOG_LEVEL=INFO
```

> **注意**：`POLYMARKET_API_KEY` 是可选的。读取公开的市场数据和订单簿**不需要 API key**。API key 仅用于未来可能的真实交易功能，当前模拟模式完全不需要。

### 4. 运行程序

```bash
# 运行测试用例（验证核心逻辑）
python test_strategy.py

# 方式一：运行 Streamlit Web Dashboard（推荐）✨
streamlit run dashboard.py
# 然后在浏览器中打开 http://localhost:8501

# 从 URL 获取 Condition ID
python get_condition_id.py "https://polymarket.com/event/btc-updown-15m-1766510100"

# 方式二：运行终端版（Rich 界面）
python main.py

# 如果 API 无法访问，使用演示模式查看可视化界面
python main.py --demo
# 或
python main.py -d
```

### 退出虚拟环境

```bash
# 使用完毕后，退出虚拟环境
deactivate
```

## 功能说明

系统会自动：
1. **检测市场**：搜索并筛选 BTC/ETH 15分钟涨跌预测市场（或使用演示数据）
2. **市场选择**：显示可用市场列表，用户可选择要监控的市场
3. **监控价格**：实时监控订单簿，当价格进入 0.35-0.50 区间时触发买入
4. **模拟交易**：根据准入判定公式自动模拟下单（不真实下单）
5. **利润锁定**：满足利润锁定条件时自动停止交易
6. **实时可视化**：Dashboard 实时显示价格图表、持仓、交易历史、市场行情、执行参数和交易日志

### 演示模式

如果 Polymarket API 无法访问（如 403 错误），系统会自动切换到演示模式，使用模拟数据展示完整的可视化界面。你也可以手动启用演示模式：

```bash
python main.py --demo
```

演示模式会：
- 使用模拟的 BTC 15分钟市场数据
- 生成模拟的订单簿和价格波动
- 完整展示所有可视化功能
- 适合测试和演示使用

## 模拟交易模式

- ✅ **真实数据**：连接真实的 Polymarket API 获取市场数据
- ✅ **模拟交易**：所有买入操作仅在系统内记录，不会真实下单
- ✅ **实时可视化**：Dashboard 实时展示所有交易操作和持仓变化
- ✅ **交易历史**：完整记录所有模拟交易，包括时间、价格、数量等
- ✅ **交易日志**：实时显示交易信号、成交记录和系统状态

## 功能特性

- ✅ **实时成本跟踪（Pair Cost）**：内存中实时维护 YES/NO 持仓成本和均价
- ✅ **准入判定公式**：每次买入前检查 `(新平均价 + 对边平均价) < 0.99`
- ✅ **利润锁定机制**：`min(Qty_YES, Qty_NO) > (Cost_YES + Cost_NO)` 时停止交易
- ✅ **高频监控**：100ms 级别监控价格变化，0.35-0.50 区间触发买入
- ✅ **异步限价单执行**：防止滑点，使用限价单而非市价单
- ✅ **动态平衡算法**：持仓不平衡超过 20% 时自动调整
- ✅ **实时 Dashboard**：使用 Rich 库显示 Pair Cost、持仓、市场行情等关键指标

## 核心策略

### 准入判定公式

每次买入前必须满足：
```
(Cost_Current + P × Δq) / (Qty_Current + Δq) + Avg_Opposite < 0.99
```

### 利润锁定公式

当满足以下条件时停止交易：
```
min(Qty_YES, Qty_NO) > (Cost_YES + Cost_NO)
```

## API 连接

系统使用真实的 Polymarket API 获取公开数据：
- **GraphQL API**：搜索市场和获取市场信息（公开数据，无需 API key）
- **CLOB API**：获取订单簿数据（公开数据，无需 API key）
- **WebSocket**：实时订单簿更新（公开数据，无需 API key）

### API 端点

- GraphQL: `https://api.polymarket.com/graphql`
- CLOB: `https://clob.polymarket.com/book`
- WebSocket: `wss://clob.polymarket.com/ws`

### 关于 API Key

✅ **读取公开数据不需要 API key**：所有市场数据、订单簿信息都是公开的，可以直接访问。

🔑 **API key 的用途**（未来功能）：
- 真实下单操作（当前为模拟模式，不需要）
- 查看私有账户信息
- 更高的 API 调用频率限制

当前系统为模拟交易模式，**完全不需要配置 API key**。

## Dashboard 功能

### Streamlit Web Dashboard（推荐）✨

美观的 Web 界面，包含以下功能：

1. **实时价格趋势图**：使用 Plotly 绘制的交互式价格图表，显示 YES/NO 价格趋势和买入区间
2. **持仓信息卡片**：显示 YES/NO 持仓数量、成本、平均价格
3. **市场行情**：实时显示 YES/NO 中间价和买入状态
4. **执行参数表格**：显示所有策略参数配置
5. **交易历史表格**：显示最近10笔模拟交易详情
6. **顶部指标卡片**：配对成本、总成本、最小持仓、利润状态
7. **侧边栏控制**：市场选择、开始/停止监控、重置功能

### 终端版 Dashboard（Rich 界面）

如果使用 `main.py`，会显示终端版 Dashboard：
1. **持仓信息**：显示 YES/NO 持仓数量、成本、平均价格、配对成本、利润状态
2. **交易历史**：显示最近10笔模拟交易，包括时间、方向、数量、价格、成本
3. **市场行情**：显示 YES/NO 的中间价、最佳买价、最佳卖价和买入状态
4. **实时日志**：显示交易信号、成交记录、系统状态等实时信息
5. **状态栏**：显示配对成本、利润锁定状态、交易统计等

## 注意事项

✅ **安全说明**：
- 本系统为**模拟交易模式**，不会进行真实下单
- 连接真实的 Polymarket API 获取市场数据
- 所有交易操作仅在系统内记录和可视化
- 适合用于策略测试、学习和演示
- 系统会自动检测 BTC/ETH 15分钟涨跌市场
- 建议在实际使用前充分测试所有边界情况


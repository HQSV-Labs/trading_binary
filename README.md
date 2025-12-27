# 15分钟预测市场双边对冲套利 Bot

基于 Polymarket BTC/ETH 15分钟预测市场的双边对冲套利交易系统。

**🔶 模拟交易模式：连接真实的 Polymarket 数据，但不会真实下单，仅在系统内展示和可视化交易操作**

## 项目结构

```
trading_binary/
├── docs/
│   ├── strategy.md          # 策略文档
│   └── ADDRESS_TRACKING.md  # 地址追踪功能文档
├── src/
│   ├── core/                # 核心数学模型
│   │   └── position.py      # 持仓成本跟踪和判定逻辑
│   ├── market/              # 市场数据
│   │   ├── polymarket_api.py # Polymarket API 客户端
│   │   ├── event_detector.py # 事件检测器（BTC/ETH 15分钟市场）
│   │   └── address_tracker.py # 地址追踪模块 🆕
│   ├── monitor/             # 监控模块
│   │   └── price_monitor.py # 高频价格监控
│   ├── execution/           # 执行模块
│   │   └── order_manager.py # 异步下单和限价单管理
│   ├── rebalancing/         # 平衡模块
│   │   └── balancer.py      # 动态平衡算法
│   └── dashboard/           # 监控面板
│       ├── display.py       # 实时 Dashboard
│       └── address_tracking.py # 地址追踪 Dashboard 🆕
├── main.py                  # 主程序入口
├── dashboard_address_tracking.py # 地址追踪 Dashboard 应用 🆕
├── example_address_tracking.py   # 地址追踪使用示例 🆕
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

# 🆕 运行地址追踪 Dashboard
./run_address_tracking.sh
# 或
streamlit run dashboard_address_tracking.py --server.port 8502
# 然后在浏览器中打开 http://localhost:8502

# 🔥 运行市场分析 Dashboard（新）
./run_market_analysis.sh
# 或
streamlit run dashboard_market_analysis.py --server.port 8503
# 然后在浏览器中打开 http://localhost:8503

# 从 URL 获取 Condition ID
python get_condition_id.py "https://polymarket.com/event/btc-updown-15m-1766510100"

# 方式二：运行终端版（Rich 界面）
python main.py

# 如果 API 无法访问，使用演示模式查看可视化界面
python main.py --demo
# 或
python main.py -d

# 🆕 运行地址追踪示例
python example_address_tracking.py
```

### 退出虚拟环境

```bash
# 使用完毕后，退出虚拟环境
deactivate
```

## 功能说明

### 主要交易功能

系统会自动：
1. **检测市场**：搜索并筛选 BTC/ETH 15分钟涨跌预测市场（或使用演示数据）
2. **市场选择**：显示可用市场列表，用户可选择要监控的市场
3. **监控价格**：实时监控订单簿，当价格进入 0.35-0.50 区间时触发买入
4. **模拟交易**：根据准入判定公式自动模拟下单（不真实下单）
5. **利润锁定**：满足利润锁定条件时自动停止交易

## 🔥 市场分析功能 🆕🆕

**全新分析逻辑**：搜索市场 → 获取所有交易 → 标记目标地址

### 功能特点
- 🔥 **从交易中提取市场**：从地址的最近交易中提取15分钟市场（支持12月最新市场！）
- 💰 **多币种支持**：BTC, ETH, SOL, XRP 的15分钟市场
- 📊 **获取所有交易**：分页获取市场的全部交易历史
- ⭐ **标记目标地址**：在所有交易中高亮显示目标地址的交易
- 📈 **完整分析**：交易统计、价格趋势、交易量分布
- 📥 **导出数据**：导出包含标记的完整交易数据

### 与原功能的区别

| 功能 | 地址追踪（原） | 市场分析（新） |
|------|---------------|---------------|
| **入口** | 输入地址 | 搜索市场 |
| **数据范围** | 该地址的所有市场 | 该市场的所有交易者 |
| **适用场景** | 追踪某个地址的活动 | 分析特定市场的全部情况 |
| **标记方式** | 所有数据都是该地址的 | 在所有交易中标记目标地址 |

### 使用方法

**启动 Dashboard**：
```bash
./run_market_analysis.sh
```

**步骤**：
1. 搜索市场（BTC 15分钟 或 自定义关键词）
2. 选择市场状态（已关闭 或 活跃）
3. 从列表中选择要分析的市场
4. （可选）输入目标地址进行标记
5. 获取并分析所有交易
6. 查看图表和统计，导出数据

详细指南：[市场分析功能使用指南](MARKET_ANALYSIS_GUIDE.md)

---

### 🆕 地址追踪功能

新增的地址追踪功能允许你：
1. **追踪任意地址**：输入以太坊地址，查看其在 Polymarket 的交易历史
2. **交易统计**：自动分析买卖比例、交易金额、涉及市场等
3. **市场对比**：查看特定市场的所有交易，与其他交易者对比
4. **实时数据**：通过 Polymarket 公开 API 获取最新交易数据
5. **📊 图表可视化**：按市场显示交易的时间序列图表（买入/卖出价格和数量）
6. **🎛️ 灵活配置**：选择交易数量（50-1000笔）
7. **🟢 市场筛选**：显示市场状态并筛选活跃市场
8. **🔥 分页获取**：突破10000笔限制，获取市场所有交易（适合已关闭市场）
9. **⭐ 交易标记**：在市场全部交易中自动标记追踪地址的交易 🆕

#### 🔥 分页获取所有交易（新功能）

**解决问题**：
- Polymarket API 单次最多返回 10,000 笔交易
- 热门市场可能有数万笔交易，无法一次性获取

**功能特点**：
- ✅ 自动分批请求，突破10,000笔限制
- ✅ 实时显示获取进度
- ✅ 可选设置上限（避免数据过多）
- ✅ 适合已关闭市场的完整数据分析

**使用方法**：
1. 在 Dashboard 中选择市场
2. 选择"🔥 获取全部"模式
3. 等待分页获取完成（1-5分钟，取决于市场大小）
4. 查看完整的市场交易数据

**使用示例**：
```bash
# 启动地址追踪 Dashboard
./run_address_tracking.sh

# 在侧边栏选择 "📊 图表分析模式" 查看可视化图表

# 测试分页功能
python test_pagination.py

# 或查看使用示例
python example_address_tracking.py

# 测试图表功能
python test_chart_visualization.py
```

#### ⭐ 交易标记功能（新）

在查看市场全部交易时，自动标记当前追踪地址的交易：
- ⭐ **图表中视觉标记**：你的交易用更大的marker和加粗边框
- ⭐ **统计信息增强**：显示"你的交易"数量
- ⭐ **CSV导出标记**：导出数据包含"是否为追踪地址"列
- ⭐ **快速识别**：在上千笔交易中一眼找到自己的交易

详细文档：
- [地址追踪功能文档](docs/ADDRESS_TRACKING.md)
- [🔥 分页获取功能](docs/PAGINATION_FEATURE.md) - 突破10000笔限制
- [⭐ 交易标记功能](HIGHLIGHT_TRACKING_UPDATE.md) - 标记追踪地址交易 🆕
- [功能总结](ADDRESS_TRACKING_SUMMARY.md)
- [📊 图表功能指南](CHART_FEATURE_GUIDE.md)
- [V1.3 功能更新](FEATURE_UPDATE_V1.3.md) - 交易数量选择 & 市场筛选
- [V1.4 筛选改进](FILTER_IMPROVEMENT.md) - 可查看已关闭市场
- [V1.5 市场数据导出](MARKET_DATA_EXPORT.md) - 获取市场全量数据（最多10000笔）& CSV导出
- [V1.6 分页获取](PAGINATION_UPDATE.md) - 突破10000笔限制
- [V1.7 交易标记](HIGHLIGHT_TRACKING_UPDATE.md) - 标记追踪地址
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


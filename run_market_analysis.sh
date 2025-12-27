#!/bin/bash

# 激活虚拟环境并运行市场分析 Dashboard
cd "$(dirname "$0")"

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 运行 Streamlit Dashboard
echo "🚀 启动市场分析 Dashboard..."
echo "📊 访问地址: http://localhost:8503"
echo ""

streamlit run dashboard_market_analysis.py --server.port 8503


#!/bin/bash

# 地址追踪 Dashboard 启动脚本

echo "🔍 启动 Polymarket 地址追踪 Dashboard..."
echo ""

# 激活虚拟环境
source venv/bin/activate

# 运行 Streamlit 应用
streamlit run dashboard_address_tracking.py --server.port 8502

# 如果脚本被中断，停用虚拟环境
deactivate


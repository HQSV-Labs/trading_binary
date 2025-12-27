"""
地址追踪 Dashboard
独立的 Streamlit 应用，用于追踪 Polymarket 地址的交易活动
"""
import streamlit as st
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入地址追踪组件
from src.dashboard.address_tracking import display_address_tracking
from src.dashboard.address_tracking_charts import display_address_tracking_with_charts

# 页面配置
st.set_page_config(
    page_title="Polymarket 地址追踪",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 自定义CSS
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    
    .stButton > button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    
    .stButton > button:hover {
        background-color: #45a049;
    }
    
    .dataframe {
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏信息
with st.sidebar:
    st.title("📖 使用说明")
    
    # 选择视图模式
    view_mode = st.radio(
        "选择显示模式",
        ["📊 图表分析模式", "📝 表格模式"],
        index=0
    )
    
    st.markdown("---")
    
    st.markdown("""
    ### 如何使用
    
    1. **输入地址**: 在主页面输入要追踪的以太坊地址
    2. **点击追踪**: 点击"追踪"按钮获取数据
    3. **查看分析**: 查看交易概览、最近交易和市场统计
    
    ### 功能特点
    
    - ✅ 实时获取交易数据
    - ✅ 交易统计分析
    - ✅ 按市场分组统计
    - ✅ 交易历史记录
    - ✅ 买卖方向分析
    - 🆕 交易时间序列图表
    - 🆕 市场对比分析
    
    ### 数据来源
    
    数据来自 Polymarket 官方 API
    """)
    
    st.markdown("---")
    st.caption("💡 提示：可以追踪任何在 Polymarket 上有交易记录的地址")

# 主页面 - 根据选择的模式显示不同视图
if view_mode == "📊 图表分析模式":
    display_address_tracking_with_charts()
else:
    display_address_tracking()

# 页脚
st.markdown("---")
st.caption("⚠️ 免责声明：本工具仅供学习和研究使用，数据来自 Polymarket 公开 API。请遵守相关法律法规。")


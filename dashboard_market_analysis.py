"""
市场分析 Dashboard 主入口
新逻辑：搜索市场 → 获取所有交易 → 标记目标地址
"""
import streamlit as st
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.dashboard.market_analysis import display_market_analysis

# 页面配置
st.set_page_config(
    page_title="市场交易分析",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 侧边栏信息
with st.sidebar:
    st.title("📊 市场分析")
    st.markdown("---")
    st.markdown("""
    ### 🎯 功能说明
    
    **新逻辑**：
    1. 🔍 搜索市场（BTC 15min）
    2. 📋 选择市场
    3. 📊 获取所有交易
    4. ⭐ 标记目标地址
    
    **特点**：
    - ✅ 直接搜索已关闭市场
    - ✅ 分页获取所有交易
    - ✅ 高亮标记目标地址
    - ✅ 导出完整数据
    
    **默认地址**：
    `0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d`
    """)
    
    st.markdown("---")
    st.markdown("""
    ### 💡 使用提示
    
    1. **搜索模式**：
       - 🎯 BTC 15分钟市场
       - 🔍 自定义关键词
    
    2. **市场状态**：
       - 🔴 已关闭（推荐）
       - 🟢 活跃
    
    3. **目标地址**：
       - 可选输入
       - 用于高亮标记
       - 图表中显示⭐标记
    
    4. **图表说明**：
       - 大marker + 黑边框 = 目标地址
       - 小marker + 半透明 = 其他人
    """)

# 主界面
display_market_analysis()


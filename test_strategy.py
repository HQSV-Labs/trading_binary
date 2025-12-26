"""
测试用例：验证策略核心逻辑
"""
from src.core.position import PairPosition


def test_case_1_initial_buy():
    """Case 1: 初始买入"""
    print("=" * 50)
    print("测试用例 1: 初始买入")
    print("=" * 50)
    
    position = PairPosition()
    
    # YES 价格 0.45，买入 100 份
    yes_price = 0.45
    qty = 100.0
    
    # 检查准入条件
    can_buy_yes = position.can_buy("YES", qty, yes_price)
    print(f"YES 价格: {yes_price}, 数量: {qty}")
    print(f"可以买入 YES: {can_buy_yes}")
    
    if can_buy_yes:
        position.yes.add_position(qty, yes_price)
        print(f"✅ 买入 YES: {qty} 份 @ ${yes_price}")
        print(f"YES 平均价: {position.yes.avg_price:.4f}")
        
        # 计算 NO 的最高可接受买入价
        max_no_avg = 0.99 - position.yes.avg_price
        print(f"NO 最高可接受平均价: {max_no_avg:.4f}")
        
        # 假设 NO 价格
        no_price = 0.50
        can_buy_no = position.can_buy("NO", qty, no_price)
        print(f"\nNO 价格: {no_price}, 数量: {qty}")
        print(f"可以买入 NO: {can_buy_no}")
        
        if can_buy_no:
            position.no.add_position(qty, no_price)
            print(f"✅ 买入 NO: {qty} 份 @ ${no_price}")
            print(f"NO 平均价: {position.no.avg_price:.4f}")
            print(f"配对成本: {position.pair_cost:.4f}")
            print(f"利润状态: {'✅ 已锁定' if position.is_profitable() else '❌ 未锁定'}")
    
    print()


def test_case_2_extreme_market():
    """Case 2: 极端行情"""
    print("=" * 50)
    print("测试用例 2: 极端行情")
    print("=" * 50)
    
    position = PairPosition()
    
    # 初始状态：YES 价格 0.8
    yes_price_initial = 0.8
    no_price_initial = 0.2
    
    print(f"初始 YES 价格: {yes_price_initial}")
    print(f"初始 NO 价格: {no_price_initial}")
    
    # 买入一些 NO（因为 NO 价格低）
    qty = 50.0
    if position.can_buy("NO", qty, no_price_initial):
        position.no.add_position(qty, no_price_initial)
        print(f"✅ 买入 NO: {qty} 份 @ ${no_price_initial}")
    
    # 极端行情：YES 价格瞬间跌至 0.2
    yes_price_extreme = 0.2
    print(f"\n极端行情：YES 价格跌至 {yes_price_extreme}")
    
    # 检查是否可以买入 YES
    qty_yes = 100.0
    can_buy = position.can_buy("YES", qty_yes, yes_price_extreme)
    print(f"可以买入 YES ({qty_yes} 份 @ ${yes_price_extreme}): {can_buy}")
    
    if can_buy:
        position.yes.add_position(qty_yes, yes_price_extreme)
        print(f"✅ 买入 YES: {qty_yes} 份 @ ${yes_price_extreme}")
        print(f"YES 平均价: {position.yes.avg_price:.4f}")
        print(f"NO 平均价: {position.no.avg_price:.4f}")
        print(f"配对成本: {position.pair_cost:.4f}")
        print(f"利润状态: {'✅ 已锁定' if position.is_profitable() else '❌ 未锁定'}")
    
    print()


def test_case_3_profit_lock():
    """Case 3: 利润锁定"""
    print("=" * 50)
    print("测试用例 3: 利润锁定")
    print("=" * 50)
    
    position = PairPosition()
    
    # 模拟两边持仓平衡
    # 总投入 90 刀，单边最小份额 91 份
    total_cost = 90.0
    min_qty = 91.0
    
    # 假设平均价格
    avg_price = 0.45
    
    # 计算数量
    qty = min_qty
    cost_per_side = total_cost / 2
    
    position.yes.add_position(qty, avg_price)
    position.no.add_position(qty, avg_price)
    
    # 调整成本以匹配总投入
    position.yes.cost = cost_per_side
    position.no.cost = cost_per_side
    
    print(f"YES 持仓: {position.yes.qty:.2f} 份, 成本: ${position.yes.cost:.2f}")
    print(f"NO 持仓: {position.no.qty:.2f} 份, 成本: ${position.no.cost:.2f}")
    print(f"总成本: ${position.total_cost:.2f}")
    print(f"最小持仓: {position.min_qty:.2f}")
    print(f"配对成本: {position.pair_cost:.4f}")
    
    is_profitable = position.is_profitable()
    print(f"利润状态: {'✅ 已锁定' if is_profitable else '❌ 未锁定'}")
    
    if is_profitable:
        print("✅ 程序应该自动进入 Stop 状态")
    else:
        print("❌ 程序应该继续交易")
    
    print()


if __name__ == "__main__":
    test_case_1_initial_buy()
    test_case_2_extreme_market()
    test_case_3_profit_lock()
    
    print("=" * 50)
    print("所有测试用例完成！")
    print("=" * 50)


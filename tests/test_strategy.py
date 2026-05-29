"""
策略模块单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio import Holding
from strategy import SellSignals, format_batch_table


class TestSellSignals:
    """卖出信号测试"""

    def test_no_signal_when_normal(self):
        h = Holding(code="002594", name="比亚迪", cost=100, shares=100)
        h.calc(105, 1, 1)  # 盈利 5%，不触发任何信号
        signals = SellSignals.check(h, ma50=100)  # 价105 > MA50 100，不触发
        assert len(signals) == 0, f"预期无信号，收到: {signals}"
        print(f"  ✅ 正常持仓无信号 (盈利5% < 20%, 价105 > MA50 100)")

    def test_stop_loss(self):
        h = Holding(code="601179", name="中国西电", cost=100, shares=100)
        h.calc(88, -2, -2)  # 亏损 -12%
        signals = SellSignals.check(h, ma50=95)
        types = [s[0] for s in signals]
        assert "stop_loss" in types
        print(f"  ✅ 止损信号触发 (亏损 {h.profit_pct:.1f}%)")

    def test_take_profit(self):
        h = Holding(code="002594", name="比亚迪", cost=80, shares=100)
        h.calc(100, 0, 0)  # 盈利 25%
        signals = SellSignals.check(h, ma50=90)
        types = [s[0] for s in signals]
        assert "take_profit" in types
        print(f"  ✅ 止盈信号触发 (盈利 {h.profit_pct:.1f}%)")

    def test_ma50_breach(self):
        h = Holding(code="002594", name="比亚迪", cost=80, shares=100)
        h.calc(85, 0, 0)  # 盈利 6.25%
        signals = SellSignals.check(h, ma50=90)  # 价格 85 < MA50 90
        types = [s[0] for s in signals]
        assert "ma50_exit" in types
        print(f"  ✅ MA50 跌破信号触发 (价 {h.price} < MA50 90)")

    def test_ma50_not_breach_if_no_profit(self):
        """亏损状态跌破 MA50 不触发（防止重复止损）"""
        h = Holding(code="002594", name="比亚迪", cost=100, shares=100)
        h.calc(85, 0, 0)  # 亏损 15%
        signals = SellSignals.check(h, ma50=90)  # 价 < MA50
        types = [s[0] for s in signals]
        assert "ma50_exit" not in types  # 止损已经触发了
        assert "stop_loss" in types
        print(f"  ✅ 亏损时不重复触发 MA50 信号")


class TestFormatTable:
    """批量对比表格测试"""

    def test_basic_table(self):
        results = [
            {"code": "002594", "name": "比亚迪", "total": 56, "scores": {"大盘": 20, "行业": 20, "业绩": 6, "估值": 5, "走势": 5}, "conclusion": "🔴不做"},
            {"code": "600176", "name": "中国巨石", "total": 66, "scores": {"大盘": 20, "行业": 20, "业绩": 6, "估值": 5, "走势": 15}, "conclusion": "🔴不做"},
        ]
        table = format_batch_table(results)
        assert "比亚迪" in table
        assert "中国巨石" in table
        assert "总分" in table
        print(f"  ✅ 批量表格格式正确")

    def test_empty_table(self):
        table = format_batch_table([])
        assert table.strip() != ""
        print(f"  ✅ 空列表表格正常")


if __name__ == "__main__":
    print("📋 卖出信号测试:")
    TestSellSignals().test_no_signal_when_normal()
    TestSellSignals().test_stop_loss()
    TestSellSignals().test_take_profit()
    TestSellSignals().test_ma50_breach()
    TestSellSignals().test_ma50_not_breach_if_no_profit()

    print("\n📋 表格格式化测试:")
    TestFormatTable().test_basic_table()
    TestFormatTable().test_empty_table()

    print("\n✅ 全部通过")

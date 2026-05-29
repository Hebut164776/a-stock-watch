"""
持仓数据模型单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio import Holding, Portfolio


class TestHolding:
    """持仓对象测试"""

    def test_calc_basic(self):
        h = Holding(code="002594", name="比亚迪", cost=89.861, shares=200)
        h.calc(96.62, 0.73, 0.76)
        assert h.price == 96.62
        assert abs(h.day_profit - (0.73 * 200)) < 0.01
        assert h.day_pct == 0.76
        assert abs(h.market_value - 19324.0) < 0.01
        assert abs(h.profit - (19324.0 - 17972.2)) < 0.5
        assert abs(h.profit_pct - ((96.62 / 89.861 - 1) * 100)) < 0.01
        print(f"  ✅ Holding.calc() 基本运算正确")

    def test_calc_loss(self):
        h = Holding(code="601179", name="中国西电", cost=18.132, shares=600)
        h.calc(16.38, -0.17, -1.03)
        assert h.day_profit < 0
        assert h.profit_pct < 0
        print(f"  ✅ Holding.calc() 亏损计算正确")

    def test_calc_profit_pct(self):
        h = Holding(code="600176", name="中国巨石", cost=38.06, shares=100)
        h.calc(42.92, -0.55, -1.27)
        cost_total = 38.06 * 100
        mv = 42.92 * 100
        expected_pct = round((mv - cost_total) / cost_total * 100, 2)
        assert abs(h.profit_pct - expected_pct) < 0.01
        print(f"  ✅ Holding.calc() 盈亏百分比正确")


class TestPortfolio:
    """持仓组合测试"""

    def test_empty_portfolio(self):
        p = Portfolio()
        p.update()
        assert p.total_cost == 0
        assert p.total_market_value == 0
        assert p.total_profit == 0
        print(f"  ✅ 空组合汇总正确")

    def test_single_holding(self):
        h = Holding(code="002594", name="比亚迪", cost=89.861, shares=200)
        h.calc(96.62, 0.73, 0.76)
        p = Portfolio(holdings=[h])
        p.update()
        assert abs(p.total_cost - 17972.2) < 0.5
        assert abs(p.total_market_value - 19324.0) < 0.5
        assert abs(p.total_day_profit - 146.0) < 0.01
        print(f"  ✅ 单持仓汇总正确")

    def test_multi_holdings(self):
        holdings = [
            Holding(code="002594", name="比亚迪", cost=89.861, shares=200),
            Holding(code="601179", name="中国西电", cost=18.132, shares=600),
        ]
        holdings[0].calc(96.62, 0.73, 0.76)
        holdings[1].calc(16.38, -0.17, -1.03)
        p = Portfolio(holdings=holdings)
        p.update()
        assert len(p.holdings) == 2
        expected_day = round((0.73 * 200) + (-0.17 * 600), 2)
        assert abs(p.total_day_profit - expected_day) < 0.01
        print(f"  ✅ 多持仓汇总正确 (今日:{p.total_day_profit})")


if __name__ == "__main__":
    print("📋 持仓模型测试:")
    TestHolding().test_calc_basic()
    TestHolding().test_calc_loss()
    TestHolding().test_calc_profit_pct()
    TestPortfolio().test_empty_portfolio()
    TestPortfolio().test_single_holding()
    TestPortfolio().test_multi_holdings()
    print("\n✅ 全部通过")

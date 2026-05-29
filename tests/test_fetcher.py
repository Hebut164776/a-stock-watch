"""
数据抓取模块单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetcher import StockQuote, detect_market


class TestStockQuote:
    """StockQuote 数据对象测试"""

    def test_create(self):
        q = StockQuote(code="002594", name="比亚迪", price=96.62,
                       open_price=95.0, high=97.0, low=94.5,
                       prev_close=95.89, change=0.73, change_pct=0.76,
                       volume=10000, amount=5000)
        assert q.code == "002594"
        assert q.name == "比亚迪"
        assert q.price == 96.62
        assert q.change_pct == 0.76
        print(f"  ✅ StockQuote 创建和字段正确")

    def test_repr(self):
        q = StockQuote(code="002594", name="比亚迪", price=96.62,
                       open_price=95.0, high=97.0, low=94.5,
                       prev_close=95.89, change=0.73, change_pct=0.76,
                       volume=10000, amount=5000)
        r = repr(q)
        assert "比亚迪" in r
        assert "96.62" in r
        assert "+0.76" in r
        print(f"  ✅ StockQuote.__repr__ 格式正确")

    def test_to_dict(self):
        q = StockQuote(code="002594", name="比亚迪", price=96.62,
                       open_price=95.0, high=97.0, low=94.5,
                       prev_close=95.89, change=0.73, change_pct=0.76,
                       volume=10000, amount=5000)
        d = q.to_dict()
        assert d["name"] == "比亚迪"
        assert d["price"] == 96.62
        assert d["open"] == 95.0
        assert d["yclose"] == 95.89
        print(f"  ✅ StockQuote.to_dict() 格式正确")


class TestDetectMarket:
    """市场识别测试"""

    def test_sh_stocks(self):
        assert detect_market("600519") == "sh"
        assert detect_market("601179") == "sh"
        assert detect_market("688981") == "sh"
        print(f"  ✅ 沪市股票识别正确")

    def test_sz_stocks(self):
        assert detect_market("000001") == "sz"
        assert detect_market("002594") == "sz"
        assert detect_market("300750") == "sz"
        print(f"  ✅ 深市股票识别正确")

    def test_fallback(self):
        assert detect_market("") == "sh"
        assert detect_market("abc") == "sh"
        print(f"  ✅ 无法识别时默认 sh")


if __name__ == "__main__":
    print("📋 StockQuote 测试:")
    TestStockQuote().test_create()
    TestStockQuote().test_repr()
    TestStockQuote().test_to_dict()

    print("\n📋 市场识别测试:")
    TestDetectMarket().test_sh_stocks()
    TestDetectMarket().test_sz_stocks()
    TestDetectMarket().test_fallback()

    print("\n✅ 全部通过")

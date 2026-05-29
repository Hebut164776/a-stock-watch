"""
A股实时行情数据抓取模块
支持新浪、腾讯、东方财富三个数据源
"""

import re
import time
import requests

# 数据源接口地址
URLS = {
    "sina": {
        "sh": "http://hq.sinajs.cn/list=sh{code}",
        "sz": "http://hq.sinajs.cn/list=sz{code}",
        "batch": "http://hq.sinajs.cn/list=",  # 逗号拼接 sh600519,sh000001
    },
    "tencent": {
        "sh": "http://qt.gtimg.cn/q=sh{code}",
        "sz": "http://qt.gtimg.cn/q=sz{code}",
    },
    "eastmoney": {
        "url": "http://push2.eastmoney.com/api/qt/stock/get",
        "params": {
            "fltt": "2",
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171",
        },
    },
}

HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def detect_market(code):
    """根据股票代码判断市场"""
    code = str(code).strip()
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith(("0", "2", "3")):
        return "sz"
    return "sh"


def _retry(fn, max_retries=3, delay=1, backoff=2):
    """带指数退避的重试包装器"""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn()
        except requests.RequestException as e:
            last_exc = e
            if attempt < max_retries - 1:
                wait = delay * (backoff ** attempt)
                time.sleep(wait)
        except (ValueError, IndexError, TypeError) as e:
            last_exc = e
            break  # 解析错误不重试
    raise last_exc


class StockQuote:
    """股票实时行情数据结构"""

    def __init__(self, code, name, price, open_price, high, low,
                 prev_close, change, change_pct, volume, amount):
        self.code = code
        self.name = name
        self.price = price                # 当前价
        self.open_price = open_price      # 开盘价
        self.high = high                  # 最高价
        self.low = low                    # 最低价
        self.prev_close = prev_close      # 昨收
        self.change = change              # 涨跌额
        self.change_pct = change_pct      # 涨跌幅(%)
        self.volume = volume              # 成交量(手)
        self.amount = amount              # 成交额(万)

    def __repr__(self):
        return (
            f"{self.name}({self.code}): ¥{self.price:.2f} "
            f"{self.change_pct:+.2f}%"
        )

    def to_dict(self):
        """转字典，方便其他模块使用"""
        return {
            "name": self.name,
            "open": self.open_price,
            "yclose": self.prev_close,
            "price": self.price,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "amount": self.amount,
        }


def _parse_sina_stock(data_str):
    """解析新浪财经返回的CSV数据"""
    try:
        # 新浪返回格式: "var hq_str_sh600519="name,open,prev_close,price,high,low,..."
        parts = data_str.split('="')
        if len(parts) < 2:
            return None
        values = parts[1].rstrip('";').split(",")
        if len(values) < 32:
            return None

        name = values[0]
        open_price = float(values[1]) if values[1] else 0
        prev_close = float(values[2]) if values[2] else 0
        price = float(values[3]) if values[3] else 0
        high = float(values[4]) if values[4] else 0
        low = float(values[5]) if values[5] else 0
        volume = float(values[8]) if values[8] else 0  # 成交量(手)

        # 成交额(万)
        amount_str = values[9] if len(values) > 9 else "0"
        amount = float(amount_str) / 10000 if float(amount_str) > 0 else 0

        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close != 0 else 0

        return StockQuote(
            code="", name=name, price=price,
            open_price=open_price, high=high, low=low,
            prev_close=prev_close, change=change,
            change_pct=change_pct, volume=volume, amount=amount,
        )
    except (ValueError, IndexError):
        return None


def _parse_tencent_stock(data_str):
    """解析腾讯财经返回的行情数据"""
    try:
        parts = data_str.split("~")
        if len(parts) < 40:
            return None

        name = parts[1]
        code_tx = parts[2]
        price = float(parts[3]) if parts[3] else 0
        prev_close = float(parts[4]) if parts[4] else 0
        open_price = float(parts[5]) if parts[5] else 0
        volume = float(parts[6]) if parts[6] else 0  # 成交量(手)
        high = float(parts[33]) if parts[33] else 0
        low = float(parts[34]) if parts[34] else 0
        change_pct = float(parts[32]) if parts[32] else 0  # 涨跌幅

        # 腾讯返回的涨跌额在 parts[31]
        change_str = parts[31] if len(parts) > 31 else "0"
        change = float(change_str) if change_str else 0

        amount = float(parts[37]) / 10000 if len(parts) > 37 and parts[37] else 0  # 亿转万

        return StockQuote(
            code=code_tx, name=name, price=price,
            open_price=open_price, high=high, low=low,
            prev_close=prev_close, change=change,
            change_pct=change_pct, volume=volume, amount=amount,
        )
    except (ValueError, IndexError):
        return None


def _parse_eastmoney_stock(data):
    """解析东方财富API返回的JSON数据"""
    try:
        d = data.get("data", {})
        if not d:
            return None

        code = d.get("f57", "")
        name = d.get("f58", "")
        price = d.get("f43", 0) / 100.0
        prev_close = d.get("f60", 0) / 100.0
        open_price = d.get("f46", 0) / 100.0
        high = d.get("f44", 0) / 100.0
        low = d.get("f45", 0) / 100.0
        volume = d.get("f47", 0) / 100.0  # 手
        amount = d.get("f48", 0) / 10000.0  # 万
        change_pct = d.get("f170", 0) / 100.0  # 百分比
        change = d.get("f169", 0) / 100.0  # 涨跌额

        return StockQuote(
            code=str(code), name=name, price=price,
            open_price=open_price, high=high, low=low,
            prev_close=prev_close, change=change,
            change_pct=change_pct, volume=volume, amount=amount,
        )
    except (ValueError, TypeError):
        return None


def fetch_single(code, market="sh", source="sina"):
    """
    获取单只股票的实时行情（带重试）

    Args:
        code: 股票代码，如 "600519"
        market: "sh" (上海) 或 "sz" (深圳)
        source: 数据源 "sina" | "tencent" | "eastmoney"

    Returns:
        StockQuote 对象，失败返回 None
    """
    def _do_fetch():
        if source == "sina":
            url = URLS["sina"][market].format(code=code)
            resp = requests.get(url, headers=HEADERS, timeout=5)
            resp.encoding = "gbk"
            quote = _parse_sina_stock(resp.text)
            if quote:
                quote.code = code
            return quote

        elif source == "tencent":
            url = URLS["tencent"][market].format(code=code)
            resp = requests.get(url, headers=HEADERS, timeout=5)
            resp.encoding = "gbk"
            quote = _parse_tencent_stock(resp.text)
            if quote:
                quote.code = code
            return quote

        elif source == "eastmoney":
            secid = f"1.{code}" if market == "sh" else f"0.{code}"
            params = {**URLS["eastmoney"]["params"], "secid": secid}
            resp = requests.get(
                URLS["eastmoney"]["url"], params=params,
                headers=HEADERS, timeout=5,
            )
            return _parse_eastmoney_stock(resp.json())
        return None

    try:
        return _retry(_do_fetch, max_retries=3, delay=1)
    except Exception as e:
        return None


def fetch_sina_batch(codes):
    """
    批量从新浪获取行情（一次HTTP请求）

    新浪支持一次请求多个股票，用逗号拼接即可
    相比串行逐个请求效率更高

    Args:
        codes: list of str, 股票代码列表如 ["600519", "002594"]

    Returns:
        dict: {code: StockQuote}
    """
    if not codes:
        return {}

    sh_codes = [c for c in codes if c.startswith(("6", "9"))]
    sz_codes = [c for c in codes if not c.startswith(("6", "9"))]
    result = {}

    def _fetch_group(market, group):
        url = URLS["sina"]["batch"] + ",".join(market + c for c in group)
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = "gbk"
        for line in resp.text.strip().split("\n"):
            if "=" not in line:
                continue
            parts = line.split('"')
            if len(parts) >= 2:
                fields = parts[1].split(",")
                if len(fields) >= 32:
                    code_raw = line.split("=")[0].split("_")[-1]
                    raw = code_raw[2:] if code_raw.startswith(("sh", "sz")) else code_raw
                    if raw in group:
                        quote = _parse_sina_stock(line)
                        if quote:
                            quote.code = raw
                            result[raw] = quote

    try:
        if sh_codes:
            _retry(lambda: _fetch_group("sh", sh_codes), max_retries=2, delay=1)
        if sz_codes:
            _retry(lambda: _fetch_group("sz", sz_codes), max_retries=2, delay=1)
    except Exception:
        pass

    return result


def fetch_batch(stock_list, source="sina"):
    """
    批量获取多只股票行情

    Args:
        stock_list: 列表，每项为 {"code": str, "market": str}
        source: 数据源

    Returns:
        dict: {code: StockQuote}
    """
    if source == "sina":
        # 新浪支持一次查询，比串行快
        codes = [item["code"] for item in stock_list]
        return fetch_sina_batch(codes)

    # 非新浪源回退到串行
    results = {}
    for item in stock_list:
        code = item["code"]
        market = item.get("market", "sh")
        print(f"  → 查询 {code}({market})...", end="")
        quote = fetch_single(code, market, source)
        if quote:
            results[code] = quote
            print(f" ¥{quote.price:.2f} {quote.change_pct:+.2f}%")
        else:
            print(" ❌ 失败")
    return results


if __name__ == "__main__":
    # 测试
    quote = fetch_single("600519", "sh")
    if quote:
        print(quote)
        print(f"  开盘: {quote.open_price}  最高: {quote.high}  最低: {quote.low}")
        print(f"  成交量: {quote.volume:.0f}手  成交额: {quote.amount:.0f}万")

    # 测试批量
    print("\n批量测试:")
    batch = fetch_sina_batch(["600519", "002594", "000001"])
    for code, q in batch.items():
        print(f"  {q}")

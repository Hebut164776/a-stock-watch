"""
策略分析模块 - 个股五维打分 & 卖出规则监控

数据获取复用 fetcher.py 的批量接口（消除重复代码）
"""

import sys
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from fetcher import fetch_sina_batch
from fundamental import enrich_with_fundamentals, fetch_valuation


def fetch_sina_kline(code, days=300):
    """从新浪获取日K线数据"""
    market = "sh" if code.startswith(("6", "9")) else "sz"
    url = (f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={days}")
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data and isinstance(data, list):
            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["day"])
            df["close"] = df["close"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["open"] = df["open"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df.sort_values("date")
    except Exception:
        pass
    return None


def fetch_index_kline(code="000300", days=300):
    """获取指数K线"""
    url = (f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol=sh{code}&scale=240&ma=no&datalen={days}")
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data and isinstance(data, list):
            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["day"])
            df["close"] = df["close"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["open"] = df["open"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df.sort_values("date")
    except Exception:
        pass
    return None


def calc_ma(df, period):
    if df is None or df.empty or len(df) < period:
        return None
    return df["close"].rolling(period).mean().iloc[-1]


def check_breakout(df):
    """检查是否放量突破2-3个月平台高点"""
    if df is None or df.empty or len(df) < 63:
        return False, False
    recent = df.tail(63)
    if len(recent) < 10:
        return False, False
    platform = recent.iloc[:-5]
    platform_high = platform["high"].max()
    latest_close = recent["close"].iloc[-1]
    latest_volume = recent["volume"].iloc[-1]
    avg_volume_20 = recent["volume"].tail(20).mean()
    is_breakout = latest_close >= platform_high * 0.99 if platform_high > 0 else False
    is_volume_spike = latest_volume >= avg_volume_20 * 1.5 if avg_volume_20 > 0 else False
    return is_breakout, is_volume_spike


# ---------- 五维打分 ----------

def analyze_stock(code):
    """对单只股票执行五维打分，返回得分详情"""
    code = code.strip()
    quotes = fetch_sina_batch([code])
    quote_dict = quotes.get(code)
    quote = quote_dict.to_dict() if quote_dict else None
    name = quote["name"] if quote else code

    scores = {"大盘": 0, "行业": 0, "业绩": 0, "估值": 0, "走势": 0}
    details = {"大盘": [], "行业": [], "业绩": [], "估值": [], "走势": []}
    warnings = []
    ma_data = {}

    # ===== 1. 大盘 =====
    hs300 = fetch_index_kline("000300", 300)
    if hs300 is not None and len(hs300) >= 200:
        hs300_close = hs300["close"]
        hs300["ma50"] = hs300_close.rolling(50).mean()
        hs300["ma200"] = hs300_close.rolling(200).mean()
        lc = hs300_close.iloc[-1]
        m50 = hs300["ma50"].iloc[-1]
        m200 = hs300["ma200"].iloc[-1]

        above_ma200 = lc > m200
        ma50_above_ma200 = m50 > m200
        details["大盘"].append({"label": "沪深300在200日均线上方", "value": f"收盘{lc:.0f}/MA200{m200:.0f}", "pass": bool(above_ma200)})
        details["大盘"].append({"label": "50日均线在200日均线上方", "value": f"MA50{m50:.0f}/MA200{m200:.0f}", "pass": bool(ma50_above_ma200)})
        if above_ma200: scores["大盘"] += 10
        if ma50_above_ma200: scores["大盘"] += 10
    else:
        details["大盘"].append({"label": "沪深300", "value": "获取失败", "pass": False})

    # ===== 2. 行业 =====
    if code.startswith("6"):
        industry_hint = "上海主板"
    elif code.startswith("00"):
        industry_hint = "深圳"
    elif code.startswith("30"):
        industry_hint = "创业板"
    elif code.startswith("68"):
        industry_hint = "科创板"
    else:
        industry_hint = "未知"
    details["行业"].append({"label": "市场板块", "value": industry_hint, "pass": True})
    scores["行业"] += 10

    if hs300 is not None and len(hs300) >= 60:
        hs300_change = (hs300["close"].iloc[-1] - hs300["open"].iloc[-60]) / hs300["open"].iloc[-60] * 100
    else:
        hs300_change = None

    stock_hist = fetch_sina_kline(code, 90)
    if stock_hist is not None and len(stock_hist) >= 60 and hs300_change is not None:
        stock_change = (stock_hist["close"].iloc[-1] - stock_hist["open"].iloc[-60]) / stock_hist["open"].iloc[-60] * 100
        beat = stock_change > hs300_change
        details["行业"].append({"label": "近3月相对大盘", "value": f"个股{stock_change:+.1f}% vs HS300{hs300_change:+.1f}%", "pass": bool(beat)})
        if beat: scores["行业"] += 10
    else:
        details["行业"].append({"label": "近3月相对大盘", "value": "数据不足", "pass": False})

    # ===== 3. 业绩 =====
    fin_info = {}
    if quote:
        try:
            url = f"http://money.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/{code}.phtml"
            resp = requests.get(url, timeout=10)
            resp.encoding = "gbk"
            html = resp.text
            rev_m = re.search(r'营业总收入[^<]*?(\d+\.?\d*)亿', html)
            profit_m = re.search(r'净利润[^<]*?(\d+\.?\d*)亿', html)
            if rev_m: fin_info["revenue"] = float(rev_m.group(1))
            if profit_m: fin_info["net_profit"] = float(profit_m.group(1))
        except Exception:
            pass

    for lbl in ["营收同比>=15%", "净利润同比>=20%", "ROE>=12%", "经营现金流为正"]:
        details["业绩"].append({"label": lbl, "value": "需APP核实", "pass": None})
    scores["业绩"] = 6

    # ===== 4. 估值 =====
    if quote and quote.get("price", 0) > 0:
        price = quote["price"]
        pe_val = None
        try:
            url = f"http://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/{code}.phtml"
            resp = requests.get(url, timeout=10)
            resp.encoding = "gbk"
            html = resp.text
            eps_m = re.search(r'每股收益[^<]*?([\d.]+)', html)
            if eps_m:
                eps = float(eps_m.group(1))
                if eps > 0:
                    pe_val = price / eps
        except Exception:
            pass

        if pe_val and pe_val > 0:
            pass_pe = pe_val < 30
            details["估值"].append({"label": "PE(TTM)<30", "value": f"{pe_val:.2f}", "pass": bool(pass_pe)})
            if pass_pe: scores["估值"] += 10
        else:
            details["估值"].append({"label": "PE(TTM)<30", "value": "未能获取" if pe_val is None else "PE为负", "pass": None})

        details["估值"].append({"label": "PEG<2", "value": "需APP核实", "pass": None})
    else:
        details["估值"].append({"label": "PE(TTM)<30", "value": "无行情", "pass": False})
        details["估值"].append({"label": "PEG<2", "value": "无行情", "pass": False})
    scores["估值"] += 5

    # ===== 5. 走势 =====
    hist = fetch_sina_kline(code, 300)
    if hist is not None and len(hist) >= 50:
        lc = hist["close"].iloc[-1]
        lv = hist["volume"].iloc[-1]
        m50 = calc_ma(hist, 50)
        m200 = calc_ma(hist, 200)
        ma_data = {"ma50": m50, "ma200": m200, "close": lc}

        if m50 is not None:
            above = lc > m50
            details["走势"].append({"label": "股价在50日均线上方", "value": f"¥{lc:.2f}/MA50¥{m50:.2f}", "pass": bool(above)})
            if above: scores["走势"] += 5
        else:
            details["走势"].append({"label": "股价在50日均线上方", "value": "数据不足", "pass": False})

        if m50 is not None and m200 is not None:
            golden = m50 > m200
            details["走势"].append({"label": "50日>200日均线", "value": f"MA50¥{m50:.2f}/MA200¥{m200:.2f}", "pass": bool(golden)})
            if golden: scores["走势"] += 5
        else:
            details["走势"].append({"label": "50日>200日均线", "value": "数据不足", "pass": False})

        is_breakout, is_vol = check_breakout(hist)
        details["走势"].append({"label": "突破2-3月平台高点", "value": "是" if is_breakout else "否", "pass": bool(is_breakout)})
        if is_breakout: scores["走势"] += 5

        avg_v20 = hist["volume"].tail(20).mean()
        vr = lv / avg_v20 if avg_v20 > 0 else 0
        details["走势"].append({"label": "放量>1.5倍", "value": f"{vr:.1f}x", "pass": bool(is_vol)})
        if is_vol: scores["走势"] += 5
    else:
        for lbl in ["股价在50日均线上方", "50日>200日均线", "突破平台高点", "放量1.5倍"]:
            details["走势"].append({"label": lbl, "value": "无数据", "pass": False})

    total = sum(scores.values())
    if total >= 80: conclusion = "🟢可以做"
    elif total >= 70: conclusion = "🟡小仓位试"
    else: conclusion = "🔴不做"

    return {
        "code": code,
        "name": name,
        "total": total,
        "scores": scores,
        "details": details,
        "conclusion": conclusion,
        "warning": "；".join(warnings),
        "current_price": quote["price"] if quote else None,
        "ma_data": ma_data,
    }


# ---------- 卖出规则 ----------

class SellSignals:
    """按策略文档定义的三条卖出规则"""
    STOP_LOSS_PCT = -8.0
    TAKE_PROFIT_PCT = 20.0
    MA50_EXIT = True

    @classmethod
    def check(cls, holding, ma50=None):
        """检查持仓是否触发卖出信号"""
        signals = []
        if holding.price <= 0:
            return signals

        if holding.profit_pct <= cls.STOP_LOSS_PCT:
            signals.append(("stop_loss",
                f"😵 止损！{holding.name}({holding.code}) 亏损{holding.profit_pct:.1f}% ≤ -8%"))

        if holding.profit_pct >= cls.TAKE_PROFIT_PCT:
            signals.append(("take_profit",
                f"💰 止盈！{holding.name}({holding.code}) 盈利{holding.profit_pct:.1f}% ≥ +20%，建议卖一半"))

        if cls.MA50_EXIT and ma50 is not None and holding.price > 0:
            if holding.price < ma50 and holding.profit_pct > 0:
                signals.append(("ma50_exit",
                    f"📉 {holding.name}({holding.code}) 跌破50日线(¥{ma50:.2f})，剩余仓位建议卖出"))

        return signals


# ---------- 历史评分记录 ----------

RECORDS_FILE = Path(__file__).parent / "score_history.json"


def load_score_history():
    if RECORDS_FILE.exists():
        try:
            with open(RECORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_score_history(records):
    RECORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def record_score(result):
    records = load_score_history()
    code = result["code"]
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    if code not in records:
        records[code] = []
    records[code].append({
        "date": today,
        "total": result["total"],
        "scores": result["scores"],
        "price": result["current_price"],
    })
    records[code] = records[code][-20:]
    save_score_history(records)


def show_score_history(code=None):
    records = load_score_history()
    if not records:
        return "暂无评分记录"
    lines = []
    if code:
        code = code.strip()
        if code in records:
            lines.append(f"📜 {code} 评分历史")
            lines.append("-" * 40)
            for r in reversed(records[code]):
                lines.append(f"  {r['date']}  总分{r['total']:>2}  价¥{r['price']:.2f}")
        else:
            return f"无 {code} 的评分记录"
    else:
        lines.append("📜 所有评分记录")
        lines.append("-" * 40)
        for c, items in sorted(records.items()):
            last = items[-1]
            lines.append(f"  {c}  最近: {last['total']}分  ({last['date']})")
    return "\n".join(lines)


# ---------- 批量分析 ----------

def analyze_batch(codes):
    results = []
    for code in codes:
        try:
            r = analyze_stock(code)
            # 补充基本面数据（PE/PB/营收增速等）
            try:
                r = enrich_with_fundamentals(r)
            except Exception:
                pass
            results.append(r)
        except Exception as e:
            results.append({"code": code, "name": "?", "total": 0, "error": str(e)})
    results.sort(key=lambda x: x.get("total", 0), reverse=True)
    return results


def format_batch_table(results):
    lines = ["📊 **多股评分对比**", "```"]
    lines.append(f"{'排名':>4} {'代码':>6} {'名称':<8} {'总分':>4} {'大盘':>4} {'行业':>4} {'业绩':>4} {'估值':>4} {'走势':>4}  建议")
    lines.append("-" * 70)
    for i, r in enumerate(results, 1):
        s = r.get("scores", {})
        line = (f"{i:>4} {r['code']:>6} {r['name']:<8} {r.get('total', 0):>4} "
                f"{s.get('大盘', 0):>4} {s.get('行业', 0):>4} "
                f"{s.get('业绩', 0):>4} {s.get('估值', 0):>4} "
                f"{s.get('走势', 0):>4}  {r.get('conclusion', '?')}")
        lines.append(line)
    lines.append("```")
    return "\n".join(lines)


# ---------- 快捷函数供 main.py 引用 ----------

def run_strategy(holdings):
    """对持仓列表执行策略分析，返回 (sell_signals, score_results)"""
    codes = [h.code for h in holdings]
    scores = analyze_batch(codes)
    score_map = {r["code"]: r for r in scores}

    all_signals = []
    for h in holdings:
        sr = score_map.get(h.code, {})
        ma_data = sr.get("ma_data", {})
        ma50 = ma_data.get("ma50")
        all_signals.extend(SellSignals.check(h, ma50))

    for r in scores:
        if r.get("total", 0) > 0:
            record_score(r)

    return all_signals, scores


if __name__ == "__main__":
    codes = sys.argv[1:]
    if not codes:
        print("用法: python strategy.py <代码1> <代码2> ...")
        sys.exit(1)
    results = analyze_batch(codes)
    print(format_batch_table(results))
    for r in results:
        print(f"\n📈 {r['name']}({r['code']})  总分{r['total']}/100  {r['conclusion']}")

"""
基本面数据抓取模块
通过 AKShare（东方财富底层）获取 PE/PB/营收/净利润/ROE 等数据

注：需要设置 NO_PROXY 环境变量绕过系统代理对东方财富 HTTPS 的限制
"""

import os
import re

# AKShare 需要 NO_PROXY 绕过系统代理
_NO_EASTMONEY = 'push2.eastmoney.com,push2his.eastmoney.com,*.eastmoney.com,eastmoney.com,emweb.securities.eastmoney.com'
_existing = os.environ.get('NO_PROXY', '')
if _NO_EASTMONEY not in _existing:
    os.environ['NO_PROXY'] = f"{_NO_EASTMONEY},{_existing}" if _existing else _NO_EASTMONEY

import requests
import akshare as ak
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout


HEADERS = {
    "Referer": "https://quote.eastmoney.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _safe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _latest_val(row, df, offset=0):
    """获取行中最新（第2列开始偏移）的值"""
    col = df.columns[2 + offset] if 2 + offset < len(df.columns) else None
    if col:
        return _safe_float(row.get(col))
    return None


def _latest_cols(df, n=4):
    """返回最新的n列名"""
    return list(df.columns[2:2+n])


def fetch_valuation(code):
    """
    获取股票的估值数据（PE/PB/总市值）
    使用东方财富 HTTP API（非HTTPS）

    Args:
        code: 股票代码

    Returns:
        dict: {pe, pb, total_mv, name}
    """
    market = 1 if code.startswith(("6", "9")) else 0
    url = "http://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": f"{market}.{code}",
        "fltt": "2",
        "fields": "f57,f58,f116,f162,f167",
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        d = resp.json().get("data")
        if not d:
            return None
        pe = d.get("f162")
        pb = d.get("f167")
        total_mv = d.get("f116")
        return {
            "code": code,
            "name": d.get("f58", ""),
            "pe": round(float(pe), 2) if pe and float(pe) > 0 else None,
            "pb": round(float(pb), 2) if pb and float(pb) > 0 else None,
            "total_mv": round(float(total_mv) / 1e8, 2) if total_mv else None,
        }
    except Exception:
        return None


def _fetch_financials_impl(code):
    """实际的AKShare财务数据抓取（由超时包装器调用）"""
    result = {
        "revenue_yoy": None,
        "profit_yoy": None,
        "roe": None,
        "eps": None,
        "gross_margin": None,
        "report_date": None,
    }
    try:
        df = ak.stock_financial_abstract(symbol=code)
        if df is None or df.empty:
            return result
    except Exception:
        return result

    # 列[0]=选项, 列[1]=指标, 列[2:]=数据（最新→最旧）
    time_cols = list(df.columns[2:])
    if time_cols:
        result["report_date"] = str(time_cols[0])

    # ---- 1. 营业总收入 ----
    rev_rows = df[df["指标"] == "营业总收入"]
    if not rev_rows.empty:
        for _, row in rev_rows.iterrows():
            if row["选项"] in ("常用指标", "主要指标", "单季度"):
                rev_latest = _latest_val(row, df, 0)   # 本期
                rev_prev = _latest_val(row, df, 4)     # 去年同期（4个季度前）
                if rev_latest and rev_prev and rev_prev > 0:
                    result["revenue_yoy"] = round((rev_latest / rev_prev - 1) * 100, 2)
                break

    # ---- 2. 归母净利润 ----
    profit_rows = df[df["指标"] == "归母净利润"]
    if not profit_rows.empty:
        for _, row in profit_rows.iterrows():
            if row["选项"] in ("常用指标", "主要指标", "单季度"):
                p_latest = _latest_val(row, df, 0)
                p_prev = _latest_val(row, df, 4)
                if p_latest and p_prev and p_prev > 0:
                    result["profit_yoy"] = round((p_latest / p_prev - 1) * 100, 2)
                break

    # ---- 3. 基本每股收益(EPS) ----
    eps_rows = df[df["指标"].str.contains("基本每股收益", na=False)]
    if not eps_rows.empty:
        for _, row in eps_rows.iterrows():
            if row["选项"] in ("常用指标", "主要指标", "单季度"):
                result["eps"] = _latest_val(row, df, 0)
                break

    # ---- 4. 净资产收益率(ROE) ----
    roe_rows = df[df["指标"].str.contains("净资产收益率", na=False)]
    if not roe_rows.empty:
        for _, row in roe_rows.iterrows():
            if row["选项"] in ("常用指标", "主要指标"):
                result["roe"] = _latest_val(row, df, 0)
                break

    # ---- 5. 毛利率 ----
    gm_rows = df[df["指标"].str.contains("毛利率", na=False)]
    if not gm_rows.empty:
        for _, row in gm_rows.iterrows():
            if row["选项"] in ("主要指标", "盈利能力"):
                result["gross_margin"] = _latest_val(row, df, 0)
                break

    return result


def _parse_financials_to_details(fin, details_业绩, scores):
    """将财务数据填充到评分详情中"""
    if fin.get("revenue_yoy") is not None:
        pass_rev = fin["revenue_yoy"] >= 15
        _update_detail(details_业绩, "营收同比>=15%", f"{fin['revenue_yoy']:+.2f}%", pass_rev)
        if pass_rev:
            scores["业绩"] = scores.get("业绩", 6) + 4

    if fin.get("profit_yoy") is not None:
        pass_profit = fin["profit_yoy"] >= 20
        _update_detail(details_业绩, "净利润同比>=20%", f"{fin['profit_yoy']:+.2f}%", pass_profit)
        if pass_profit:
            scores["业绩"] = scores.get("业绩", 6) + 5

    if fin.get("roe") is not None:
        pass_roe = fin["roe"] >= 12
        _update_detail(details_业绩, "ROE>=12%", f"{fin['roe']:.2f}%", pass_roe)
        if pass_roe:
            scores["业绩"] = scores.get("业绩", 6) + 3

    if fin.get("eps") is not None and fin["eps"] > 0:
        _update_detail(details_业绩, "每股收益", f"¥{fin['eps']:.2f}", True)


def _update_detail(details, label, value, passed):
    """更新或追加详情条目"""
    for item in details:
        if item["label"] == label:
            item["value"] = value
            item["pass"] = passed
            return
    details.append({"label": label, "value": value, "pass": passed})


def enrich_with_fundamentals(score_result):
    """
    给策略评分结果补充基本面数据

    Args:
        score_result: analyze_stock 返回的 dict

    Returns:
        修改后的 score_result
    """
    code = score_result["code"]

    # 1. 估值数据（PE/PB）
    val = fetch_valuation(code)
    if val:
        score_result["current_price"] = _latest_stock_price(code)
        pe = val.get("pe")
        details_估值 = score_result.setdefault("details", {}).setdefault("估值", [])
        scores = score_result.setdefault("scores", {})

        if pe is not None:
            pass_pe = pe < 30
            _update_detail(details_估值, "PE(TTM)<30", f"{pe:.2f}", pass_pe)
            # 先重置估值基础分
            base = 5
            if pass_pe:
                scores["估值"] = base + 10  # PE达标15分
            else:
                scores["估值"] = base
        else:
            scores["估值"] = max(scores.get("估值", 0), 5)

    # 2. 财务数据（营收增速/净利润/ROE/每股收益）
    fin = fetch_financials(code)
    if fin:
        details_业绩 = score_result.setdefault("details", {}).setdefault("业绩", [])
        scores = score_result.setdefault("scores", {})
        _parse_financials_to_details(fin, details_业绩, scores)

    # 如果还有PEG字段未补，标记一下
    details_估值 = score_result.setdefault("details", {}).setdefault("估值", [])
    has_peg = any(d["label"] == "PEG<2" for d in details_估值)
    if not has_peg:
        details_估值.append({"label": "PEG<2", "value": "需APP核实", "pass": None})

    # 如果还有经营现金流字段未补
    details_业绩 = score_result.setdefault("details", {}).setdefault("业绩", [])
    has_cf = any(d["label"] == "经营现金流为正" for d in details_业绩)
    if not has_cf:
        details_业绩.append({"label": "经营现金流为正", "value": "需APP核实", "pass": None})

    # 3. 重新算总分
    total = sum(scores.values())
    score_result["total"] = total
    if total >= 80:
        score_result["conclusion"] = "🟢可以做"
    elif total >= 70:
        score_result["conclusion"] = "🟡小仓位试"
    else:
        score_result["conclusion"] = "🔴不做"

    return score_result


def _latest_stock_price(code):
    """获取最新股价（从估值接口返回）"""
    val = fetch_valuation(code)
    if val:
        return None  # push2 接口没返回 price 字段
    return None


def batch_fetch_valuations(codes):
    """批量获取估值数据"""
    results = {}
    for code in codes:
        try:
            val = fetch_valuation(code)
            if val:
                results[code] = val
        except Exception:
            pass
    return results


def fetch_financials(code, timeout=25):
    """
    通过 AKShare 获取财务指标数据（带超时保护）

    stock_financial_abstract 接口有时较慢，
    使用线程超时避免整个流程挂起

    Args:
        code: 股票代码
        timeout: 超时秒数（默认25s）

    Returns:
        dict: {revenue_yoy, profit_yoy, roe, eps, gross_margin}
    """
    result = {
        "revenue_yoy": None,
        "profit_yoy": None,
        "roe": None,
        "eps": None,
        "gross_margin": None,
        "report_date": None,
    }
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_fetch_financials_impl, code)
            return fut.result(timeout=timeout)
    except FuturesTimeout:
        pass
    except Exception:
        pass
    return result


if __name__ == "__main__":
    import json

    # 测试比亚迪
    print("=== 比亚迪 估值 ===")
    val = fetch_valuation("002594")
    print(json.dumps(val, ensure_ascii=False, indent=2))

    print("\n=== 比亚迪 财务指标 ===")
    fin = fetch_financials("002594")
    print(json.dumps(fin, ensure_ascii=False, indent=2))

    # 测试伯特利
    print("\n=== 伯特利 财务指标 ===")
    fin2 = fetch_financials("603596")
    print(json.dumps(fin2, ensure_ascii=False, indent=2))

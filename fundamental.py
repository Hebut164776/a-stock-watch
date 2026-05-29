"""
基本面数据抓取模块
通过东方财富 HTTP API（非HTTPS）获取估值和财务数据
回避 HTTPS 被系统网络限制的问题
"""

import re
import requests
from datetime import datetime

HEADERS = {
    "Referer": "https://quote.eastmoney.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def fetch_valuation(code):
    """
    获取股票的估值数据（PE/PB/总市值）
    使用东方财富 HTTP API

    Args:
        code: 股票代码

    Returns:
        dict: {pe, pb, total_mv, name} 或 None
    """
    market = 1 if code.startswith(("6", "9")) else 0  # 1=沪 0=深
    url = "http://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": f"{market}.{code}",
        "fltt": "2",
        "fields": "f57,f58,f116,f162,f167,f43,f170",
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()
        d = data.get("data")
        if not d:
            return None

        pe = d.get("f162")
        pb = d.get("f167")
        total_mv = d.get("f116")
        name = d.get("f58", "")
        price = d.get("f43", 0)
        change_pct = d.get("f170", 0)

        result = {
            "code": code,
            "name": name,
            "pe": round(float(pe), 2) if pe and float(pe) > 0 else None,
            "pb": round(float(pb), 2) if pb and float(pb) > 0 else None,
            "total_mv": round(float(total_mv) / 1e8, 2) if total_mv else None,  # 亿
            "price": float(price) / 100 if price else None,
            "change_pct": float(change_pct) / 100 if change_pct else None,
        }
        return result
    except Exception:
        return None


def fetch_financial_summary(code):
    """
    从东方财富 HTTP API 获取财务指标摘要

    注意：免费接口无法稳定获取营收增速和净利润增速，
    需要这些数据的用户可在券商APP核实后手动填入。

    Args:
        code: 股票代码

    Returns:
        dict: 财务数据
    """
    result = {
        "revenue_yoy": None,    # 营收同比(%)
        "profit_yoy": None,     # 净利润同比(%)
        "roe": None,            # 净资产收益率(%)
        "eps": None,            # 每股收益
        "report_date": None,    # 报告期
    }

    # 东方财富 datacenter-web API（HTTP 方式）
    # 财务数据接口需要特定的 reportName，不同环境可能不同
    # 这里尝试股票基本面核心指标
    try:
        url = "http://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            "reportName": "RPT_LICO_FN_CPD",
            "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,EPS,WEIGHTAVG_ROE,GROSS_PROFIT_MARGIN",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageNumber": 1,
            "pageSize": 1,
            "sortTypes": -1,
            "sortColumns": "NOTICE_DATE",
            "source": "WEB",
            "client": "WEB",
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()
        if data.get("result") and data["result"].get("data"):
            d = data["result"]["data"][0]
            result["eps"] = float(d.get("EPS", 0)) if d.get("EPS") else None
            result["roe"] = float(d.get("WEIGHTAVG_ROE", 0)) if d.get("WEIGHTAVG_ROE") else None
            result["report_date"] = str(d.get("REPORT_DATE", ""))[:10]
    except Exception:
        pass

    if result["eps"] is None:
        # 备选：从新浪业绩预测页面尝试抓取
        try:
            url = f"http://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/{code}.phtml"
            resp = requests.get(url, timeout=10)
            resp.encoding = "gbk"
            html = resp.text
            eps_m = re.search(r'([\d.]+)元.*?(?:基本)?每股收益', html)
            if not eps_m:
                eps_m = re.search(r'(?:基本)?每股收益.*?([\d.]+)元', html)
            if eps_m:
                result["eps"] = float(eps_m.group(1))
        except Exception:
            pass

    return result


def batch_fetch_valuations(codes):
    """
    批量获取估值数据

    Args:
        codes: list of stock codes

    Returns:
        dict: {code: {pe, pb, ...}}
    """
    results = {}
    for code in codes:
        try:
            val = fetch_valuation(code)
            if val:
                results[code] = val
        except Exception:
            pass
    return results


def enrich_with_fundamentals(score_result):
    """
    给策略评分结果补充基本面数据（PE、营收增速等）
    修改 score_result 中的 details 和 scores

    Args:
        score_result: analyze_stock 返回的 dict
    """
    code = score_result["code"]
    val = fetch_valuation(code)
    fin = fetch_financial_summary(code)

    if val:
        pe = val.get("pe")
        score_result["current_price"] = val.get("price")

        # 更新估值维度
        details_估值 = score_result.setdefault("details", {}).setdefault("估值", [])
        scores = score_result.setdefault("scores", {})

        if pe is not None:
            pass_pe = pe < 30
            # 替换 "PE(TTM)<30: 未能获取" 条目
            for item in details_估值:
                if item["label"] == "PE(TTM)<30":
                    item["value"] = f"{pe:.2f}"
                    item["pass"] = bool(pass_pe)
                    break
            else:
                details_估值.append({"label": "PE(TTM)<30", "value": f"{pe:.2f}", "pass": bool(pass_pe)})
            # 重置估值基础分，重新计算
            if pass_pe:
                scores["估值"] = max(scores.get("估值", 0), 15)  # PE达标给高分
            else:
                scores["估值"] = max(scores.get("估值", 0), 5)   # 不给分
        else:
            scores["估值"] = max(scores.get("估值", 0), 5)

    if fin:
        # 更新业绩维度
        roe = fin.get("roe")
        eps = fin.get("eps")
        details_业绩 = score_result.setdefault("details", {}).setdefault("业绩", [])
        scores = score_result.setdefault("scores", {})

        score_业绩 = 6  # 基础分

        if roe is not None:
            pass_roe = roe >= 12
            for item in details_业绩:
                if item["label"] == "ROE>=12%":
                    item["value"] = f"{roe:.2f}%"
                    item["pass"] = bool(pass_roe)
                    break
            if pass_roe:
                score_业绩 += 5

        if eps is not None and eps > 0:
            score_业绩 += 3

        detail_map = {d["label"]: d for d in details_业绩}

        if "营收同比>=15%" not in detail_map:
            details_业绩.append({"label": "营收同比>=15%", "value": "需APP核实", "pass": None})
        if "净利润同比>=20%" not in detail_map:
            details_业绩.append({"label": "净利润同比>=20%", "value": "需APP核实", "pass": None})
        if "经营现金流为正" not in detail_map:
            details_业绩.append({"label": "经营现金流为正", "value": "需APP核实", "pass": None})

        scores["业绩"] = score_业绩

    # 根据 PE 补充 PEG 计算
    pass_pe = val and val.get("pe") and val["pe"] < 30
    if val and val.get("pe") and fin and fin.get("roe"):
        details_估值 = score_result.setdefault("details", {}).setdefault("估值", [])
        for item in details_估值:
            if item["label"] == "PEG<2":
                item["value"] = f"PE={val['pe']:.1f}, ROE={fin['roe']:.1f}%"
                # 粗略认为ROE高则PEG低
                if val["pe"] / max(fin["roe"], 1) < 2:
                    item["pass"] = True
                else:
                    item["pass"] = None
                break

    # 重新算总分
    total = sum(scores.values())
    score_result["total"] = total
    if total >= 80:
        score_result["conclusion"] = "🟢可以做"
    elif total >= 70:
        score_result["conclusion"] = "🟡小仓位试"
    else:
        score_result["conclusion"] = "🔴不做"

    return score_result


if __name__ == "__main__":
    import json

    # 测试 比亚迪
    val = fetch_valuation("002594")
    print(f"估值: {json.dumps(val, ensure_ascii=False, indent=2)}")

    fin = fetch_financial_summary("002594")
    print(f"财务: {json.dumps(fin, ensure_ascii=False, indent=2)}")

    # 测试 中国巨石
    val2 = fetch_valuation("600176")
    print(f"\n中国巨石: {json.dumps(val2, ensure_ascii=False, indent=2)}")

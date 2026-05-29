#!/usr/bin/env python3
"""
自选观察列表管理工具 - 独立于持仓管理

使用单独的 watchlist.json 存储，不参与盈亏计算。
观察股可用五维策略分析评分，支持观察→持仓转换。

用法:
  python watcher.py list                # 列出观察列表
  python watcher.py add 601138          # 添加（自动获取名称）
  python watcher.py remove 601138       # 移除
  python watcher.py score               # 观察列表五维评分
  python watcher.py score 601138 000333 # 指定股票评分
  python watcher.py to-hold 601138      # 观察→持仓（交互式）
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"

import platform
if platform.system() == "Windows":
    os.system("color")

WATCHLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


# ─── 数据层 ───────────────────────────────────────────────

def load_watchlist():
    """加载观察列表"""
    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("stocks", [])
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return []


def save_watchlist(stocks):
    """保存观察列表"""
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump({"stocks": stocks}, f, ensure_ascii=False, indent=2)


def _fetch_stock_name(code):
    """从新浪获取股票名称"""
    try:
        import requests
        market = "sh" if code.startswith(("6", "9")) else "sz"
        url = f"http://hq.sinajs.cn/list={market}{code}"
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = "gbk"
        parts = resp.text.split('="')
        if len(parts) >= 2:
            values = parts[1].rstrip('";').split(",")
            if values[0]:
                return values[0]
    except Exception:
        pass
    return None


# ─── 命令行 ───────────────────────────────────────────────

def cmd_list(args):
    """列出观察列表"""
    stocks = load_watchlist()
    if not stocks:
        print("📭 观察列表为空")
        return

    print(f"🔭 共 {len(stocks)} 只观察股:")
    print("=" * 40)
    for i, s in enumerate(stocks, 1):
        print(f"  {i:>2}. {s['code']}  {s.get('name', '')}")
    print("=" * 40)


def cmd_add(args):
    """添加观察股"""
    stocks = load_watchlist()
    code = args.code

    # 检查是否已存在
    for s in stocks:
        if s["code"] == code:
            print(f"⚠️  {s.get('name', code)}({code}) 已在观察列表中")
            return

    # 自动获取名称
    print(f"  🔍 正在获取 {code} 名称...", end=" ")
    name = _fetch_stock_name(code)
    if name:
        print(name)
    else:
        name = code
        print("⚠️ 未获取到")

    stocks.append({"code": code, "name": name})
    save_watchlist(stocks)
    print(f"✅ 已添加 {name}({code}) 到观察列表")


def cmd_remove(args):
    """移除观察股"""
    stocks = load_watchlist()
    code = args.code

    found = [s for s in stocks if s["code"] == code]
    if not found:
        print(f"❌ 未找到 {code}")
        return

    stock = found[0]
    stocks = [s for s in stocks if s["code"] != code]
    save_watchlist(stocks)
    print(f"✅ 已移除 {stock.get('name', '')}({code})")


def cmd_score(args):
    """观察列表五维评分"""
    from strategy import analyze_batch, format_batch_table, record_score

    if args.codes:
        codes = args.codes
    else:
        stocks = load_watchlist()
        codes = [s["code"] for s in stocks]

    if not codes:
        print("📭 观察列表为空，请先添加或指定股票代码")
        return

    print(f"🔭 观察列表分析（共 {len(codes)} 只）")
    results = analyze_batch(codes)
    print()
    print(format_batch_table(results))

    # 显示详情
    for r in results:
        if r.get("error"):
            print(f"❌ {r['code']}: {r['error']}")
            continue
        print(f"\n  📈 {r['name']}({r['code']})  总分{r['total']}/100  {r['conclusion']}")
        for dim in ["大盘", "行业", "业绩", "估值", "走势"]:
            dim_detail = r.get("details", {}).get(dim, [])
            dim_score = r.get("scores", {}).get(dim, 0)
            icon = "🟢" if dim_score >= 16 else "🟡" if dim_score >= 10 else "🔴"
            labels = " | ".join(
                f"{'✅' if d['pass'] else '❌' if d['pass'] is False else '⬜'} {d['label']}: {d['value']}"
                for d in dim_detail
            )
            print(f"    {icon} {dim} {dim_score}/20  {labels}")

    # 保存历史
    for r in results:
        if r.get("total", 0) > 0:
            record_score(r)
    print("\n📝 评分已记录")

    return results


def cmd_to_hold(args):
    """观察→持仓转换（交互式输入成本和股数）"""
    code = args.code

    stocks = load_watchlist()
    found = [s for s in stocks if s["code"] == code]
    if not found:
        print(f"❌ 观察列表中未找到 {code}，请先用 add 添加")
        return

    stock = found[0]
    name = stock.get("name", code)

    print(f"🔭 {name}({code}) → 📈 持仓")
    print("请输入持仓信息：")

    try:
        cost_str = input(f"  成本价（如 89.861）: ")
        cost = float(cost_str)
        if cost <= 0:
            print("❌ 成本价必须大于0")
            return
    except (ValueError, EOFError):
        print("❌ 无效输入")
        return

    try:
        shares_str = input(f"  持股数（如 200）: ")
        shares = int(shares_str)
        if shares <= 0:
            print("❌ 持股数必须大于0")
            return
    except (ValueError, EOFError):
        print("❌ 无效输入")
        return

    market = "sh" if code.startswith(("6", "9")) else "sz"

    # 生成 manage.py 命令并输出
    cmd = f'python manage.py add {code} {cost} {shares} --market {market}'
    print(f"\n  请执行以下命令添加持仓：")
    print(f"\n    cd D:\\claw\\a-stock-watch")
    print(f"    $env:PYTHONIOENCODING='utf-8'; {cmd}")
    print()

    # 询问是否从观察列表移除
    try:
        rm = input("  是否从观察列表移除？(Y/n): ").strip().lower()
        if rm != "n":
            stocks = [s for s in stocks if s["code"] != code]
            save_watchlist(stocks)
            print(f"  ✅ 已从观察列表移除 {name}")
    except (EOFError, KeyboardInterrupt):
        pass


def main():
    parser = argparse.ArgumentParser(
        description="自选观察列表管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python watcher.py list                     # 列出观察列表
  python watcher.py add 601138               # 添加工业富联
  python watcher.py remove 601138            # 移除
  python watcher.py score                    # 观察列表五维评分
  python watcher.py score 601138 000333      # 指定股票评分
  python watcher.py to-hold 601138           # 观察→持仓
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    p_list = subparsers.add_parser("list", aliases=["ls"], help="列出观察列表")
    p_list.set_defaults(func=cmd_list)

    # add
    p_add = subparsers.add_parser("add", help="添加观察股（自动获取名称）")
    p_add.add_argument("code", help="股票代码")
    p_add.set_defaults(func=cmd_add)

    # remove
    p_rm = subparsers.add_parser("remove", aliases=["rm", "del"], help="移除观察股")
    p_rm.add_argument("code", help="股票代码")
    p_rm.set_defaults(func=cmd_remove)

    # score
    p_score = subparsers.add_parser("score", aliases=["analyze"], help="五维评分")
    p_score.add_argument("codes", nargs="*", help="股票代码（留空则分析全部观察列表）")
    p_score.set_defaults(func=cmd_score)

    # to-hold
    p_th = subparsers.add_parser("to-hold", aliases=["2hold", "add-hold"], help="观察→持仓（交互式输入）")
    p_th.add_argument("code", help="股票代码")
    p_th.set_defaults(func=cmd_to_hold)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()

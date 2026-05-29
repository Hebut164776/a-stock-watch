#!/usr/bin/env python3
"""
A股实时股价监控 + 盈亏计算 + 策略分析 → main.py

功能:
  基本 - 持仓盈亏查询
  策略 - 五维打分排名 + 卖出信号监控 + 评分历史
  监控 - 实时刷新模式

使用:
  python main.py                   # 单次查询（含卖出信号）
  python main.py --score           # 单次查询 + 五维打分排名
  python main.py --watch           # 实时监控模式（每30s刷新）
  python main.py --history         # 查看评分历史
  python main.py --history 601179  # 查看某只的历史评分
  python main.py --source tencent  # 指定数据源
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"

from portfolio import load_config, Portfolio
from fetcher import fetch_single
from views import (
    print_header, print_row, print_summary,
    print_alert, print_footer, print_compact, BOLD,
)
from strategy import (
    run_strategy, analyze_stock, analyze_batch,
    format_batch_table, show_score_history, SellSignals,
)
import platform

if platform.system() == "Windows":
    os.system("color")


def run_once(holdings, data_source="sina", config=None, with_score=False):
    """单次查询"""
    portfolio = Portfolio()
    for h in holdings:
        quote = fetch_single(h.code, h.market, data_source)
        if quote:
            h.calc(quote.price, quote.change, quote.change_pct)
        else:
            print(f"  ❌ {h.name}({h.code}) 查询失败")
        portfolio.holdings.append(h)

    portfolio.update()

    print_header()
    for h in portfolio.holdings:
        print_row(h)
    print_summary(portfolio)

    # ---------- 策略分析：卖出信号 + 评分 ----------
    signals, score_results = run_strategy(holdings)

    # 卖出信号
    if signals:
        print("\n" + "=" * 50)
        print(BOLD("🚨 卖出信号"))
        for sig_type, msg in signals:
            print(f"  {msg}")
        print("=" * 50)

    # 评分排名
    if with_score and score_results:
        print()
        print(format_batch_table(score_results))

    # 传统止损止盈（兼容旧配置）
    stop_loss = config.get("stop_loss_pct", 0) if config else 0
    take_profit = config.get("take_profit_pct", 0) if config else 0
    has_old_alerts = False
    if stop_loss or take_profit:
        old_alerts = []
        for h in portfolio.holdings:
            old_alerts.extend(print_alert(h, stop_loss, take_profit))
        # 只在没触发新规则时才显示旧的（避免重复）
        if old_alerts and not signals:
            print("\n" + "=" * 50)
            print("🚨 提醒")
            for a in old_alerts:
                print(a)
            print("=" * 50)
            has_old_alerts = True

    print_footer()
    return portfolio


def watch_mode(holdings, data_source="sina", config=None, interval=30):
    """实时监控模式"""
    refresh = config.get("refresh_interval", interval) if config else interval

    try:
        while True:
            portfolio = Portfolio()
            for h in holdings:
                quote = fetch_single(h.code, h.market, data_source)
                if quote:
                    h.calc(quote.price, quote.change, quote.change_pct)
                portfolio.holdings.append(h)

            portfolio.update()
            print_compact(portfolio)

            # 卖出信号检测
            signals, _ = run_strategy(holdings)
            for sig_type, msg in signals:
                print(f"\n🚨 {msg}")

            # 旧版止损止盈
            stop_loss = config.get("stop_loss_pct", 0) if config else 0
            take_profit = config.get("take_profit_pct", 0) if config else 0
            if stop_loss or take_profit and not signals:
                for h in portfolio.holdings:
                    alerts = print_alert(h, stop_loss, take_profit)
                    for a in alerts:
                        print(f"\n🚨 {a}")

            time.sleep(refresh)

    except KeyboardInterrupt:
        print("\n\n👋 已退出监控")


def main():
    parser = argparse.ArgumentParser(
        description="A股实时股价监控 + 盈亏计算 + 策略分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                     # 单次查询(含卖出信号)
  python main.py --score             # +五维打分排名
  python main.py --watch             # 实时监控
  python main.py --history           # 查看评分历史
  python main.py --history 601179    # 查看某只历史评分
  python main.py --source tencent    # 指定数据源
  python main.py --skills            # 从技能加载持仓
  python main.py --dry-run           # 仅显示配置
        """,
    )
    parser.add_argument("--score", action="store_true", help="显示五维打分排名")
    parser.add_argument("--history", nargs="?", const="__all__", default=None, metavar="CODE",
                        help="查看评分历史，可选指定股票代码")
    parser.add_argument("--watch", "-w", action="store_true", help="实时监控模式")
    parser.add_argument("--source", "-s", default="sina", choices=["sina", "tencent", "eastmoney"], help="数据源")
    parser.add_argument("--interval", "-i", type=int, default=30, help="刷新间隔（秒）")
    parser.add_argument("--skills", action="store_true", help="从已安装技能加载持仓")
    parser.add_argument("--config", "-c", default="config.yaml", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅显示配置，不发起网络请求")

    args = parser.parse_args()

    # --history 走历史查询，不需要加载持仓
    if args.history is not None:
        code = None if args.history == "__all__" else args.history
        # 支持名称别名
        if code:
            try:
                holdings, cfg = load_config(args.config)
                name_map = {s["name"]: s["code"] for s in cfg.get("stocks", []) if s.get("name")}
                if code in name_map:
                    code = name_map[code]
            except Exception:
                pass
        print(show_score_history(code))
        return

    # 加载持仓
    if args.skills:
        try:
            from portfolio import load_from_skills
            holdings, _ = load_from_skills()
            config = {}
        except (FileNotFoundError, Exception) as e:
            print(f"❌ 从技能加载持仓失败: {e}\n   请先在 config.yaml 中配置持仓")
            sys.exit(1)
    else:
        try:
            holdings, config = load_config(args.config)
        except FileNotFoundError:
            print(f"❌ 未找到配置文件: {args.config}\n   请先添加持仓，如: python manage.py add 002594 89.861 200")
            sys.exit(1)

    data_source = args.source
    print(f"📡 数据源: {data_source.upper()}")
    print(f"📈 共 {len(holdings)} 只持仓")
    for h in holdings:
        print(f"   {h.code} {h.name}: 成本¥{h.cost} × {h.shares}股")

    if args.dry_run:
        print("\n✅ Dry-run 模式，不发起网络请求。")
        return

    if args.watch:
        watch_mode(holdings, data_source, config, args.interval)
    else:
        run_once(holdings, data_source, config, with_score=args.score)


if __name__ == "__main__":
    main()

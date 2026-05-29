#!/usr/bin/env python3
"""
A股持仓管理工具 - 添加/删除/列出/导入/导出持仓
免去手动编辑 config.yaml 的麻烦

用法:
  python manage.py list                          # 列出所有持仓
  python manage.py add 600519 180.0 100  # 添加持仓（自动获取名称）
  python manage.py add 000001 12.5 500 --market sz
  python manage.py remove 600519                  # 删除持仓
  python manage.py update 600519 --cost 190.0     # 修改成本价
  python manage.py update 600519 --shares 200     # 修改持股数
  python manage.py update 600519 --name 贵州茅台集团  # 修改名称
  python manage.py clear                          # 清空所有持仓
  python manage.py settings                       # 查看当前设置
  python manage.py settings --stop-loss -10       # 修改止损
  python manage.py settings --take-profit 20      # 修改止盈
  python manage.py settings --refresh 60          # 修改刷新间隔
  python manage.py export                         # 导出到技能数据格式
  python manage.py import-stocks                  # 从技能数据导入
  python manage.py total                          # 显示持仓汇总
"""

import sys
import os
import json
import argparse
import copy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
SKILL_STOCKS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "skills", "a-stock-portfolio-monitor", "data", "stocks.json"
)


def load_config_raw(path=CONFIG_PATH):
    """加载原始配置"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config, path=CONFIG_PATH):
    """保存配置，保留注释和格式"""
    yaml_str = yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False, width=1000)
    # 把字符串值里的引号保持干净
    with open(path, "w", encoding="utf-8") as f:
        f.write(yaml_str)


def _normalize_stock(stock):
    """统一股票记录格式"""
    s = {}
    s["code"] = str(stock["code"])
    s["name"] = str(stock.get("name", ""))
    s["cost"] = float(stock.get("cost", 0))
    s["shares"] = int(stock.get("shares", stock.get("qty", 0)))
    s["market"] = str(stock.get("market", "sh"))
    if s["market"] not in ("sh", "sz"):
        # 自动识别市场
        code = s["code"]
        if code.startswith(("6", "9")):
            s["market"] = "sh"
        elif code.startswith(("0", "2", "3")):
            s["market"] = "sz"
        else:
            s["market"] = "sh"
    return s


def cmd_list(args):
    """列出所有持仓"""
    config = load_config_raw()
    stocks = config.get("stocks", [])
    if not stocks:
        print("📭 持仓为空")
        return

    print(f"📈 共 {len(stocks)} 只持仓:")
    print("=" * 65)
    print(f"{'代码':>8} {'名称':<10} {'成本价':>8} {'持股数':>8} {'市场':>5} {'总成本':>10}")
    print("-" * 65)
    total_cost = 0
    for s in stocks:
        c = float(s.get("cost", 0))
        q = int(s.get("shares", 0))
        cost_total = round(c * q, 2)
        total_cost += cost_total
        market_name = "上海" if s.get("market", "sh") == "sh" else "深圳"
        print(f"{str(s['code']):>8} {s.get('name', ''):<10} ¥{c:<8.2f} {q:>8} {market_name:>5} ¥{cost_total:>9,.2f}")
    print("-" * 65)
    print(f"{'':>8} {'合计':<10} {'':>8} {'':>8} {'':>5} ¥{total_cost:>9,.2f}")
    print("=" * 65)
    print(f"止损线: {config.get('stop_loss_pct', 0):+.1f}%")
    print(f"止盈线: {config.get('take_profit_pct', 0):+.1f}%")
    print(f"刷新间隔: {config.get('refresh_interval', 30)}秒")


def fetch_stock_name(code, market):
    """自动从网络获取股票名称"""
    try:
        # 通过新浪接口获取股票名称
        url = f"http://hq.sinajs.cn/list={market}{code}"
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        import requests
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


def cmd_add(args):
    """添加持仓"""
    config = load_config_raw()
    stocks = config.get("stocks", [])

    code = args.code
    cost = args.cost
    shares = args.shares
    market = args.market or ("sh" if code.startswith(("6", "9")) else "sz")

    # 检查是否已存在
    for s in stocks:
        if s["code"] == code:
            print(f"⚠️  {s.get('name', code)}({code}) 已存在")
            print(f"   使用 `manage.py update {code} --cost X --shares Y` 修改")
            return

    # 自动获取股票名称
    print(f"  🔍 正在获取 {code} 名称...", end=" ")
    name = fetch_stock_name(code, market)
    if name:
        print(f"{name}")
    else:
        name = code
        print("⚠️ 未获取到，暂用代码代替")

    stock = {"code": code, "name": name, "cost": cost, "shares": shares, "market": market}
    stock = _normalize_stock(stock)
    stocks.append(stock)
    config["stocks"] = stocks
    save_config(config)

    print(f"✅ 已添加 {stock['name']}({stock['code']})")
    print(f"   成本 ¥{stock['cost']:.3f} × {stock['shares']}股")
    print(f"   市场: {'上海' if stock['market'] == 'sh' else '深圳'}")


def cmd_remove(args):
    """删除持仓"""
    config = load_config_raw()
    stocks = config.get("stocks", [])
    code = args.code

    found = [s for s in stocks if s["code"] == code]
    if not found:
        print(f"❌ 未找到 {code}")
        return

    stock = found[0]
    stocks = [s for s in stocks if s["code"] != code]
    config["stocks"] = stocks
    save_config(config)

    print(f"✅ 已删除 {stock.get('name', '')}({code})")


def cmd_update(args):
    """修改持仓"""
    config = load_config_raw()
    stocks = config.get("stocks", [])
    code = args.code

    found = [s for s in stocks if s["code"] == code]
    if not found:
        print(f"❌ 未找到 {code}")
        return

    stock = found[0]
    changed = []
    if args.name is not None:
        stock["name"] = args.name
        changed.append(f"名称 → {args.name}")
    if args.cost is not None:
        stock["cost"] = args.cost
        changed.append(f"成本价 → ¥{args.cost}")
    if args.shares is not None:
        stock["shares"] = args.shares
        changed.append(f"持股数 → {args.shares}")
    if args.market is not None:
        stock["market"] = args.market
        changed.append(f"市场 → {'上海' if args.market == 'sh' else '深圳'}")

    if changed:
        save_config(config)
        print(f"✅ {code} 已更新:")
        for c in changed:
            print(f"   • {c}")
        stock = _normalize_stock(stock)
        print(f"   现: {stock['name']} ¥{stock['cost']} × {stock['shares']}股 "
              f"({'上海' if stock['market'] == 'sh' else '深圳'})")
    else:
        print("⚠️ 未指定要修改的字段 (使用 --cost / --shares / --name / --market)")


def cmd_clear(args):
    """清空持仓"""
    if not args.yes:
        confirm = input("⚠️  确定清空所有持仓？(y/N): ")
        if confirm.lower() != "y":
            print("已取消")
            return
    config = load_config_raw()
    config["stocks"] = []
    save_config(config)
    print("✅ 已清空所有持仓")


def cmd_settings(args):
    """查看/修改设置"""
    config = load_config_raw()

    # 获取当前值
    stop_loss = config.get("stop_loss_pct", 0)
    take_profit = config.get("take_profit_pct", 0)
    refresh = config.get("refresh_interval", 30)
    source = config.get("data_source", "sina")

    # 修改模式
    changed = False
    if args.stop_loss is not None:
        config["stop_loss_pct"] = args.stop_loss
        changed = True
        print(f"📊 止损线: {stop_loss:+.1f}% → {args.stop_loss:+.1f}%")
    if args.take_profit is not None:
        config["take_profit_pct"] = args.take_profit
        changed = True
        print(f"📊 止盈线: {take_profit:+.1f}% → {args.take_profit:+.1f}%")
    if args.refresh is not None:
        config["refresh_interval"] = args.refresh
        changed = True
        print(f"📊 刷新间隔: {refresh}s → {args.refresh}s")
    if args.source is not None:
        config["data_source"] = args.source
        changed = True
        print(f"📊 数据源: {source} → {args.source}")

    if changed:
        save_config(config)
        print("✅ 设置已保存")
    else:
        # 查看模式
        print("📋 当前设置:")
        print(f"  数据源:     {source}")
        print(f"  止损线:     {stop_loss:+.1f}%")
        print(f"  止盈线:     {take_profit:+.1f}%")
        print(f"  刷新间隔:   {refresh}s")

        print(f"\n修改方法:")
        print(f"  python manage.py settings --stop-loss -8")
        print(f"  python manage.py settings --take-profit 15")
        print(f"  python manage.py settings --refresh 60")
        print(f"  python manage.py settings --source tencent")


def cmd_export(args):
    """导出到技能数据格式"""
    config = load_config_raw()
    stocks = config.get("stocks", [])

    skill_data = {
        "stocks": [],
        "settings": {
            "stop_loss_pct": config.get("stop_loss_pct", 0),
            "take_profit_pct": config.get("take_profit_pct", 0),
        }
    }
    for s in stocks:
        skill_data["stocks"].append({
            "code": s["code"],
            "name": s.get("name", ""),
            "cost": float(s.get("cost", 0)),
            "qty": int(s.get("shares", 0)),
            "market": s.get("market", "sh"),
        })

    os.makedirs(os.path.dirname(SKILL_STOCKS_PATH), exist_ok=True)
    with open(SKILL_STOCKS_PATH, "w", encoding="utf-8") as f:
        json.dump(skill_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已导出 {len(stocks)} 只持仓到技能数据: {SKILL_STOCKS_PATH}")


def cmd_import_stocks(args):
    """从技能数据导入"""
    if not os.path.exists(SKILL_STOCKS_PATH):
        print(f"❌ 技能数据文件不存在: {SKILL_STOCKS_PATH}")
        return

    with open(SKILL_STOCKS_PATH, "r", encoding="utf-8") as f:
        skill_data = json.load(f)

    skill_stocks = []
    for s in skill_data.get("stocks", []):
        skill_stocks.append({
            "code": s["code"],
            "name": s.get("name", ""),
            "cost": float(s.get("cost", 0)),
            "shares": int(s.get("qty", 0)),
            "market": s.get("market", "sh"),
        })

    if not skill_stocks:
        print("⚠️  技能数据中没有持仓")
        return

    # 导入策略：追加或替换
    config = load_config_raw()
    existing_codes = {s["code"] for s in config.get("stocks", [])}
    new_count = 0
    update_count = 0

    for s in skill_stocks:
        if s["code"] in existing_codes:
            # 更新已有
            for existing in config["stocks"]:
                if existing["code"] == s["code"]:
                    existing.update(s)
                    update_count += 1
                    break
        else:
            config["stocks"].append(s)
            new_count += 1

    config["stocks"] = config.get("stocks", [])
    save_config(config)
    print(f"✅ 从技能导入完成: 新增 {new_count}, 更新 {update_count}")


def _resolve_code(user_input):
    """接受股票代码或名称，返回代码列表"""
    if not user_input:
        return []
    inputs = [u.strip() for u in user_input]
    # 先建一个名称->代码映射
    config = load_config_raw()
    name_map = {}
    for s in config.get("stocks", []):
        name = s.get("name", "")
        if name:
            name_map[name] = s["code"]
            name_map[name.lower()] = s["code"]
    # 解析
    resolved = []
    for inp in inputs:
        if inp in name_map:
            resolved.append(name_map[inp])
        elif inp.lower() in name_map:
            resolved.append(name_map[inp.lower()])
        else:
            resolved.append(inp)  # 直接当代码用
    return resolved


def cmd_score(args):
    """五维打分分析（支持名称别名）"""
    from strategy import analyze_batch, format_batch_table, record_score

    if args.codes:
        codes = _resolve_code(args.codes)
    else:
        config = load_config_raw()
        codes = [s["code"] for s in config.get("stocks", [])]

    if not codes:
        print("📭 没有持仓，请指定股票代码")
        return

    print(f"🔍 正在分析 {len(codes)} 只股票...")
    results = analyze_batch(codes)
    print()
    print(format_batch_table(results))
    print()

    # 评分详情
    for r in results:
        if r.get("error"):
            print(f"❌ {r['code']}: {r['error']}")
            continue
        print(f"  📈 {r['name']}({r['code']})  总分{r['total']}/100  {r['conclusion']}")
        for dim in ["大盘", "行业", "业绩", "估值", "走势"]:
            dim_detail = r.get("details", {}).get(dim, [])
            icon = "🟢" if r["scores"].get(dim, 0) >= 16 else "🟡" if r["scores"].get(dim, 0) >= 10 else "🔴"
            label = " | ".join(
                f"{'✅' if d['pass'] else '❌' if d['pass'] is False else '⬜'} {d['label']}: {d['value']}"
                for d in dim_detail
            )
            print(f"    {icon} {dim} {r['scores'].get(dim, 0)}/20  {label}")

    # 保存历史
    for r in results:
        if r.get("total", 0) > 0:
            record_score(r)
    print()
    print("📝 评分已记录到 score_history.json")


def cmd_total(args):
    """汇总统计"""
    config = load_config_raw()
    stocks = config.get("stocks", [])
    if not stocks:
        print("📭 持仓为空")
        return

    total_cost = sum(float(s["cost"]) * int(s["shares"]) for s in stocks)
    total_shares = sum(int(s["shares"]) for s in stocks)
    market_counts = {"sh": 0, "sz": 0}
    market_count = 0
    for s in stocks:
        m = s.get("market", "sh")
        market_counts[m] = market_counts.get(m, 0) + 1
        market_count += 1

    print(f"📊 持仓汇总:")
    print(f"  股票数:     {len(stocks)}")
    print(f"  沪市:       {market_counts.get('sh', 0)} 只")
    print(f"  深市:       {market_counts.get('sz', 0)} 只")
    print(f"  总持股数:   {total_shares:,} 股")
    print(f"  总投入成本: ¥{total_cost:,.2f}")
    print(f"  数据源:     {config.get('data_source', 'sina')}")
    print(f"  止损线:     {config.get('stop_loss_pct', 0):+.1f}%")
    print(f"  止盈线:     {config.get('take_profit_pct', 0):+.1f}%")


def main():
    parser = argparse.ArgumentParser(
        description="A股持仓管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    p_list = subparsers.add_parser("list", help="列出所有持仓")
    p_list.set_defaults(func=cmd_list)

    # add
    p_add = subparsers.add_parser("add", help="添加持仓 (自动获取名称)")
    p_add.add_argument("code", help="股票代码 (如 600519)")
    p_add.add_argument("cost", type=float, help="成本价")
    p_add.add_argument("shares", type=int, help="持股数")
    p_add.add_argument("--market", choices=["sh", "sz"], help="市场 (自动识别)")
    p_add.set_defaults(func=cmd_add)

    # remove
    p_rm = subparsers.add_parser("remove", aliases=["rm", "del", "delete"], help="删除持仓")
    p_rm.add_argument("code", help="股票代码")
    p_rm.set_defaults(func=cmd_remove)

    # update
    p_up = subparsers.add_parser("update", aliases=["up", "mod", "edit"], help="修改持仓")
    p_up.add_argument("code", help="股票代码")
    p_up.add_argument("--name", help="新名称")
    p_up.add_argument("--cost", type=float, help="新成本价")
    p_up.add_argument("--shares", type=int, help="新持股数")
    p_up.add_argument("--market", choices=["sh", "sz"], help="新市场")
    p_up.set_defaults(func=cmd_update)

    # clear
    p_cl = subparsers.add_parser("clear", help="清空持仓")
    p_cl.add_argument("--yes", "-y", action="store_true", help="跳过确认")
    p_cl.set_defaults(func=cmd_clear)

    # settings
    p_set = subparsers.add_parser("settings", aliases=["config", "cfg"], help="查看/修改设置")
    p_set.add_argument("--stop-loss", type=float, help="止损线 (如 -8)")
    p_set.add_argument("--take-profit", type=float, help="止盈线 (如 15)")
    p_set.add_argument("--refresh", type=int, help="刷新间隔(秒)")
    p_set.add_argument("--source", choices=["sina", "tencent", "eastmoney"], help="数据源")
    p_set.set_defaults(func=cmd_settings)

    # export
    p_exp = subparsers.add_parser("export", help="导出到技能数据格式")
    p_exp.set_defaults(func=cmd_export)

    # import-stocks
    p_imp = subparsers.add_parser("import-stocks", aliases=["import"], help="从技能数据导入")
    p_imp.set_defaults(func=cmd_import_stocks)

    # total
    p_tot = subparsers.add_parser("total", aliases=["summary", "info"], help="持仓汇总统计")
    p_tot.set_defaults(func=cmd_total)

    # score
    p_score = subparsers.add_parser("score", aliases=["analyze"], help="五维打分 (对持仓或指定股票)")
    p_score.add_argument("codes", nargs="*", help="股票代码（留空则分析全部持仓）")
    p_score.set_defaults(func=cmd_score)

    # history
    p_hist = subparsers.add_parser("history", aliases=["hist"], help="查看评分历史")
    p_hist.add_argument("code", nargs="?", help="股票代码（留空显示所有）")
    p_hist.set_defaults(func=cmd_history)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)


def cmd_history(args):
    """查看评分历史（支持名称别名）"""
    from strategy import show_score_history
    if args.code:
        codes = _resolve_code([args.code])
        code = codes[0] if codes else args.code
    else:
        code = None
    print(show_score_history(code))


if __name__ == "__main__":
    main()

"""
展示模块 - 终端表格显示
"""

from datetime import datetime


def GREEN(s):
    return f"\033[92m{s}\033[0m"


def RED(s):
    return f"\033[91m{s}\033[0m"


def YELLOW(s):
    return f"\033[93m{s}\033[0m"


def CYAN(s):
    return f"\033[96m{s}\033[0m"


def BOLD(s):
    return f"\033[1m{s}\033[0m"


def colorize_price(price, change_pct):
    """根据涨跌上色"""
    if change_pct > 0:
        return GREEN(f"¥{price:.2f}")
    elif change_pct < 0:
        return RED(f"¥{price:.2f}")
    return f"¥{price:.2f}"


def colorize_pct(pct):
    """根据涨跌幅上色"""
    if pct > 0:
        return GREEN(f"+{pct:.2f}%")
    elif pct < 0:
        return RED(f"{pct:.2f}%")
    return f"{pct:.2f}%"


def colorize_amount(amount):
    """根据盈亏金额上色"""
    if amount > 0:
        return GREEN(f"+¥{amount:,.2f}")
    elif amount < 0:
        return RED(f"-¥{abs(amount):,.2f}")
    return f"¥{amount:,.2f}"


def colorize_profit_pct(pct):
    """根据盈亏百分比上色"""
    if pct > 0:
        return GREEN(f"+{pct:.2f}%")
    elif pct < 0:
        return RED(f"{pct:.2f}%")
    return f"{pct:.2f}%"


def print_header():
    """打印表格头部"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{BOLD('📊 A股持仓监控')}   {now}")
    print("=" * 110)
    header = (
        f"{'代码':>8} {'名称':<10} {'持仓':>6} "
        f"{'成本价':>8} {'当前价':>10} {'涨跌幅':>8} "
        f"{'市值':>10} {'今日盈亏':>12} {'总盈亏额':>12} {'总盈亏率':>8}"
    )
    print(BOLD(header))
    print("-" * 110)


def print_row(holding):
    """打印单行持仓数据（含今日盈亏）"""
    profit_icon = "🟢" if holding.profit >= 0 else "🔴"
    day_icon = "🟢" if holding.day_profit >= 0 else "🔴"
    change_color = GREEN if holding.change_pct > 0 else RED if holding.change_pct < 0 else lambda x: x

    row = (
        f"{holding.code:>8} {holding.name:<10} "
        f"{holding.shares:>6,} "
        f"¥{holding.cost:<6.2f} "
        f"{colorize_price(holding.price, holding.change_pct):>10} "
        f"{change_color(f'{holding.change_pct:+.2f}%'):>8} "
        f"¥{holding.market_value:>8,.2f} "
        f"{day_icon} {colorize_amount(holding.day_profit):>10} "
        f"{profit_icon} {colorize_amount(holding.profit):>10} "
        f"{colorize_profit_pct(holding.profit_pct):>8}"
    )
    print(row)


def print_summary(portfolio):
    """打印持有收益汇总（含今日盈亏）"""
    print("-" * 110)
    total_profit = portfolio.total_profit
    total_pct = portfolio.total_profit_pct
    total_day = portfolio.total_day_profit
    total_day_pct = portfolio.total_day_pct

    profit_icon = "🟢" if total_profit >= 0 else "🔴"
    day_icon = "🟢" if total_day >= 0 else "🔴"
    total_str = f"{profit_icon} {colorize_amount(total_profit)}"
    pct_str = colorize_profit_pct(total_pct)
    day_str = f"{day_icon} {colorize_amount(total_day)}"

    summary = (
        f"{'':>8} {'合计':<10} "
        f"{sum(h.shares for h in portfolio.holdings):>6,} "
        f"{'—':>8} {'—':>10} {'—':>8} "
        f"¥{portfolio.total_market_value:>8,.2f} "
        f"{day_str:>12} {total_str:>12} {pct_str:>8}"
    )
    print(BOLD(summary))
    print(f"  投入成本: ¥{portfolio.total_cost:,.2f}")
    print(f"  📅 今日: {day_str}  {colorize_profit_pct(total_day_pct)}")
    print("=" * 110)


def print_alert(holding, stop_loss=-8.0, take_profit=15.0):
    """检测并打印止损止盈提醒"""
    triggered = []
    if stop_loss != 0 and holding.profit_pct <= stop_loss:
        triggered.append(
            f"  ⚠️  {holding.name}({holding.code}) 触发{''}止损！"
            f"亏损 {holding.profit_pct:.1f}% < {stop_loss:.0f}%"
        )
    if take_profit != 0 and holding.profit_pct >= take_profit:
        triggered.append(
            f"  🎯 {holding.name}({holding.code}) 触发止盈！"
            f"盈利 {holding.profit_pct:.1f}% > {take_profit:.0f}%"
        )
    return triggered


def print_footer():
    """打印页脚提示"""
    print("  [按 Ctrl+C 退出 | 数据仅供参考，不构成投资建议]")


def print_compact(portfolio):
    """紧凑模式显示（含今日盈亏）"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\033[H", end="")  # 回到行首
    print(f"📊 A股持仓 | {now}")
    print("=" * 90)

    for h in portfolio.holdings:
        d_icon = "🟢" if h.day_profit >= 0 else "🔴"
        line = (
            f"{h.name:<8} ¥{h.price:<8.2f} "
            f"{colorize_pct(h.change_pct):>8} "
            f"| 今日 {d_icon} {colorize_amount(h.day_profit):>10} "
            f"| 累计 {colorize_amount(h.profit):>10} "
            f"{colorize_profit_pct(h.profit_pct):>8}"
        )
        print(line)

    print("-" * 90)
    d_icon = "🟢" if portfolio.total_day_profit >= 0 else "🔴"
    p_icon = "🟢" if portfolio.total_profit >= 0 else "🔴"
    print(
        f"{'合计':<8} 市值 ¥{portfolio.total_market_value:<10,.2f} "
        f"| 今日 {d_icon} {colorize_amount(portfolio.total_day_profit):>10} "
        f"| 累计 {p_icon} {colorize_amount(portfolio.total_profit):>10} "
        f"{colorize_profit_pct(portfolio.total_profit_pct):>8}"
    )

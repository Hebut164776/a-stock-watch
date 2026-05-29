"""
展示模块 - 终端表格显示
对齐策略：先格式化纯文本到固定宽度，再包裹颜色转义码
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


def _cjk_pad(text, width):
    """将文本填充到指定终端宽度（CJK字符占2列）"""
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    actual = len(text) + cjk
    return text + ' ' * max(0, width - actual)


def _fmt_price(price):
    return f"¥{price:.2f}"


def _fmt_pct(pct):
    if pct > 0:
        return f"+{pct:.2f}%"
    elif pct < 0:
        return f"{pct:.2f}%"
    return f"{pct:.2f}%"


def _fmt_number(n):
    return f"¥{n:,.2f}"


def _fmt_amount(amount):
    if amount > 0:
        return f"+¥{amount:,.2f}"
    elif amount < 0:
        return f"-¥{abs(amount):,.2f}"
    return f"¥{amount:,.2f}"


def _wrap(text, positive):
    """正数=红色，负数=绿色"""
    if positive > 0:
        return RED(text)
    elif positive < 0:
        return GREEN(text)
    return text


def print_header():
    """打印表格头部"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{BOLD('📊 A股持仓监控')}   {now}")
    print("=" * 115)
    # 各列宽度：代码8 名称10 持仓6 成本8 当前价10 涨跌幅8 市值12 今日盈亏14 总盈亏额14 总盈亏8
    # 名称3+9=12(因为中文字宽)，但直接用固定填充
    header = (
        f"{'代码':>8} {_cjk_pad('名称', 8)} {'持仓':>6} "
        f"{'成本价':>8} {'当前价':>10} {'涨跌幅':>8} "
        f"{'市值':>12} {'今日盈亏':>14} {'总盈亏额':>14} {'总盈亏率':>8}"
    )
    print(BOLD(header))
    print("-" * 115)


def print_row(holding):
    """打印单行持仓数据（含今日盈亏）"""
    # 列宽常量
    W_CODE = 8
    W_NAME = 8
    W_SHARES = 6
    W_COST = 8
    W_PRICE = 10
    W_CHGPCT = 8
    W_MV = 12
    W_DAY = 14
    W_PROFIT = 14
    W_PCT = 8

    # 所有字段先格式化成纯文本，再右对齐到固定宽度，再上色
    code = f"{holding.code:>{W_CODE}}"

    name_pad = _cjk_pad(holding.name, W_NAME)

    shares = f"{holding.shares:>{W_SHARES},}"

    cost_raw = f"¥{holding.cost:.2f}"
    cost = f"{cost_raw:>{W_COST}}"

    price_raw = _fmt_price(holding.price)
    price_colored = _wrap(f"{price_raw:>{W_PRICE}}", holding.change_pct)

    chgpct_raw = _fmt_pct(holding.change_pct)
    chgpct_colored = _wrap(f"{chgpct_raw:>{W_CHGPCT}}", holding.change_pct)

    mv_raw = _fmt_number(holding.market_value)
    mv = f"{mv_raw:>{W_MV}}"

    day_raw = _fmt_amount(holding.day_profit)
    day_icon = "🔴" if holding.day_profit > 0 else "🟢" if holding.day_profit < 0 else "⚪"
    day_colored = _wrap(f"{day_raw:>{W_DAY - 2}}", holding.day_profit)

    profit_raw = _fmt_amount(holding.profit)
    profit_icon = "🔴" if holding.profit > 0 else "🟢" if holding.profit < 0 else "⚪"
    profit_colored = _wrap(f"{profit_raw:>{W_PROFIT - 2}}", holding.profit)

    pct_raw = _fmt_pct(holding.profit_pct)
    pct_colored = _wrap(f"{pct_raw:>{W_PCT}}", holding.profit_pct)

    row = (
        f"{code} {name_pad} {shares} {cost} "
        f"{price_colored} {chgpct_colored} {mv} "
        f"{day_icon} {day_colored} {profit_icon} {profit_colored} {pct_colored}"
    )
    print(row)


def print_summary(portfolio):
    """打印持有收益汇总（含今日盈亏）"""
    print("-" * 115)
    total_profit = portfolio.total_profit
    total_pct = portfolio.total_profit_pct
    total_day = portfolio.total_day_profit
    total_day_pct = portfolio.total_day_pct
    total_shares = sum(h.shares for h in portfolio.holdings)

    W_CODE = 8
    W_NAME = 8
    W_SHARES = 6
    W_COST = 8
    W_PRICE = 10
    W_CHGPCT = 8
    W_MV = 12
    W_DAY = 14
    W_PROFIT = 14
    W_PCT = 8

    code = f"{'':>{W_CODE}}"
    name_pad = _cjk_pad('合计', W_NAME)
    shares = f"{total_shares:>{W_SHARES},}"
    cost_dash = f"{'—':>{W_COST}}"
    price_dash = f"{'—':>{W_PRICE}}"
    chgpct_dash = f"{'—':>{W_CHGPCT}}"
    mv_raw = _fmt_number(portfolio.total_market_value)
    mv = f"{mv_raw:>{W_MV}}"

    day_raw = _fmt_amount(total_day)
    day_icon = "🔴" if total_day > 0 else "🟢" if total_day < 0 else "⚪"
    day_colored = _wrap(f"{day_raw:>{W_DAY - 2}}", total_day)

    profit_raw = _fmt_amount(total_profit)
    profit_icon = "🔴" if total_profit > 0 else "🟢" if total_profit < 0 else "⚪"
    profit_colored = _wrap(f"{profit_raw:>{W_PROFIT - 2}}", total_profit)

    pct_raw = _fmt_pct(total_pct)
    pct_colored = _wrap(f"{pct_raw:>{W_PCT}}", total_pct)

    summary = (
        f"{code} {name_pad} {shares} {cost_dash} {price_dash} {chgpct_dash} {mv} "
        f"{day_icon} {day_colored} {profit_icon} {profit_colored} {pct_colored}"
    )
    print(BOLD(summary))
    print(f"  投入成本: ¥{portfolio.total_cost:,.2f}")
    print(f"  📅 今日盈亏: {day_icon} {_fmt_amount(total_day)}  ({_fmt_pct(total_day_pct)})")
    print("=" * 115)


def print_sell_signals(signals):
    """打印策略卖出信号"""
    print("=" * 60)
    print(f"{BOLD('🚨 卖出信号')}")
    if not signals:
        print("  ✅ 无卖出信号")
    for s in signals:
        print(f"  {s}")
    print("=" * 60)


def print_alert(holding, stop_loss=-8.0, take_profit=15.0):
    """检测并打印止损止盈提醒"""
    triggered = []
    if stop_loss != 0 and holding.profit_pct <= stop_loss:
        triggered.append(
            f"  ⚠️  {holding.name}({holding.code}) 触发止损！"
            f"亏损 {holding.profit_pct:.1f}% ≤ {stop_loss:.0f}%"
        )
    if take_profit != 0 and holding.profit_pct >= take_profit:
        triggered.append(
            f"  🎯 {holding.name}({holding.code}) 触发止盈！"
            f"盈利 {holding.profit_pct:.1f}% ≥ {take_profit:.0f}%"
        )
    return triggered


def print_footer():
    """打印页脚提示"""
    print("  [按 Ctrl+C 退出 | 数据仅供参考，不构成投资建议]")


def print_compact(portfolio):
    """紧凑模式显示（含今日盈亏）"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\033[H", end="")
    print(f"📊 A股持仓 | {now}")
    print("=" * 95)

    for h in portfolio.holdings:
        day_icon = "🔴" if h.day_profit > 0 else "🟢" if h.day_profit < 0 else "⚪"
        line = (
            f"{_cjk_pad(h.name, 8)} "
            f"{_wrap(f'{_fmt_price(h.price):>8}', h.change_pct)} "
            f"{_wrap(f'{_fmt_pct(h.change_pct):>8}', h.change_pct)} "
            f"| 今日 {day_icon} {_wrap(f'{_fmt_amount(h.day_profit):>10}', h.day_profit)} "
            f"| 累计 {_wrap(f'{_fmt_amount(h.profit):>10}', h.profit)} "
            f"{_wrap(f'{_fmt_pct(h.profit_pct):>8}', h.profit_pct)}"
        )
        print(line)

    print("-" * 95)
    total_day = portfolio.total_day_profit
    total_profit = portfolio.total_profit
    d_icon = "🔴" if total_day > 0 else "🟢" if total_day < 0 else "⚪"
    p_icon = "🔴" if total_profit > 0 else "🟢" if total_profit < 0 else "⚪"
    print(
        f"{'合计':<8} "
        f"{'市值 ' + _fmt_number(portfolio.total_market_value):<18} "
        f"| 今日 {d_icon} {_wrap(f'{_fmt_amount(total_day):>10}', total_day)} "
        f"| 累计 {p_icon} {_wrap(f'{_fmt_amount(total_profit):>10}', total_profit)} "
        f"{_wrap(f'{_fmt_pct(portfolio.total_profit_pct):>8}', total_profit)}"
    )

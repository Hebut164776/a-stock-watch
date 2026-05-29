"""
持仓盈亏计算模块
"""

from dataclasses import dataclass, field
from typing import List, Optional
import yaml


@dataclass
class Holding:
    """单只持仓信息"""
    code: str
    name: str
    cost: float          # 成本价
    shares: int          # 持股数
    market: str = "sh"   # 市场: sh/sz

    # 动态数据（由计算后填充）
    price: float = 0.0       # 当前价
    market_value: float = 0.0    # 当前市值
    cost_total: float = 0.0      # 总成本
    profit: float = 0.0          # 总盈亏额
    profit_pct: float = 0.0      # 总盈亏百分比
    change: float = 0.0          # 涨跌额
    change_pct: float = 0.0      # 涨跌幅
    day_profit: float = 0.0      # 今日盈亏（基于昨收）
    day_pct: float = 0.0          # 今日涨幅

    def calc(self, price, change=0.0, change_pct=0.0):
        """基于实时价格计算盈亏（含今日盈亏）"""
        self.price = price
        self.change = change
        self.change_pct = change_pct
        self.cost_total = round(self.cost * self.shares, 2)
        self.market_value = round(price * self.shares, 2)
        self.profit = round(self.market_value - self.cost_total, 2)
        self.profit_pct = round(
            ((price - self.cost) / self.cost) * 100, 2
        ) if self.cost != 0 else 0.0
        # 今日盈亏 = 涨跌额 × 持股数
        self.day_profit = round(change * self.shares, 2)
        self.day_pct = change_pct


@dataclass
class Portfolio:
    """整个持仓组合"""
    holdings: List[Holding] = field(default_factory=list)
    total_cost: float = 0.0       # 总投入
    total_market_value: float = 0.0  # 总市值
    total_profit: float = 0.0     # 总盈亏
    total_profit_pct: float = 0.0  # 总盈亏百分比
    total_day_profit: float = 0.0  # 今日总盈亏
    total_day_pct: float = 0.0     # 今日平均涨幅

    def update(self):
        """更新组合汇总数据"""
        self.total_cost = round(sum(h.cost_total for h in self.holdings), 2)
        self.total_market_value = round(sum(h.market_value for h in self.holdings), 2)
        self.total_profit = round(self.total_market_value - self.total_cost, 2)
        self.total_profit_pct = round(
            (self.total_profit / self.total_cost) * 100, 2
        ) if self.total_cost != 0 else 0.0
        self.total_day_profit = round(sum(h.day_profit for h in self.holdings), 2)
        # 今日涨幅按市值加权
        if self.total_market_value > 0:
            weighted = sum(h.day_pct * h.market_value for h in self.holdings)
            self.total_day_pct = round(weighted / self.total_market_value, 2)
        else:
            self.total_day_pct = 0.0


def load_config(path="config.yaml"):
    """从YAML配置文件加载持仓"""
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    holdings = []
    for item in config.get("stocks", []):
        holding = Holding(
            code=item["code"],
            name=item.get("name", ""),
            cost=item["cost"],
            shares=item["shares"],
            market=item.get("market", "sh"),
        )
        holdings.append(holding)

    return holdings, config


def load_from_skills():
    """
    尝试从 a-stock-portfolio-monitor 技能的 save_stock() 格式读取持仓
    如果配置文件存在且有数据则使用，否则回退到 config.yaml
    """
    import os
    import json

    skill_data_path = os.path.join(
        os.path.dirname(__file__),
        "skills", "a-stock-portfolio-monitor", "data", "stocks.json"
    )
    if os.path.exists(skill_data_path):
        try:
            with open(skill_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            holdings = []
            for item in data.get("stocks", []):
                holdings.append(Holding(
                    code=item["code"],
                    name=item.get("name", ""),
                    cost=item["cost"],
                    shares=item["qty"],
                    market=item.get("market", "sh"),
                ))
            if holdings:
                print(f"  📂 从技能数据加载 {len(holdings)} 只持仓")
                return holdings, {}
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    raise FileNotFoundError("未找到持仓配置")

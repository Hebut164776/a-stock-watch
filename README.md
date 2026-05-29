# 📊 A股持仓监控系统

A股实时行情监控 + 五维策略打分 + 卖出信号监控 + CLI管理工具。

## ✨ 功能

### 📈 实时持仓盈亏
- 三数据源可选（新浪/腾讯/东方财富）
- 实时股价 + 涨跌幅 + 市值 + 盈亏额/盈亏率
- **今日盈亏** — 基于昨收计算当日盈亏
- 实时监控模式（定时刷新）

### 🧠 五维策略打分
基于《投资最简版_小白入门》策略框架，对每只股票进行五维评估：

| 维度 | 分值 | 评判标准 |
|------|------|---------|
| 大盘 | 20分 | 沪深300在MA200上方、MA50 > MA200 |
| 行业 | 20分 | 板块识别、近3月相对大盘表现 |
| 业绩 | 20分 | 营收同比≥15%、净利润同比≥20%、ROE≥12% |
| 估值 | 20分 | PE(TTM)≤30、PEG≤2 |
| 走势 | 20分 | 股价在MA50上方、多头排列、放量突破 |

### 🚨 卖出信号监控
自动检测三条卖出规则：
- 😵 **-8%止损** — 亏损超过-8%发出止损警告
- 💰 **+20%止盈** — 盈利超过+20%建议卖出一半
- 📉 **跌破50日线** — 跌破MA50建议清仓剩余仓位

### 📜 评分历史
每次评分自动存档，每只保留最近20条记录，可追溯评分变化趋势。

### 📊 批量对比
多只股票同时打分排名，一目了然。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests pandas pyyaml
```

### 2. 配置持仓

用 CLI 工具添加持仓（自动获取股票名称）：

```bash
python manage.py add 002594 89.861 200     # 比亚迪 成本89.861 200股
python manage.py add 601179 18.13 600      # 中国西电
python manage.py list                       # 列出所有持仓
```

### 3. 运行

```bash
# 查询持仓盈亏 + 卖出信号
python main.py

# 查询 + 五维打分排名
python main.py --score

# 实时监控（每30秒刷新）
python main.py --watch

# 查看评分历史
python main.py --history
python main.py --history 002594    # 只看某只
```

## 🛠️ CLI 管理工具

```bash
# 持仓管理
python manage.py list                          # 列出持仓
python manage.py add <代码> <成本> <股数>       # 添加
python manage.py remove <代码>                  # 删除
python manage.py update <代码> --cost X         # 修改成本
python manage.py update <代码> --shares X       # 修改股数

# 策略分析
python manage.py score                          # 持仓五维排名
python manage.py score 002594 000333            # 批量打分
python manage.py history                        # 评分历史

# 配置
python manage.py settings                       # 查看配置
python manage.py settings --stop-loss -8        # 修改止损线
python manage.py settings --take-profit 20      # 修改止盈线

# 数据
python manage.py export                         # 导出到技能数据格式
python manage.py total                          # 持仓汇总统计
```

## 📁 项目结构

```
a-stock-watch/
├── main.py              # 主程序（查询/评分/信号/历史）
├── manage.py            # CLI管理工具
├── fetcher.py           # 行情数据抓取（新浪/腾讯/东方财富）
├── portfolio.py         # 持仓与盈亏计算
├── strategy.py          # 五维打分引擎 + 卖出规则
├── views.py             # 终端格式化输出
├── config.yaml          # 持仓配置（不提交git）
├── score_history.json   # 评分历史（不提交git）
├── .gitignore
├── README.md
└── 投资最简版_小白入门.md  # 策略文档
```

## 🔌 数据源

| 数据源 | 速度 | 稳定性 | 特点 |
|--------|------|--------|------|
| 新浪(sina) | ⭐⭐⭐ | ⭐⭐⭐ | 默认数据源，含K线数据 |
| 腾讯(tencent) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 响应快 |
| 东方财富(eastmoney) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 信息最全（需直连） |

切换数据源：
```bash
python main.py --source tencent
```

## 🔗 集成

- **OpenClaw 微信插件** — 通过微信对话查询持仓盈亏
- **stock-wechat-monitor skill** — 自定义微信回复技能
- **stock-investment-strategy skill** — 策略分析技能

## ⚠️ 免责声明

数据仅供参考，不构成投资建议。股市有风险，入市需谨慎。

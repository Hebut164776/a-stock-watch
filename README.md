# 📊 A股实时股价监控 + 盈亏计算

## 功能

- ✅ A股实时股价查询（支持三数据源）
- ✅ 持仓盈亏实时计算
- ✅ 止损止盈提醒
- ✅ 实时刷新模式
- ✅ 兼容 `a-stock-portfolio-monitor` 技能数据

## 快速开始

### 1. 安装依赖

```bash
pip install akshare pandas requests pyyaml
```

### 2. 配置持仓

编辑 `config.yaml`，添加你的持仓股票：

```yaml
stocks:
  - code: "600519"    # 股票代码
    name: "贵州茅台"   # 股票名称
    cost: 180.00      # 成本价
    shares: 100       # 持股数
    market: "sh"      # sh=上海, sz=深圳
```

### 3. 运行

```bash
# 单次查询
python main.py

# 实时监控（每30秒刷新）
python main.py --watch

# 指定数据源（sina/tencent/eastmoney）
python main.py --source tencent

# 自定义刷新间隔（每10秒）
python main.py --watch --interval 10

# 从技能数据加载持仓
python main.py --skills

# 仅查看配置，不发起网络请求
python main.py --dry-run
```

## 数据源对比

| 数据源 | 速度 | 稳定性 | 延迟 |
|--------|------|--------|------|
| 新浪(sina) | ⭐⭐⭐ | ⭐⭐⭐ | 约3s |
| 腾讯(tencent) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 约1s |
| 东方财富(eastmoney) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 约1s |

## 已安装的 OpenClaw 技能

- `stock` - 股票实时查询（CLI命令）
- `a-stock-portfolio-monitor` - 持仓监控助手
- `akshare-finance` - AKShare财经数据封装

## 数据源

- 新浪财经: `hq.sinajs.cn`
- 腾讯证券: `qt.gtimg.cn`
- 东方财富: `push2.eastmoney.com`

⚠️ **免责声明**: 数据仅供参考，不构成投资建议。股市有风险，入市需谨慎。

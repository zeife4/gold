# Gold Agent - 多 Agent 协作黄金实时智能监控系统

四个专职 Agent 协同工作的桌面端黄金价格监控工具，融合实时数据采集、numpy 技术指标计算与 Claude 长链推理，为散户投资者提供数据驱动的交易决策辅助。

## 架构

```
GUI (Tkinter 主线程)
  ↕ root.after() 线程桥接
Orchestrator (后台线程, 每 3s 一轮)
  ├─ DataFetcher Agent      → 交易所 API 实时金价采集
  ├─ TechnicalAnalyst Agent → 15+ 项技术指标计算 (每 10s)
  └─ StrategyAgent (LLM)    → 五步推理链, BUY/SELL/HOLD (每 60s)
       └─ SharedContext      → 线程安全共享内存
```

## Agent 职责

| Agent | 功能 | 频率 |
|-------|------|------|
| **DataFetcher** | 从交易所 API 采集实时金价，统一 PricePoint 数据结构 | 3s |
| **TechnicalAnalyst** | numpy 计算 MA5/10/20、RSI(14)、MACD(12,26,9)、布林带(20,2)、支撑/阻力位 | 10s |
| **StrategyAgent** | 调用 Claude API extended thinking，执行五步长链推理 | 60s |
| **Orchestrator** | 调度节奏、管理共享上下文、线程安全 GUI 桥接 | 3s |

## 长链推理流程

1. **趋势分析** — 从近期 20 个价格点判定走势方向与强度
2. **技术指标校验** — MA 排列 / MACD 金叉死叉 / RSI 超买超卖 / 布林带突破交叉验证
3. **市场状态判断** — 归类为强牛市/弱牛市/震荡市/弱熊市/强熊市/高波动突破
4. **风险评估** — 识别反转信号、超买超卖极端值、假突破风险
5. **最终建议** — 输出 BUY/SELL/HOLD + HIGH/MEDIUM/LOW 信心等级 + 中文详解

## 安装

```bash
git clone git@github.com:zeife4/gold.git
cd gold
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## 使用

```bash
# 设置 Anthropic API Key（可选，不设置则策略引擎禁用但其他功能正常）
set ANTHROPIC_API_KEY=sk-ant-...

# 启动
pythonw gold_agent.pyw
```

## 界面

- 上部：实时金价 + 持仓浮盈
- 左侧面板：四 Agent 运行状态（○空闲 ◌运行 ●正常 ✕错误 ⊘禁用）
- 右侧面板：策略分析 — 操作建议、信心等级、可展开的五步推理追踪
- 底部：买入/卖出阈值、持仓设置、K 线图、一键强制分析
- K 线图：价格折线 + MA5/10/20 均线叠加 + 涨跌统计

## 项目结构

```
├── gold.pyw              # 原始版本（单文件轮询）
├── gold_agent.pyw        # 增强版主入口（多 Agent 集成）
├── config.py             # 集中配置
├── requirements.txt      # 依赖
├── agents/
│   ├── __init__.py
│   ├── data_fetcher.py      # DataFetcher Agent
│   ├── technical_analyst.py # TechnicalAnalyst Agent
│   ├── strategy_agent.py    # StrategyAgent (LLM)
│   └── orchestrator.py      # Orchestrator Agent
```

## 依赖

- Python 3.12+
- `requests` — HTTP API 调用
- `numpy` — 技术指标向量化计算
- `anthropic` — Claude API（可选，未设置则策略引擎禁用）
- `tkinter` — GUI（Python 内置）

## Token 消耗估算

单次策略推理：~800t（cached system prompt）+ 600t（market data）+ 1600t（thinking）+ 500t（output）≈ 3500 token/次。每分钟 1 次，持续监控约 5M token/天。利用 Anthropic prompt caching 降低 90% 重复输入成本。

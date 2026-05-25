import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import winsound
from datetime import datetime

from config import (
    APIS, WINDOW_TITLE, WINDOW_SIZE, WINDOW_OPACITY,
    FONT_PRICE, FONT_REASONING, FONT_STATUS, REFRESH_SEC,
    ANTHROPIC_API_KEY,
)
from agents.orchestrator import Orchestrator, SharedContext
from agents.strategy_agent import StrategyRecommendation
from agents.technical_analyst import TechnicalIndicators

# ------------------- 主窗口 -------------------
root = tk.Tk()
root.title(WINDOW_TITLE)
root.geometry(WINDOW_SIZE)
root.resizable(True, True)
root.attributes("-alpha", WINDOW_OPACITY)

# ------------------- 显示变量 -------------------
price_var = tk.StringVar(value="-- 等待数据 --")
time_var = tk.StringVar(value="--:--:--")
status_var = tk.StringVar(value="正在初始化 Agent 系统...")
profit_display_var = tk.StringVar(value="")

# 策略分析显示变量
action_var = tk.StringVar(value="--")
confidence_var = tk.StringVar(value="--")
trend_var = tk.StringVar(value="--")
regime_var = tk.StringVar(value="--")
rsi_display_var = tk.StringVar(value="--")
macd_display_var = tk.StringVar(value="--")
ma_display_var = tk.StringVar(value="--")

# 设置变量
buy_var = tk.StringVar(value="980")
sell_var = tk.StringVar(value="1010")
current_api_var = tk.StringVar(value="浙商积存金")
holdings_var = tk.StringVar(value="3.2786")
avg_price_var = tk.StringVar(value="995.55")

# 控制变量
last_alert_type = None
kline_data = []
kline_window = None
kline_canvas = None
start_time = None
show_indicators_on_chart = tk.BooleanVar(value=True)
reasoning_expanded = tk.BooleanVar(value=False)

# orchestrator 引用
orchestrator = None

# Agent 状态显示组件
agent_status_widgets = {}

# 策略面板组件引用
action_label = None
reasoning_toggle_btn = None
reasoning_frame = None
reasoning_text = None
indicator_grid_frame = None


# ------------------- UI 构建函数 -------------------

def build_price_header(parent):
    header = ttk.Frame(parent, padding=10)
    header.pack(fill=tk.X)

    global price_label
    price_label = tk.Label(header, textvariable=price_var, font=FONT_PRICE, fg="black")
    price_label.pack()

    profit_label = tk.Label(header, textvariable=profit_display_var,
                            font=("微软雅黑", 12), fg="black")
    profit_label.pack()

    tk.Label(header, textvariable=time_var, font=("微软雅黑", 10)).pack(pady=2)
    tk.Label(header, textvariable=status_var, font=("微软雅黑", 10), fg="green").pack(pady=2)


def build_dual_panel(parent):
    panel_frame = ttk.Frame(parent, padding=5)
    panel_frame.pack(fill=tk.BOTH, expand=True)

    # 左侧：Agent 状态面板
    status_frame = ttk.LabelFrame(panel_frame, text="Agent 状态", padding=5)
    status_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))
    build_agent_status_panel(status_frame)

    # 右侧：策略分析面板
    insight_frame = ttk.LabelFrame(panel_frame, text="策略分析", padding=5)
    insight_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3, 0))
    build_strategy_panel(insight_frame)


def build_agent_status_panel(parent):
    status_icons = {"idle": "○", "running": "◌", "success": "●", "error": "✕", "disabled": "⊘"}
    status_colors = {"idle": "gray", "running": "blue", "success": "green",
                     "error": "red", "disabled": "gray"}
    agent_names = ["DataFetcher", "TechnicalAnalyst", "StrategyAgent", "Orchestrator"]
    display_names = {"DataFetcher": "数据采集", "TechnicalAnalyst": "技术分析",
                     "StrategyAgent": "策略引擎", "Orchestrator": "调度中心"}

    for name in agent_names:
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, pady=2)

        icon_label = tk.Label(row_frame, text=status_icons["idle"],
                              font=("Arial", 12), fg=status_colors["idle"], width=2)
        icon_label.pack(side=tk.LEFT)

        name_label = tk.Label(row_frame, text=f"{display_names.get(name, name)}:",
                              font=FONT_STATUS, width=10, anchor=tk.W)
        name_label.pack(side=tk.LEFT)

        detail_label = tk.Label(row_frame, text="等待启动", font=FONT_STATUS, anchor=tk.W)
        detail_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        agent_status_widgets[name] = {
            "icon": icon_label, "detail": detail_label,
            "colors": status_colors, "icons": status_icons, "display": display_names.get(name, name)
        }

    global stats_label
    stats_label = tk.Label(parent, text="", font=("微软雅黑", 8), fg="gray")
    stats_label.pack(fill=tk.X, pady=5)


def build_strategy_panel(parent):
    global action_label, reasoning_toggle_btn, reasoning_frame, reasoning_text, indicator_grid_frame

    # 操作建议
    action_frame = ttk.Frame(parent)
    action_frame.pack(fill=tk.X, pady=2)
    tk.Label(action_frame, text="操作建议:", font=("微软雅黑", 12, "bold")).pack(side=tk.LEFT)
    action_label = tk.Label(action_frame, textvariable=action_var,
                             font=("微软雅黑", 14, "bold"), fg="blue")
    action_label.pack(side=tk.LEFT, padx=10)

    # 信心等级
    conf_frame = ttk.Frame(parent)
    conf_frame.pack(fill=tk.X, pady=2)
    tk.Label(conf_frame, text="信心等级:", font=FONT_STATUS).pack(side=tk.LEFT)
    tk.Label(conf_frame, textvariable=confidence_var,
             font=("微软雅黑", 11, "bold")).pack(side=tk.LEFT, padx=5)

    # 快速指标摘要
    indicator_grid_frame = ttk.Frame(parent)
    indicator_grid_frame.pack(fill=tk.X, pady=5)

    indicators_info = [
        ("趋势方向:", trend_var),
        ("市场状态:", regime_var),
        ("RSI:", rsi_display_var),
        ("MACD:", macd_display_var),
        ("均线:", ma_display_var),
    ]
    for i, (label_text, var) in enumerate(indicators_info):
        row = i // 2
        col = i % 2
        sub = ttk.Frame(indicator_grid_frame)
        sub.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        tk.Label(sub, text=label_text, font=("微软雅黑", 9)).pack(side=tk.LEFT)
        tk.Label(sub, textvariable=var, font=("微软雅黑", 9, "bold")).pack(side=tk.LEFT)

    # 推理追踪（可折叠）
    reasoning_toggle_btn = ttk.Button(
        parent, text="▸ 展开推理过程",
        command=toggle_reasoning_trace
    )
    reasoning_toggle_btn.pack(fill=tk.X, pady=5)

    reasoning_frame = ttk.Frame(parent)
    reasoning_text = tk.Text(
        reasoning_frame, height=10, wrap=tk.WORD,
        font=FONT_REASONING, state=tk.DISABLED
    )
    scrollbar = ttk.Scrollbar(reasoning_frame, command=reasoning_text.yview)
    reasoning_text.configure(yscrollcommand=scrollbar.set)
    reasoning_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # 初始状态提示
    if not ANTHROPIC_API_KEY:
        action_var.set("不可用")
        confidence_var.set("未设置 API Key")
        trend_var.set("请在环境变量中设置")
        regime_var.set("ANTHROPIC_API_KEY")


def toggle_reasoning_trace():
    if reasoning_expanded.get():
        reasoning_frame.pack_forget()
        reasoning_toggle_btn.config(text="▸ 展开推理过程")
        reasoning_expanded.set(False)
    else:
        reasoning_frame.pack(fill=tk.BOTH, expand=True)
        reasoning_toggle_btn.config(text="▾ 收起推理过程")
        reasoning_expanded.set(True)


def build_controls(parent):
    # 阈值输入
    frame = tk.Frame(parent)
    frame.pack(pady=5)

    tk.Label(frame, text="买入提醒 ≤：").grid(row=0, column=0, padx=5)
    tk.Entry(frame, textvariable=buy_var, width=8).grid(row=0, column=1, padx=5)
    tk.Label(frame, text="卖出提醒 ≥：").grid(row=0, column=2, padx=5)
    tk.Entry(frame, textvariable=sell_var, width=8).grid(row=0, column=3, padx=5)

    # 持仓设置
    holdings_frame = tk.Frame(parent)
    holdings_frame.pack(pady=5)

    tk.Label(holdings_frame, text="持有数量(克)：").grid(row=0, column=0, padx=5)
    h_entry = tk.Entry(holdings_frame, textvariable=holdings_var, width=8)
    h_entry.grid(row=0, column=1, padx=5)

    tk.Label(holdings_frame, text="均价(元/克)：").grid(row=0, column=2, padx=5)
    a_entry = tk.Entry(holdings_frame, textvariable=avg_price_var, width=8)
    a_entry.grid(row=0, column=3, padx=5)

    # 绑定持仓变化
    def on_portfolio_change(*args):
        if orchestrator:
            try:
                h = float(holdings_var.get())
                a = float(avg_price_var.get())
                orchestrator.update_portfolio(h, a)
            except ValueError:
                pass

    holdings_var.trace_add("write", on_portfolio_change)
    avg_price_var.trace_add("write", on_portfolio_change)

    # 按钮框架
    btn_frame = tk.Frame(parent)
    btn_frame.pack(pady=5)

    def topmost():
        is_topmost = not root.attributes("-topmost")
        root.attributes("-topmost", is_topmost)
        btn_top.config(text="已置顶" if is_topmost else "窗口置顶")
        if kline_window is not None and kline_window.winfo_exists():
            kline_window.attributes("-topmost", is_topmost)

    btn_top = ttk.Button(btn_frame, text="窗口置顶", command=topmost)
    btn_top.pack(side=tk.LEFT, padx=3)

    def toggle_kline():
        global kline_window
        if kline_window is None or not kline_window.winfo_exists():
            create_kline_window()
        else:
            kline_window.destroy()
            kline_window = None

    btn_kline = ttk.Button(btn_frame, text="显示K线图", command=toggle_kline)
    btn_kline.pack(side=tk.LEFT, padx=3)

    # 技术指标叠加开关
    btn_indicators = ttk.Checkbutton(btn_frame, text="技术指标叠加", variable=show_indicators_on_chart)
    btn_indicators.pack(side=tk.LEFT, padx=3)

    # 立即分析按钮
    def force_analysis():
        if orchestrator:
            orchestrator.force_strategy_analysis()
            status_var.set("🔍 已触发立即策略分析...")

    btn_force = ttk.Button(btn_frame, text="立即分析", command=force_analysis)
    btn_force.pack(side=tk.LEFT, padx=3)

    # API选择
    api_frame = tk.Frame(parent)
    api_frame.pack(pady=5)
    tk.Label(api_frame, text="数据源：").pack(side=tk.LEFT, padx=5)
    api_combo = ttk.Combobox(api_frame, textvariable=current_api_var,
                             values=list(APIS.keys()), width=15, state="readonly")
    api_combo.pack(side=tk.LEFT, padx=5)


# ------------------- K线图 -------------------

def create_kline_window():
    global kline_window, kline_canvas
    kline_window = tk.Toplevel(root)
    kline_window.title("实时价格走势 - 技术分析图表")
    kline_window.geometry("750x450")
    kline_window.attributes("-alpha", 0.95)
    kline_canvas = tk.Canvas(kline_window, bg="white")
    kline_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    draw_kline()

    def on_kline_close():
        global kline_window, kline_canvas
        kline_window.destroy()
        kline_window = None
        kline_canvas = None

    kline_window.protocol("WM_DELETE_WINDOW", on_kline_close)


def draw_kline(indicators=None):
    global kline_canvas
    if kline_canvas is None or len(kline_data) == 0:
        return

    canvas_width = kline_canvas.winfo_width()
    canvas_height = kline_canvas.winfo_height()
    if canvas_width <= 1: canvas_width = 730
    if canvas_height <= 1: canvas_height = 430

    kline_canvas.delete("all")
    prices = [item[1] for item in kline_data]
    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price or 1

    margin_left, margin_right = 70, 30
    margin_top, margin_bottom = 30, 45
    chart_width = canvas_width - margin_left - margin_right
    chart_height = canvas_height - margin_top - margin_bottom

    # 背景
    kline_canvas.create_rectangle(margin_left, margin_top,
                                  canvas_width - margin_right,
                                  canvas_height - margin_bottom,
                                  fill="#fafafa", outline="#ddd")

    # 网格
    grid_lines = 5
    for i in range(grid_lines + 1):
        y = margin_top + (chart_height / grid_lines) * i
        kline_canvas.create_line(margin_left, y, canvas_width - margin_right, y,
                                fill="#e0e0e0", dash=(2, 2))
        price_label_val = max_price - (price_range / grid_lines) * i
        kline_canvas.create_text(margin_left - 5, y,
                               text=f"{price_label_val:.2f}",
                               fill="#666", font=("Arial", 8), anchor=tk.E)

    # 价格折线
    points = []
    for i, (timestamp, price) in enumerate(kline_data):
        x = margin_left + (i / max(len(kline_data) - 1, 1)) * chart_width
        y = margin_top + ((max_price - price) / price_range) * chart_height
        points.append((x, y, price, timestamp))

    # 如果启用了技术指标叠加且有指标数据，绘制MA和BB
    if show_indicators_on_chart.get() and indicators and len(kline_data) >= 20:
        draw_indicator_overlays(indicators, points, margin_left, chart_width,
                                margin_top, chart_height, max_price, price_range)

    # 绘制价格连线
    for i in range(len(points) - 1):
        x1, y1, p1, _ = points[i]
        x2, y2, p2, _ = points[i + 1]
        color = "red" if p2 >= p1 else "green"
        kline_canvas.create_line(x1, y1, x2, y2, fill=color, width=2)

    # 标题
    kline_canvas.create_text(canvas_width // 2, 15,
                           text="黄金实时价格走势",
                           fill="#333", font=("微软雅黑", 11, "bold"))

    # 统计信息
    current_price = kline_data[-1][1]
    start_price_val = kline_data[0][1]
    change = current_price - start_price_val
    change_percent = (change / start_price_val) * 100 if start_price_val else 0
    change_color = "red" if change >= 0 else "green"
    symbol = "+" if change >= 0 else ""
    info_text = f"最新: {current_price:.2f}  |  涨跌: {symbol}{change:.2f} ({symbol}{change_percent:.2f}%)"

    if indicators and indicators.rsi:
        info_text += f"  |  RSI: {indicators.rsi:.1f}"

    kline_canvas.create_text(canvas_width // 2, canvas_height - 15,
                           text=info_text, fill=change_color, font=("微软雅黑", 9, "bold"))

    # 时间标签
    if len(points) > 0:
        total_pts = len(points)
        if total_pts >= 5:
            label_indices = [0]
            for i in range(3):
                idx = 1 + int((total_pts - 2) * (i + 1) / 4)
                label_indices.append(idx)
            label_indices.append(total_pts - 1)
        else:
            label_indices = list(range(total_pts))

        for idx in label_indices:
            x, y, price, timestamp = points[idx]
            if idx == 0:
                anchor = tk.W
                display_time = start_time if start_time else timestamp
            elif idx == len(points) - 1:
                anchor = tk.E
                display_time = timestamp
            else:
                anchor = tk.CENTER
                display_time = timestamp
            kline_canvas.create_text(x, canvas_height - margin_bottom + 15,
                                   text=display_time, fill="#666",
                                   font=("Arial", 8), anchor=anchor)

    # 图例
    if show_indicators_on_chart.get() and indicators:
        legend_x = canvas_width - margin_right - 10
        legend_y = margin_top + 5
        legend_items = [
            ("价格", "red"),
            ("MA5", "#2196F3"),
            ("MA10", "#FF9800"),
            ("MA20", "#9C27B0"),
        ]
        for i, (label, color) in enumerate(legend_items):
            ly = legend_y + i * 16
            kline_canvas.create_line(legend_x - 25, ly + 8, legend_x - 5, ly + 8,
                                    fill=color, width=2)
            kline_canvas.create_text(legend_x, ly + 8, text=label,
                                   fill=color, font=("Arial", 7), anchor=tk.W)


def draw_indicator_overlays(indicators, points, margin_left, chart_width,
                            margin_top, chart_height, max_price, price_range):
    """在K线图上叠加MA均线"""
    # 使用最近的20个数据点为MA提供上下文
    if len(kline_data) < 5:
        return

    # 从kline数据计算移动平均线
    n = len(kline_data)
    ma_periods = [("MA5", 5, "#2196F3"), ("MA10", 10, "#FF9800"), ("MA20", 20, "#9C27B0")]

    for label, period, color in ma_periods:
        if n < period:
            continue
        ma_points = []
        for i in range(period - 1, n):
            avg = sum(kline_data[j][1] for j in range(i - period + 1, i + 1)) / period
            x = margin_left + (i / max(n - 1, 1)) * chart_width
            y = margin_top + ((max_price - avg) / price_range) * chart_height
            ma_points.append((x, y))

        for i in range(len(ma_points) - 1):
            x1, y1 = ma_points[i]
            x2, y2 = ma_points[i + 1]
            kline_canvas.create_line(x1, y1, x2, y2, fill=color, width=1, dash=(4, 2))


# ------------------- 提醒逻辑 -------------------

def check_alert(price):
    global last_alert_type
    try:
        buy = float(buy_var.get())
        sell = float(sell_var.get())
    except ValueError:
        return

    if price <= buy:
        if last_alert_type != "buy":
            status_var.set("🔔 已达到买入价格！")
            winsound.Beep(800, 800)
            messagebox.showinfo("买入提醒", f"当前金价：{price:.2f}\n已低于买入价：{buy}")
            last_alert_type = "buy"
    elif price >= sell:
        if last_alert_type != "sell":
            status_var.set("🔔 已达到卖出价格！")
            winsound.Beep(1200, 800)
            messagebox.showinfo("卖出提醒", f"当前金价：{price:.2f}\n已高于卖出价：{sell}")
            last_alert_type = "sell"
    else:
        last_alert_type = None


# ------------------- 收益计算 -------------------

def update_profit_display(price):
    try:
        holdings = float(holdings_var.get())
        avg_price = float(avg_price_var.get())
        if holdings > 0 and avg_price > 0:
            profit = (price - avg_price) * holdings
            profit_rate = ((price - avg_price) / avg_price) * 100
            profit_display_var.set(f"浮盈: {profit:+.2f} 元  |  {profit_rate:+.2f}%")
            if price > avg_price:
                color = "red"
            elif price < avg_price:
                color = "green"
            else:
                color = "black"
            price_label.config(fg=color)
        else:
            profit_display_var.set("")
            price_label.config(fg="black")
    except Exception:
        profit_display_var.set("")


# ------------------- Orchestrator → GUI 桥接 -------------------

def on_context_update(context: SharedContext):
    """由 Orchestrator 后台线程调用，调度到主线程"""
    root.after(0, update_ui_from_context, context)


def update_ui_from_context(context: SharedContext):
    """主线程安全地更新所有UI"""
    global start_time

    # 价格更新
    if context.latest_price:
        pp = context.latest_price
        price_var.set(f"{pp.price:.2f} 元/克")
        time_var.set(datetime.fromtimestamp(pp.timestamp).strftime("%H:%M:%S"))
        status_var.set("正常监控中")

        kline_data.append((time.strftime("%H:%M:%S"), pp.price))
        if len(kline_data) == 1:
            start_time = time.strftime("%H:%M:%S")

        update_profit_display(pp.price)
        check_alert(pp.price)

        # 更新K线图
        if kline_window is not None:
            try:
                draw_kline(context.technical_indicators)
            except Exception:
                pass

    # Agent 状态面板
    status_icons = {"idle": "○", "running": "◌", "success": "●", "error": "✕", "disabled": "⊘"}
    status_colors = {"idle": "gray", "running": "blue", "success": "green",
                     "error": "red", "disabled": "gray"}
    status_texts = {
        "idle": "空闲", "running": "运行中", "success": "正常",
        "error": "错误", "disabled": "已禁用"
    }

    for name, widgets in agent_status_widgets.items():
        agent = context.agent_statuses.get(name)
        if agent:
            widgets["icon"].config(
                text=status_icons.get(agent.status, "?"),
                fg=status_colors.get(agent.status, "gray")
            )
            detail = status_texts.get(agent.status, agent.status)
            if agent.status == "success" and agent.last_duration_ms:
                detail = f"{detail} ({agent.last_duration_ms:.0f}ms) · 第{agent.run_count}次"
            elif agent.status == "error" and agent.error_message:
                detail = f"错误: {agent.error_message[:25]}"
            elif agent.status == "disabled":
                detail = "未设置 API Key"
            widgets["detail"].config(text=detail)

    # 策略分析面板
    if context.strategy_recommendation:
        rec = context.strategy_recommendation
        update_strategy_panel(rec)
    elif not ANTHROPIC_API_KEY:
        pass  # 保持初始提示

    if context.technical_indicators:
        update_indicator_summary(context.technical_indicators)

    # 统计信息
    total_fetches = context.agent_statuses.get("DataFetcher", None)
    if total_fetches:
        stats_label.config(
            text=f"数据点数: {len(context.price_history)}  |  "
                 f"API调用: {total_fetches.run_count}次  |  "
                 f"策略建议: {len(context.recommendation_history)}次"
        )


def update_strategy_panel(rec: StrategyRecommendation):
    action_var.set(rec.action)
    action_colors = {"BUY": "red", "SELL": "green", "HOLD": "blue"}
    action_label.config(fg=action_colors.get(rec.action, "black"))

    confidence_var.set(rec.confidence)
    trend_var.set(f"{rec.trend_analysis.get('direction', '--')} ({rec.trend_analysis.get('strength', '--')})")
    regime_var.set(rec.market_regime.get('regime', '--'))

    # 更新推理追踪文本
    reasoning_text.config(state=tk.NORMAL)
    reasoning_text.delete(1.0, tk.END)

    trace = f"生成时间: {datetime.fromtimestamp(rec.timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n"
    trace += f"模型: {rec.model_used}\n\n"
    trace += "═══ 五步推理追踪 ═══\n\n"
    trace += f"【步骤1 - 趋势分析】\n  方向: {rec.trend_analysis.get('direction', 'N/A')}\n"
    trace += f"  强度: {rec.trend_analysis.get('strength', 'N/A')}\n"
    trace += f"  分析: {rec.trend_analysis.get('detail', 'N/A')}\n\n"
    trace += f"【步骤2 - 技术指标校验】\n"
    trace += f"  均线信号: {rec.indicator_alignment.get('ma_signal', 'N/A')}\n"
    trace += f"  RSI信号: {rec.indicator_alignment.get('rsi_signal', 'N/A')}\n"
    trace += f"  MACD信号: {rec.indicator_alignment.get('macd_signal', 'N/A')}\n"
    trace += f"  布林带信号: {rec.indicator_alignment.get('bb_signal', 'N/A')}\n"
    trace += f"  综合: {rec.indicator_alignment.get('overall', 'N/A')}\n\n"
    trace += f"【步骤3 - 市场状态判断】\n  状态: {rec.market_regime.get('regime', 'N/A')}\n"
    trace += f"  描述: {rec.market_regime.get('description', 'N/A')}\n\n"
    trace += f"【步骤4 - 风险评估】\n  总体风险: {rec.risk_assessment.get('overall_risk', 'N/A')}\n  风险点:\n"
    for risk in rec.risk_assessment.get('risks', []):
        trace += f"    - {risk}\n"
    trace += f"\n【步骤5 - 最终建议】\n  操作: {rec.action}\n  信心: {rec.confidence}\n"
    trace += f"  理由: {rec.reasoning_cn}\n  要点:\n"
    for pt in rec.key_points:
        trace += f"    - {pt}\n"

    reasoning_text.insert(tk.END, trace)
    reasoning_text.config(state=tk.DISABLED)


def update_indicator_summary(ind: TechnicalIndicators):
    if ind.rsi:
        rsi_display_var.set(f"{ind.rsi:.1f} ({ind.rsi_zone})")
    if ind.macd_crossover:
        macd_display_var.set(ind.macd_crossover)
    if ind.trend_signal:
        ma_display_var.set(ind.trend_signal)

    # 趋势和市场状态由策略引擎更新，这里不覆盖


# ------------------- 生命周期 -------------------

def on_closing():
    if orchestrator:
        orchestrator.stop()
    root.destroy()


# ------------------- 构建界面并启动 -------------------

build_price_header(root)
build_dual_panel(root)
build_controls(root)

# 初始化 Orchestrator
try:
    h = float(holdings_var.get())
    a = float(avg_price_var.get())
except ValueError:
    h, a = 0, 0

orchestrator = Orchestrator(gui_callback=on_context_update)
orchestrator.update_portfolio(h, a)
orchestrator.start()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

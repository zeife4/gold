import requests
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import winsound

# ------------------- 配置 -------------------
APIS = {
    "浙商积存金": {
        "url": "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816",
        "unit": "元/克"
    }
}
REFRESH_SEC = 3  # 刷新间隔（秒）

# ------------------- 主窗口 -------------------
root = tk.Tk()
root.title("黄金实时监控工具")
root.geometry("500x500")
root.resizable(True, True)
root.attributes("-alpha", 0.9)  # 窗口透明度 (0.0-1.0)

# ------------------- 全局变量 -------------------
# 显示变量
price_var = tk.StringVar(value="-- 等待数据 --")  # 当前价格显示
time_var = tk.StringVar(value="--:--:--")  # 最后更新时间显示
status_var = tk.StringVar(value="正常监控中")  # 运行状态显示
profit_display_var = tk.StringVar(value="")  # 收益和收益率显示

# 设置变量
buy_var = tk.StringVar(value="980")  # 买入提醒价格阈值
sell_var = tk.StringVar(value="1010")  # 卖出提醒价格阈值
current_api_var = tk.StringVar(value="浙商积存金")  # 当前选择的API源
holdings_var = tk.StringVar(value="3.2786")  # 持有黄金数量（克）
avg_price_var = tk.StringVar(value="995.55")  # 持仓平均价格（元/克）

# 控制变量
monitor_running = True  # 监控线程运行标志
last_alert_type = None  # 上次提醒类型（"buy"/"sell"/None），防止重复提醒

# 界面组件引用
price_label = None  # 价格标签组件
profit_frame = None  # 收益信息框架组件

# K线图相关
kline_data = []  # K线数据列表，存储 (时间字符串, 价格浮点数) 元组
kline_window = None  # K线图独立窗口对象
kline_canvas = None  # K线图画布组件
start_time = None  # 程序启动时的第一条数据时间
first_data_point = None  # 程序启动时的第一条完整数据(时间, 价格)，用于固定折线图起点

# ------------------- 界面布局 -------------------

# 当前价格
price_label = tk.Label(root, textvariable=price_var, font=("Arial", 28, "bold"), fg="black")
price_label.pack()

# 收益信息
profit_frame = tk.Frame(root)
profit_frame.pack(pady=5)
tk.Label(profit_frame, textvariable=profit_display_var, font=("微软雅黑", 12), fg="black").pack()

# 刷新时间
tk.Label(root, textvariable=time_var, font=("微软雅黑", 10)).pack(pady=2)

# 状态
tk.Label(root, textvariable=status_var, font=("微软雅黑", 10), fg="green").pack(pady=2)

# 输入框框架
frame = tk.Frame(root)
frame.pack(pady=10)

tk.Label(frame, text="买入提醒 ≤：").grid(row=0, column=0, padx=5)
tk.Entry(frame, textvariable=buy_var, width=8).grid(row=0, column=1, padx=5)

tk.Label(frame, text="卖出提醒 ≥：").grid(row=0, column=2, padx=5)
tk.Entry(frame, textvariable=sell_var, width=8).grid(row=0, column=3, padx=5)

# 持仓设置框架
holdings_frame = tk.Frame(root)
holdings_frame.pack(pady=10)

tk.Label(holdings_frame, text="持有数量(克)：").grid(row=0, column=0, padx=5)
tk.Entry(holdings_frame, textvariable=holdings_var, width=8).grid(row=0, column=1, padx=5)

tk.Label(holdings_frame, text="均价(元/克)：").grid(row=0, column=2, padx=5)
tk.Entry(holdings_frame, textvariable=avg_price_var, width=8).grid(row=0, column=3, padx=5)

# 按钮框架
btn_frame = tk.Frame(root)
btn_frame.pack(pady=5)

# 置顶按钮
def topmost():
    is_topmost = not root.attributes("-topmost")
    root.attributes("-topmost", is_topmost)
    btn_top.config(text="已置顶" if is_topmost else "窗口置顶")
    
    # 如果K线图窗口存在，同步置顶状态
    if kline_window is not None and kline_window.winfo_exists():
        kline_window.attributes("-topmost", is_topmost)

btn_top = ttk.Button(btn_frame, text="窗口置顶", command=topmost)
btn_top.pack(side=tk.LEFT, padx=5)

# K线图按钮
def toggle_kline():
    global kline_window
    if kline_window is None or not kline_window.winfo_exists():
        create_kline_window()
    else:
        kline_window.destroy()
        kline_window = None

btn_kline = ttk.Button(btn_frame, text="显示K线图", command=toggle_kline)
btn_kline.pack(side=tk.LEFT, padx=5)

# API选择框架
api_frame = tk.Frame(root)
api_frame.pack(pady=5)
tk.Label(api_frame, text="选择API：").pack(side=tk.LEFT, padx=5)
api_combo = ttk.Combobox(api_frame, textvariable=current_api_var, values=list(APIS.keys()), width=15, state="readonly")
api_combo.pack(side=tk.LEFT, padx=5)

# ------------------- K线图窗口 -------------------
def create_kline_window():
    global kline_window, kline_canvas
    
    kline_window = tk.Toplevel(root)
    kline_window.title("实时价格走势 - K线图")
    kline_window.geometry("700x400")
    kline_window.attributes("-alpha", 0.95)
    
    # 创建画布
    kline_canvas = tk.Canvas(kline_window, bg="white")
    kline_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 初始绘制
    draw_kline()
    
    # 绑定窗口关闭事件
    def on_kline_close():
        global kline_window, kline_canvas
        kline_window.destroy()
        kline_window = None
        kline_canvas = None
    
    kline_window.protocol("WM_DELETE_WINDOW", on_kline_close)

# ------------------- 绘制K线图 -------------------
def draw_kline():
    global kline_canvas
    
    if kline_canvas is None or len(kline_data) == 0:
        return
    
    canvas_width = kline_canvas.winfo_width()
    canvas_height = kline_canvas.winfo_height()
    
    if canvas_width <= 1:
        canvas_width = 680
    if canvas_height <= 1:
        canvas_height = 380
    
    # 清空画布
    kline_canvas.delete("all")
    
    # 获取价格范围
    prices = [item[1] for item in kline_data]
    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price
    
    if price_range == 0:
        price_range = 1
    
    # 边距
    margin_left = 60
    margin_right = 30
    margin_top = 30
    margin_bottom = 40
    
    # 绘制区域
    chart_width = canvas_width - margin_left - margin_right
    chart_height = canvas_height - margin_top - margin_bottom
    
    # 绘制背景
    kline_canvas.create_rectangle(margin_left, margin_top, 
                                  canvas_width - margin_right, 
                                  canvas_height - margin_bottom,
                                  fill="#fafafa", outline="#ddd")
    
    # 绘制网格线和价格标签
    grid_lines = 5
    for i in range(grid_lines + 1):
        y = margin_top + (chart_height / grid_lines) * i
        kline_canvas.create_line(margin_left, y, canvas_width - margin_right, y, 
                                fill="#e0e0e0", dash=(2, 2))
        
        # 价格标签
        price_label_value = max_price - (price_range / grid_lines) * i
        kline_canvas.create_text(margin_left - 5, y, 
                               text=f"{price_label_value:.2f}", 
                               fill="#666", font=("Arial", 8), anchor=tk.E)
    
    # 计算数据点坐标（支持动态间距调整）
    points = []
    
    # 均匀分布所有数据点
    for i, (timestamp, price) in enumerate(kline_data):
        x = margin_left + (i / max(len(kline_data) - 1, 1)) * chart_width
        y = margin_top + ((max_price - price) / price_range) * chart_height
        
        # 初始不标记显示，后续统一计算
        points.append((x, y, price, timestamp, False))
    
    # 计算需要显示的时间标签索引（固定5个：首尾+中间3个均匀分布的点）
    if len(points) > 0:
        label_indices = []
        total_points = len(points)
        
        if total_points >= 5:
            # 第一个点（起始时间）
            label_indices.append(0)
            
            # 中间3个点，均匀分布在索引1到total_points-2之间
            middle_start = 1
            middle_end = total_points - 2
            middle_count = 3
            
            for i in range(middle_count):
                idx = middle_start + int((middle_end - middle_start) * (i + 1) / (middle_count + 1))
                label_indices.append(idx)
            
            # 最后一个点（最新时间）
            label_indices.append(total_points - 1)
        else:
            # 数据点不足5个时，显示所有点
            label_indices = list(range(total_points))
        
        # 标记应该显示的点
        for idx in label_indices:
            x, y, price, timestamp, _ = points[idx]
            points[idx] = (x, y, price, timestamp, True)
    
    # 绘制连线
    for i in range(len(points) - 1):
        x1, y1, p1, _, _ = points[i]
        x2, y2, p2, _, _ = points[i + 1]
        
        # 根据涨跌设置颜色
        color = "red" if p2 >= p1 else "green"
        kline_canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
    
    # 标题
    kline_canvas.create_text(canvas_width // 2, 15, 
                           text="黄金实时价格走势", 
                           fill="#333", font=("微软雅黑", 11, "bold"))
    
    # 统计信息
    current_price = kline_data[-1][1]
    start_price = kline_data[0][1]
    change = current_price - start_price
    change_percent = (change / start_price) * 100 if start_price > 0 else 0
    change_color = "red" if change >= 0 else "green"
    change_symbol = "+" if change >= 0 else ""
    
    info_text = f"最新: {current_price:.2f}  |  涨跌: {change_symbol}{change:.2f} ({change_symbol}{change_percent:.2f}%)"
    kline_canvas.create_text(canvas_width // 2, canvas_height - 15, 
                           text=info_text, 
                           fill=change_color, font=("微软雅黑", 9, "bold"))
    
    # 时间标签（固定显示5个：首尾+中间3个均匀分布的点）
    if len(points) > 0:
        for idx, (x, y, price, timestamp, should_show) in enumerate(points):
            if should_show:
                # 首尾标签左/右对齐，中间标签居中对齐
                if idx == 0:
                    anchor_style = tk.W
                    display_time = start_time if start_time else timestamp
                elif idx == len(points) - 1:
                    anchor_style = tk.E
                    display_time = timestamp
                else:
                    anchor_style = tk.CENTER
                    display_time = timestamp
                kline_canvas.create_text(x, canvas_height - margin_bottom + 15, 
                                       text=display_time, 
                                       fill="#666", font=("Arial", 8), anchor=anchor_style)

# ------------------- 金价获取核心 -------------------
def get_price():
    """获取当前黄金价格"""
    try:
        api_name = current_api_var.get()
        api_info = APIS[api_name]
        url = api_info["url"]
        
        if api_name == "浙商积存金":
            res = requests.get(url, timeout=5).json()
            price = float(res['resultData']['datas']['price'])
            return price
        return None
    except Exception:
        return None

# ------------------- 更新颜色和收益 -------------------
def update_profit_display(price):
    """更新收益显示和颜色"""
    try:
        holdings = float(holdings_var.get())
        avg_price = float(avg_price_var.get())
        
        if holdings > 0 and avg_price > 0:
            profit = (price - avg_price) * holdings
            profit_rate = ((price - avg_price) / avg_price) * 100
            
            profit_display_var.set(f"{profit:.2f}    {profit_rate:.2f}%")
            
            if price > avg_price:
                color = "red"
            elif price < avg_price:
                color = "green"
            else:
                color = "black"
            
            price_label.config(fg=color)
            for widget in profit_frame.winfo_children():
                widget.config(fg=color)
        else:
            profit_display_var.set("")
            price_label.config(fg="black")
            for widget in profit_frame.winfo_children():
                widget.config(fg="black")
    except Exception:
        profit_display_var.set("")

# ------------------- UI更新（主线程） -------------------
def update_ui(price, api_name, now):
    """在主线程中更新所有UI元素"""
    global start_time
    time_var.set(now)

    if price is not None:
        price_var.set(f"{price:.2f} {APIS[api_name]['unit']}")
        status_var.set("正常监控中")

        # 记录K线数据（存储所有历史数据，不删除）
        kline_data.append((now, price))
        if len(kline_data) == 1:
            start_time = now
            first_data_point = (now, price)

        # 如果K线图窗口存在，则更新绘制
        if kline_window is not None:
            try:
                draw_kline()
            except Exception:
                pass

        update_profit_display(price)
        check_alert(price)
    else:
        status_var.set("⚠ 获取失败，正在重试")


# ------------------- 监控线程 -------------------
def monitor_loop():
    """后台线程：仅获取数据，UI更新交给主线程"""
    global monitor_running
    while monitor_running:
        api_name = current_api_var.get()
        price = get_price()
        now = time.strftime("%H:%M:%S")
        root.after(0, update_ui, price, api_name, now)
        time.sleep(REFRESH_SEC)

# ------------------- 提醒逻辑 -------------------
def check_alert(price):
    """检查是否达到提醒条件"""
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

# ------------------- 启动 -------------------
def on_closing():
    """窗口关闭处理"""
    global monitor_running
    monitor_running = False
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
threading.Thread(target=monitor_loop, daemon=True).start()

root.mainloop()
import os

# --- Anthropic API ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
LLM_MAX_TOKENS = 2048
LLM_THINKING_BUDGET = 1600

# --- Intervals (seconds) ---
REFRESH_SEC = 3
TECHNICAL_INTERVAL = 10
STRATEGY_INTERVAL = 60

# --- Data ---
MAX_HISTORY_POINTS = 500
MIN_POINTS_FOR_ANALYSIS = 20

# --- Technical Indicators ---
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STDDEV = 2.0
SUPPORT_RESISTANCE_WINDOW = 20

# --- API Endpoints ---
APIS = {
    "浙商积存金": {
        "url": "https://api.jdjygold.com/gw2/generic/jrm/h5/m/stdLatestPrice?productSku=1961543816",
        "unit": "元/克",
        "type": "domestic",
        "parser": "zheshang"
    },
}

# --- GUI ---
WINDOW_TITLE = "黄金智能监控系统"
WINDOW_SIZE = "900x700"
WINDOW_OPACITY = 0.92
FONT_PRICE = ("Arial", 30, "bold")
FONT_REASONING = ("微软雅黑", 9)
FONT_STATUS = ("微软雅黑", 10)

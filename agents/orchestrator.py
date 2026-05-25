import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from config import (
    APIS, ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    REFRESH_SEC, TECHNICAL_INTERVAL, STRATEGY_INTERVAL,
    MAX_HISTORY_POINTS, MIN_POINTS_FOR_ANALYSIS,
)
from .data_fetcher import DataFetcher, PricePoint
from .technical_analyst import TechnicalAnalyst, TechnicalIndicators
from .strategy_agent import StrategyAgent, StrategyRecommendation


@dataclass
class AgentStatus:
    name: str = ""
    status: str = "idle"
    last_run: Optional[float] = None
    last_duration_ms: float = 0.0
    error_message: str = ""
    run_count: int = 0


@dataclass
class SharedContext:
    lock: threading.Lock = field(default_factory=threading.Lock)
    price_history: List[PricePoint] = field(default_factory=list)
    latest_price: Optional[PricePoint] = None
    technical_indicators: Optional[TechnicalIndicators] = None
    strategy_recommendation: Optional[StrategyRecommendation] = None
    recommendation_history: List[StrategyRecommendation] = field(default_factory=list)
    agent_statuses: Dict[str, AgentStatus] = field(default_factory=dict)
    portfolio: Dict[str, float] = field(default_factory=dict)
    alert_state: Optional[str] = None

    def add_price(self, pp: PricePoint):
        self.latest_price = pp
        self.price_history.append(pp)
        if len(self.price_history) > MAX_HISTORY_POINTS:
            self.price_history = self.price_history[-MAX_HISTORY_POINTS:]


class Orchestrator:
    def __init__(self, gui_callback: Callable[["SharedContext"], None]):
        self.gui_callback = gui_callback
        self.context = SharedContext()
        self.fetcher = DataFetcher(APIS)
        self.analyst = TechnicalAnalyst()
        self.strategist: Optional[StrategyAgent] = None
        if ANTHROPIC_API_KEY:
            self.strategist = StrategyAgent(ANTHROPIC_API_KEY, ANTHROPIC_MODEL)

        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_technical_run = 0.0
        self.last_strategy_run = 0.0

    def start(self):
        self.running = True
        self._init_agent_statuses()
        self.thread = threading.Thread(target=self._main_loop, daemon=True, name="Orchestrator")
        self.thread.start()

    def stop(self):
        self.running = False

    def update_portfolio(self, holdings: float, avg_price: float):
        with self.context.lock:
            self.context.portfolio = {"holdings": holdings, "avg_price": avg_price}

    def force_strategy_analysis(self):
        if self.strategist and self.context.latest_price and self.context.technical_indicators:
            self.last_strategy_run = 0
            self.strategist.last_call_time = 0

    def _main_loop(self):
        while self.running:
            cycle_start = time.time()

            # Step 1: Data Fetching
            self._update_status("DataFetcher", "running")
            t0 = time.time()
            price = self.fetcher.fetch_price("浙商积存金")
            duration = (time.time() - t0) * 1000

            if price:
                self._update_status("DataFetcher", "success", duration_ms=duration)
                with self.context.lock:
                    self.context.add_price(price)
            else:
                self._update_status("DataFetcher", "error", "API request failed", duration)

            # Step 2: Technical Analysis
            now = time.time()
            if (now - self.last_technical_run >= TECHNICAL_INTERVAL
                    and len(self.context.price_history) >= MIN_POINTS_FOR_ANALYSIS):
                self._update_status("TechnicalAnalyst", "running")
                t0 = time.time()
                with self.context.lock:
                    history_snapshot = list(self.context.price_history)
                indicators = self.analyst.compute_all(history_snapshot)
                duration = (time.time() - t0) * 1000
                with self.context.lock:
                    self.context.technical_indicators = indicators
                self._update_status("TechnicalAnalyst", "success", duration_ms=duration)
                self.last_technical_run = now

            # Step 3: Strategy Analysis (LLM)
            if (self.strategist
                    and now - self.last_strategy_run >= STRATEGY_INTERVAL
                    and self.context.technical_indicators
                    and len(self.context.price_history) >= MIN_POINTS_FOR_ANALYSIS
                    and self.context.latest_price):
                self._update_status("StrategyAgent", "running")
                t0 = time.time()
                try:
                    with self.context.lock:
                        history = list(self.context.price_history)
                        indicators = self.context.technical_indicators
                        portfolio = dict(self.context.portfolio)
                        latest = self.context.latest_price

                    recommendation = self.strategist.analyze(
                        current_price=latest.price if latest else 0,
                        price_history=history,
                        indicators=indicators,
                        portfolio=portfolio,
                        yesterday_price=latest.yesterday_price if latest else None,
                    )
                    duration = (time.time() - t0) * 1000
                    if recommendation:
                        with self.context.lock:
                            self.context.strategy_recommendation = recommendation
                            self.context.recommendation_history.append(recommendation)
                        self._update_status("StrategyAgent", "success", duration_ms=duration)
                    else:
                        self._update_status("StrategyAgent", "success", "rate limited", duration)
                except Exception as e:
                    self._update_status("StrategyAgent", "error", str(e))
                self.last_strategy_run = now

            # Step 4: GUI Update
            self._update_status("Orchestrator", "success")
            self.gui_callback(self.context)

            # Sleep until next cycle
            elapsed = time.time() - cycle_start
            sleep_time = max(0, REFRESH_SEC - elapsed)
            time.sleep(sleep_time)

    def _init_agent_statuses(self):
        for name in ["DataFetcher", "TechnicalAnalyst", "StrategyAgent", "Orchestrator"]:
            if name == "StrategyAgent" and not self.strategist:
                self.context.agent_statuses[name] = AgentStatus(
                    name=name, status="disabled", error_message="未设置 ANTHROPIC_API_KEY"
                )
            else:
                self.context.agent_statuses[name] = AgentStatus(name=name, status="idle")

    def _update_status(self, name: str, status: str, error: str = "", duration_ms: float = 0):
        agent = self.context.agent_statuses.get(name)
        if agent:
            agent.status = status
            if status in ("success", "error"):
                agent.last_run = time.time()
                agent.last_duration_ms = duration_ms
                agent.run_count += 1
            agent.error_message = error

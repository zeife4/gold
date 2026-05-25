import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from config import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BB_PERIOD, BB_STDDEV, SUPPORT_RESISTANCE_WINDOW, MIN_POINTS_FOR_ANALYSIS,
)
from .data_fetcher import PricePoint


@dataclass
class TechnicalIndicators:
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    rsi: Optional[float] = None
    rsi_zone: str = "unknown"
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_crossover: str = "unknown"
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width_pct: Optional[float] = None
    bb_position: str = "unknown"
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    ma5_ma10_cross: str = "none"
    trend_signal: str = "neutral"


class TechnicalAnalyst:
    def __init__(self):
        self.rsi_period = RSI_PERIOD
        self.macd_fast = MACD_FAST
        self.macd_slow = MACD_SLOW
        self.macd_signal = MACD_SIGNAL
        self.bb_period = BB_PERIOD
        self.bb_stddev = BB_STDDEV
        self.sr_window = SUPPORT_RESISTANCE_WINDOW

    def compute_all(self, price_history: List[PricePoint]) -> TechnicalIndicators:
        prices = np.array([p.price for p in price_history], dtype=np.float64)
        if len(prices) < MIN_POINTS_FOR_ANALYSIS:
            return TechnicalIndicators()

        rsi_val = self._rsi(prices)
        macd_line, macd_sig, macd_hist = self._macd(prices)
        bb_upper, bb_middle, bb_lower = self._bollinger_bands(prices)

        return TechnicalIndicators(
            ma5=self._sma(prices, 5),
            ma10=self._sma(prices, 10),
            ma20=self._sma(prices, 20),
            rsi=rsi_val,
            rsi_zone=self._rsi_zone_label(rsi_val),
            macd_line=macd_line,
            macd_signal=macd_sig,
            macd_histogram=macd_hist,
            macd_crossover=self._macd_cross_label(macd_line, macd_sig),
            bb_upper=bb_upper,
            bb_middle=bb_middle,
            bb_lower=bb_lower,
            bb_width_pct=self._bb_width(bb_upper, bb_middle, bb_lower),
            bb_position=self._bb_position_label(prices[-1], bb_upper, bb_lower),
            support_level=self._find_support(prices),
            resistance_level=self._find_resistance(prices),
            ma5_ma10_cross=self._ma5_ma10_cross(prices),
            trend_signal=self._trend_aggregate(prices),
        )

    def _sma(self, prices: np.ndarray, period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        return float(np.mean(prices[-period:]))

    def _ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        alpha = 2.0 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
        return ema

    def _rsi(self, prices: np.ndarray) -> Optional[float]:
        if len(prices) < self.rsi_period + 1:
            return None
        deltas = np.diff(prices[-(self.rsi_period + 1):])
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    def _macd(self, prices: np.ndarray) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(prices) < self.macd_slow + self.macd_signal:
            return (None, None, None)
        ema_fast = self._ema(prices, self.macd_fast)
        ema_slow = self._ema(prices, self.macd_slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, self.macd_signal)
        histogram = macd_line - signal_line
        return (float(macd_line[-1]), float(signal_line[-1]), float(histogram[-1]))

    def _bollinger_bands(self, prices: np.ndarray) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(prices) < self.bb_period:
            return (None, None, None)
        window = prices[-self.bb_period:]
        middle = np.mean(window)
        std = np.std(window, ddof=0)
        return (
            float(middle + self.bb_stddev * std),
            float(middle),
            float(middle - self.bb_stddev * std),
        )

    def _find_support(self, prices: np.ndarray) -> Optional[float]:
        if len(prices) < self.sr_window:
            return None
        recent = prices[-self.sr_window:]
        local_mins = []
        for i in range(1, len(recent) - 1):
            if recent[i] <= recent[i - 1] and recent[i] <= recent[i + 1]:
                local_mins.append(recent[i])
        if not local_mins:
            return float(np.min(recent))
        return float(min(local_mins))

    def _find_resistance(self, prices: np.ndarray) -> Optional[float]:
        if len(prices) < self.sr_window:
            return None
        recent = prices[-self.sr_window:]
        local_maxs = []
        for i in range(1, len(recent) - 1):
            if recent[i] >= recent[i - 1] and recent[i] >= recent[i + 1]:
                local_maxs.append(recent[i])
        if not local_maxs:
            return float(np.max(recent))
        return float(max(local_maxs))

    def _rsi_zone_label(self, rsi: Optional[float]) -> str:
        if rsi is None: return "unknown"
        if rsi < 30: return "oversold"
        if rsi > 70: return "overbought"
        return "neutral"

    def _ma5_ma10_cross(self, prices: np.ndarray) -> str:
        if len(prices) < 11:
            return "none"
        ma5_now = self._sma(prices, 5)
        ma10_now = self._sma(prices, 10)
        ma5_prev = self._sma(prices[:-1], 5)
        ma10_prev = self._sma(prices[:-1], 10)
        if ma5_prev is None or ma10_prev is None or ma5_now is None or ma10_now is None:
            return "none"
        if ma5_prev <= ma10_prev and ma5_now > ma10_now:
            return "golden_cross"
        if ma5_prev >= ma10_prev and ma5_now < ma10_now:
            return "death_cross"
        return "none"

    def _macd_cross_label(self, macd_line: Optional[float], signal: Optional[float]) -> str:
        if macd_line is None or signal is None:
            return "unknown"
        if macd_line > signal:
            return "bullish"
        return "bearish"

    def _bb_position_label(self, price: float, upper: Optional[float], lower: Optional[float]) -> str:
        if upper is None or lower is None:
            return "unknown"
        if price > upper: return "above_upper"
        if price < lower: return "below_lower"
        return "inside"

    def _bb_width(self, upper: Optional[float], middle: Optional[float], lower: Optional[float]) -> Optional[float]:
        if upper is None or middle is None or lower is None or middle == 0:
            return None
        return (upper - lower) / middle * 100

    def _trend_aggregate(self, prices: np.ndarray) -> str:
        ma5 = self._sma(prices, 5)
        ma10 = self._sma(prices, 10)
        ma20 = self._sma(prices, 20)
        if ma5 and ma10 and ma20:
            if ma5 > ma10 > ma20: return "bullish"
            if ma5 < ma10 < ma20: return "bearish"
        if ma5 and ma20:
            if ma5 > ma20: return "bullish"
            if ma5 < ma20: return "bearish"
        return "neutral"

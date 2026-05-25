import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import anthropic

from config import (
    ANTHROPIC_MODEL, LLM_MAX_TOKENS, LLM_THINKING_BUDGET, STRATEGY_INTERVAL,
)
from .data_fetcher import PricePoint
from .technical_analyst import TechnicalIndicators


@dataclass
class StrategyRecommendation:
    action: str = ""
    confidence: str = ""
    reasoning_cn: str = ""
    key_points: List[str] = field(default_factory=list)
    trend_analysis: Dict = field(default_factory=dict)
    indicator_alignment: Dict = field(default_factory=dict)
    market_regime: Dict = field(default_factory=dict)
    risk_assessment: Dict = field(default_factory=dict)
    timestamp: float = 0.0
    model_used: str = ""


class StrategyAgent:
    def __init__(self, api_key: str, model: str = ANTHROPIC_MODEL):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for StrategyAgent")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.last_call_time: float = 0.0
        self.min_interval: float = STRATEGY_INTERVAL
        self._last_recommendation: Optional[StrategyRecommendation] = None

    def analyze(
        self,
        current_price: float,
        price_history: List[PricePoint],
        indicators: TechnicalIndicators,
        portfolio: Dict[str, float],
        yesterday_price: Optional[float] = None,
    ) -> Optional[StrategyRecommendation]:
        now = time.time()
        if now - self.last_call_time < self.min_interval:
            return None
        self.last_call_time = now

        prompt = self._build_prompt(current_price, price_history, indicators, portfolio, yesterday_price)
        system = self._system_prompt()

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=LLM_MAX_TOKENS,
                thinking={"type": "enabled", "budget_tokens": LLM_THINKING_BUDGET},
                temperature=0.3,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            recommendation = self._parse_response(response)
            self._last_recommendation = recommendation
            return recommendation
        except Exception:
            return None

    def force_analyze(
        self,
        current_price: float,
        price_history: List[PricePoint],
        indicators: TechnicalIndicators,
        portfolio: Dict[str, float],
        yesterday_price: Optional[float] = None,
    ) -> Optional[StrategyRecommendation]:
        self.last_call_time = 0
        return self.analyze(current_price, price_history, indicators, portfolio, yesterday_price)

    @property
    def last_recommendation(self) -> Optional[StrategyRecommendation]:
        return self._last_recommendation

    def _system_prompt(self) -> str:
        return """你是一位专业的黄金交易分析师，精通技术分析和市场判断。

你的任务是分析提供的市场数据，完成以下五步推理，并给出结构化的交易建议。

## 重要原则
1. 基于数据，而非情绪
2. 承认不确定性，不要给出100%确定的建议
3. 当指标互相矛盾时，明确指出冲突
4. 始终用中文给出解释
5. 回复格式必须是严格的JSON，不要包含其他文字

## 五步推理框架

**步骤1 - 趋势分析**
分析价格走势方向（上涨/下跌/震荡）和趋势强度。
考察：价格序列的方向性、连续涨跌天数、波动幅度变化。

**步骤2 - 技术指标校验**
评估MA均线排列、MACD信号、RSI位置、布林带位置是否互相印证。
检查：均线多头/空头排列、金叉/死叉、RSI超买/超卖、MACD柱状图方向、布林带突破。

**步骤3 - 市场状态判断**
综合趋势和指标，将市场分类为：强牛市、弱牛市、震荡市、弱熊市、强熊市、高波动突破。

**步骤4 - 风险评估**
识别关键风险：趋势反转信号、超买超卖极端值、支撑/阻力突破风险、假突破风险。

**步骤5 - 最终建议**
综合以上推理，给出：操作建议（买入/卖出/持有）、信心等级（高/中/低）、用中文详细解释理由。

## 输出格式
严格按照以下JSON格式输出，不要有任何偏离：
```json
{
  "trend_analysis": {
    "direction": "上涨/下跌/震荡",
    "strength": "强/弱",
    "detail": "对趋势的具体分析说明，50字以内"
  },
  "indicator_alignment": {
    "ma_signal": "多头排列/空头排列/交叉/无明确信号",
    "rsi_signal": "超买/超卖/中性",
    "macd_signal": "金叉/死叉/柱状图放大/柱状图缩小",
    "bb_signal": "上轨附近/中轨附近/下轨附近/突破上轨/突破下轨",
    "overall": "指标一致看多/指标一致看空/指标分歧"
  },
  "market_regime": {
    "regime": "强牛市/弱牛市/震荡市/弱熊市/强熊市/高波动突破",
    "description": "对当前市场状态的简要描述，50字以内"
  },
  "risk_assessment": {
    "risks": ["风险点1", "风险点2"],
    "overall_risk": "低/中/高"
  },
  "recommendation": {
    "action": "BUY/SELL/HOLD",
    "confidence": "LOW/MEDIUM/HIGH",
    "reasoning_cn": "最终建议的中文解释，包含关键判断依据",
    "key_points": ["关键要点1", "关键要点2", "关键要点3"]
  }
}
```"""

    def _build_prompt(
        self,
        current_price: float,
        price_history: List[PricePoint],
        indicators: TechnicalIndicators,
        portfolio: Dict[str, float],
        yesterday_price: Optional[float],
    ) -> str:
        recent = price_history[-20:]
        history_lines = []
        for i, pp in enumerate(recent):
            dt = datetime.fromtimestamp(pp.timestamp).strftime("%H:%M:%S")
            history_lines.append(f"  {i+1:2d}. {dt}  {pp.price:.2f} {pp.unit}")

        ind = indicators
        ma5_s = f"{ind.ma5:.2f}" if ind.ma5 else "N/A"
        ma10_s = f"{ind.ma10:.2f}" if ind.ma10 else "N/A"
        ma20_s = f"{ind.ma20:.2f}" if ind.ma20 else "N/A"
        rsi_s = f"{ind.rsi:.1f}" if ind.rsi else "N/A"
        macd_l_s = f"{ind.macd_line:.4f}" if ind.macd_line else "N/A"
        macd_sig_s = f"{ind.macd_signal:.4f}" if ind.macd_signal else "N/A"
        macd_h_s = f"{ind.macd_histogram:.4f}" if ind.macd_histogram else "N/A"
        bb_u_s = f"{ind.bb_upper:.2f}" if ind.bb_upper else "N/A"
        bb_m_s = f"{ind.bb_middle:.2f}" if ind.bb_middle else "N/A"
        bb_l_s = f"{ind.bb_lower:.2f}" if ind.bb_lower else "N/A"
        bb_w_s = f"{ind.bb_width_pct:.1f}%" if ind.bb_width_pct else "N/A"
        sup_s = f"{ind.support_level:.2f}" if ind.support_level else "N/A"
        res_s = f"{ind.resistance_level:.2f}" if ind.resistance_level else "N/A"

        indicator_text = f"""
均线系统:
  MA5:  {ma5_s}
  MA10: {ma10_s}
  MA20: {ma20_s}
  均线信号: {ind.ma5_ma10_cross}
  趋势信号: {ind.trend_signal}

RSI(14): {rsi_s}  ({ind.rsi_zone})

MACD(12,26,9):
  MACD线: {macd_l_s}
  信号线: {macd_sig_s}
  柱状图: {macd_h_s}
  MACD信号: {ind.macd_crossover}

布林带(20,2):
  上轨: {bb_u_s}
  中轨: {bb_m_s}
  下轨: {bb_l_s}
  带宽: {bb_w_s}
  当前价格位置: {ind.bb_position}

支撑位: {sup_s}
阻力位: {res_s}
"""

        holdings = portfolio.get("holdings", 0)
        avg_price = portfolio.get("avg_price", 0)
        profit = (current_price - avg_price) * holdings if holdings and avg_price else 0
        profit_pct = ((current_price - avg_price) / avg_price * 100) if avg_price else 0

        portfolio_text = f"""
持有数量: {holdings} 克
持仓均价: {avg_price:.2f} 元/克
当前浮盈: {profit:.2f} 元 ({profit_pct:+.2f}%)
"""

        day_change = ((current_price - yesterday_price) / yesterday_price * 100) if yesterday_price else 0

        prompt = f"""请分析以下黄金市场数据，完成五步推理并给出交易建议。

## 当前市场数据
当前价格: {current_price:.2f} 元/克
昨日收盘: {yesterday_price:.2f} 元/克 (if available)
日涨跌幅: {day_change:+.2f}%

## 近期价格走势（最近20个数据点）
```
{chr(10).join(history_lines)}
```

## 技术指标
{indicator_text}

## 用户持仓
{portfolio_text}

请开始你的五步分析。记住：只输出JSON，不要其他内容。"""
        return prompt

    def _parse_response(self, response) -> StrategyRecommendation:
        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start == -1 or json_end == -1:
            raise ValueError(f"No JSON found in response")

        json_str = text[json_start:json_end + 1]
        data = json.loads(json_str)

        return StrategyRecommendation(
            action=data["recommendation"]["action"],
            confidence=data["recommendation"]["confidence"],
            reasoning_cn=data["recommendation"]["reasoning_cn"],
            key_points=data["recommendation"]["key_points"],
            trend_analysis=data["trend_analysis"],
            indicator_alignment=data["indicator_alignment"],
            market_regime=data["market_regime"],
            risk_assessment=data["risk_assessment"],
            timestamp=time.time(),
            model_used=self.model,
        )

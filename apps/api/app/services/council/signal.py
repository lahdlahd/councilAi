"""Deterministic market-signal reader.

Turns a real MarketSnapshot into structured, interpretable readings. Used two ways:
  1. As factual EVIDENCE injected into LLM prompts (so agents cite real numbers).
  2. As the basis for OFFLINE-mode agent reasoning (deterministic, no LLM).

Nothing here is fabricated — every value derives from the live snapshot/indicators.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import Side
from app.domain.models import MarketSnapshot


@dataclass
class Signal:
    bias: float                 # net directional bias in [-1, 1] (+bullish / -bearish)
    rsi_read: str               # "oversold" | "overbought" | "neutral"
    macd_read: str              # "bullish" | "bearish" | "flat"
    trend_read: str             # "uptrend" | "downtrend" | "ranging"
    momentum_read: str          # from 24h change
    volatility_level: str       # "low" | "elevated" | "high"
    risk_score: float           # 0 (calm) .. 1 (dangerous)
    sentiment: float            # [-1, 1], proxy from momentum + trend

    def side(self) -> Side:
        if self.bias > 0.2:
            return Side.BUY
        if self.bias < -0.2:
            return Side.SELL
        return Side.HOLD


# Volatility (% realized) thresholds for classification.
_VOL_ELEVATED = 0.4
_VOL_HIGH = 0.9


def read_signal(snap: MarketSnapshot) -> Signal:
    components: list[float] = []

    rsi_read = "neutral"
    macd_read = "flat"
    trend_read = "ranging"

    if snap.indicators is not None:
        ind = snap.indicators

        # RSI
        if ind.rsi <= 30:
            rsi_read, rsi_bias = "oversold", 0.6      # oversold -> mean-revert up
        elif ind.rsi >= 70:
            rsi_read, rsi_bias = "overbought", -0.6
        else:
            rsi_read, rsi_bias = "neutral", (50 - ind.rsi) / 100  # mild contrarian tilt
        components.append(rsi_bias)

        # MACD histogram
        if ind.macd.histogram > 0:
            macd_read, macd_bias = "bullish", 0.5
        elif ind.macd.histogram < 0:
            macd_read, macd_bias = "bearish", -0.5
        else:
            macd_read, macd_bias = "flat", 0.0
        components.append(macd_bias)

        # Trend via EMA stack + price position
        if snap.price > ind.ema.ema50 and ind.ema.ema12 > ind.ema.ema26:
            trend_read, trend_bias = "uptrend", 0.6
        elif snap.price < ind.ema.ema50 and ind.ema.ema12 < ind.ema.ema26:
            trend_read, trend_bias = "downtrend", -0.6
        else:
            trend_read, trend_bias = "ranging", 0.0
        components.append(trend_bias)

    # 24h momentum
    mom_bias = max(-1.0, min(1.0, snap.change24h / 5.0))  # ±5% saturates
    momentum_read = (
        "rising" if snap.change24h > 0.5 else "falling" if snap.change24h < -0.5 else "flat"
    )
    components.append(mom_bias * 0.5)

    bias = sum(components) / len(components) if components else 0.0
    bias = max(-1.0, min(1.0, bias))

    # Volatility classification + risk score
    vol = snap.volatility
    if vol >= _VOL_HIGH:
        volatility_level = "high"
    elif vol >= _VOL_ELEVATED:
        volatility_level = "elevated"
    else:
        volatility_level = "low"
    # Risk grows with volatility and with conflict between trend and momentum.
    conflict = abs(mom_bias - bias)
    risk_score = max(0.0, min(1.0, vol / (_VOL_HIGH * 1.5) + conflict * 0.25))

    sentiment = max(-1.0, min(1.0, mom_bias * 0.6 + bias * 0.4))

    return Signal(
        bias=round(bias, 3),
        rsi_read=rsi_read,
        macd_read=macd_read,
        trend_read=trend_read,
        momentum_read=momentum_read,
        volatility_level=volatility_level,
        risk_score=round(risk_score, 3),
        sentiment=round(sentiment, 3),
    )

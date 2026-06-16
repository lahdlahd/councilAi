"""Pure technical-indicator functions. No I/O, fully deterministic, unit-tested.

Inputs are chronological (oldest -> newest) close/high/low series.
"""

from __future__ import annotations

import math

from app.domain.models import Ema, Indicators, Macd


def ema_series(values: list[float], period: int) -> list[float]:
    """Exponential moving average, seeded with the SMA of the first `period` values.

    Returns a series aligned to `values` (entries before the seed are absent).
    Raises if there isn't enough data.
    """
    if len(values) < period:
        raise ValueError(f"need >= {period} values for EMA, got {len(values)}")
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out = [seed]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def ema_last(values: list[float], period: int) -> float:
    return ema_series(values, period)[-1]


def rsi(closes: list[float], period: int = 14) -> float:
    """Wilder's RSI over the last `period` changes. Returns 0-100."""
    if len(closes) < period + 1:
        raise ValueError(f"need >= {period + 1} closes for RSI")
    gains, losses = 0.0, 0.0
    # Initial average over the first `period` deltas.
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    # Wilder smoothing across the remaining deltas.
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Macd:
    """MACD line, signal line, and histogram from close prices."""
    if len(closes) < slow + signal:
        raise ValueError(f"need >= {slow + signal} closes for MACD")
    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    # Align tails (fast_ema is longer because it seeds earlier).
    offset = len(fast_ema) - len(slow_ema)
    macd_line = [f - s for f, s in zip(fast_ema[offset:], slow_ema)]
    signal_line = ema_series(macd_line, signal)
    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    return Macd(
        macd=round(macd_val, 4),
        signal=round(signal_val, 4),
        histogram=round(macd_val - signal_val, 4),
    )


def realized_volatility(closes: list[float], window: int = 30) -> float:
    """Standard deviation of recent simple returns, as a percentage.

    A pragmatic, honest 'volatility' figure for display and the confidence engine.
    """
    series = closes[-(window + 1):] if len(closes) > window + 1 else closes
    if len(series) < 2:
        return 0.0
    returns = [
        (series[i] - series[i - 1]) / series[i - 1]
        for i in range(1, len(series))
        if series[i - 1]
    ]
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return round(math.sqrt(var) * 100, 3)


def compute_indicators(candles: list[list[float]]) -> Indicators:
    """Build the Indicators model from chronological candles.

    candle row = [ts, open, high, low, close, baseVol, quoteVol]
    """
    closes = [row[4] for row in candles]
    return Indicators(
        rsi=rsi(closes),
        macd=macd(closes),
        ema=Ema(
            ema12=round(ema_last(closes, 12), 2),
            ema26=round(ema_last(closes, 26), 2),
            ema50=round(ema_last(closes, 50), 2),
        ),
    )

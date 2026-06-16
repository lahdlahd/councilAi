"""Unit tests for the pure indicator functions.

These guard the math the Technical Analyst will rely on. Values are checked against
hand-computable expectations and known properties (RSI bounds, EMA monotonicity).
"""

from __future__ import annotations

import math

import pytest

from app.services.market.indicators import (
    ema_last,
    ema_series,
    macd,
    realized_volatility,
    rsi,
)


def test_ema_seed_is_sma():
    values = [1, 2, 3, 4, 5]
    series = ema_series(values, period=5)
    # With period == len, the only EMA point is the SMA of all values.
    assert series == [pytest.approx(3.0)]


def test_ema_tracks_upward_series():
    values = [float(i) for i in range(1, 51)]
    assert ema_last(values, 12) < values[-1]  # lags a rising series
    assert ema_last(values, 12) > ema_last(values, 26)  # faster EMA is closer to price


def test_rsi_all_gains_is_100():
    closes = [float(i) for i in range(1, 30)]
    assert rsi(closes) == 100.0


def test_rsi_all_losses_is_low():
    closes = [float(i) for i in range(30, 1, -1)]
    assert rsi(closes) == pytest.approx(0.0, abs=1e-6)


def test_rsi_within_bounds():
    closes = [100, 102, 101, 105, 103, 107, 106, 110, 108, 112,
              111, 115, 113, 117, 116, 120, 118, 122, 121, 125]
    value = rsi([float(c) for c in closes])
    assert 0.0 <= value <= 100.0


def test_macd_histogram_relation():
    closes = [float(100 + math.sin(i / 3) * 5 + i * 0.2) for i in range(60)]
    result = macd(closes)
    assert result.histogram == pytest.approx(result.macd - result.signal, abs=1e-6)


def test_realized_volatility_zero_for_flat_series():
    assert realized_volatility([100.0] * 40) == 0.0


def test_realized_volatility_positive_for_moving_series():
    closes = [float(100 + (i % 5)) for i in range(40)]
    assert realized_volatility(closes) > 0.0


def test_indicator_input_guards():
    with pytest.raises(ValueError):
        rsi([1.0, 2.0])  # not enough data
    with pytest.raises(ValueError):
        ema_series([1.0], period=5)

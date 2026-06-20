"""Domain enums shared across the council. Pure values, no I/O."""

from __future__ import annotations

from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class DataSource(str, Enum):
    BITGET = "bitget"
    COINGECKO = "coingecko"


class MarketType(str, Enum):
    SPOT = "spot"
    FUTURES = "futures"  # Bitget USDT-M perpetual ("mix")


class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TradeAction(str, Enum):
    OPEN = "open"
    INCREASE = "increase"
    REDUCE = "reduce"
    CLOSE = "close"
    FLIP = "flip"


class ConnectionState(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"  # e.g. running on CoinGecko fallback


class AgentId(str, Enum):
    TECHNICAL = "technical"
    NEWS = "news"
    QUANT = "quant"
    RISK = "risk"
    EXECUTION = "execution"


class Stance(str, Enum):
    """How an agent's message relates to the debate so far."""

    OPENING = "opening"      # first to speak on a thread
    AGREE = "agree"
    DISAGREE = "disagree"
    CHALLENGE = "challenge"
    NEUTRAL = "neutral"


class Phase(str, Enum):
    IDLE = "idle"
    DEBATING = "debating"
    VOTING = "voting"
    DECIDED = "decided"
    BLOCKED = "blocked"      # risk veto

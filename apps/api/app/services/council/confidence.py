"""Council Confidence Score — deterministic 0-100 from four components.

  score = f(agreement, risk, volatility, sentiment)

Pure and reproducible (no LLM randomness), so the big confidence visualization is
explainable: each component is returned in the breakdown for the UI.
"""

from __future__ import annotations

from collections import Counter

from app.domain.models import ConfidenceBreakdown, MarketSnapshot, Vote
from app.services.council.signal import read_signal

# Weights sum to 1.0
_W_AGREEMENT = 0.40
_W_RISK = 0.30
_W_VOLATILITY = 0.15
_W_SENTIMENT = 0.15


def _agreement_score(votes: list[Vote]) -> float:
    """0-100: how concentrated the votes are. Unanimous -> high; 3-way split -> low."""
    if not votes:
        return 0.0
    tally = Counter(v.side for v in votes)
    top = tally.most_common(1)[0][1]
    share = top / len(votes)  # 0.33 (split) .. 1.0 (unanimous)
    return round((share - 1 / 3) / (1 - 1 / 3) * 100, 1)


def compute_confidence(
    snapshot: MarketSnapshot,
    votes: list[Vote],
    risk_score: float | None,
    sentiment: float | None,
    vetoed: bool,
) -> tuple[float, ConfidenceBreakdown]:
    sig = read_signal(snapshot)

    agreement = _agreement_score(votes)
    # Risk component: invert risk_score (0 risk -> 100 confidence).
    rs = risk_score if risk_score is not None else sig.risk_score
    risk_component = round((1 - rs) * 100, 1)
    # Volatility: lower vol -> higher confidence. Normalize against a 1% ceiling.
    vol_component = round(max(0.0, 1 - snapshot.volatility / 1.0) * 100, 1)
    # Sentiment: strength of conviction (|sentiment|), direction-agnostic.
    sent = sentiment if sentiment is not None else sig.sentiment
    sentiment_component = round(abs(sent) * 100, 1)

    breakdown = ConfidenceBreakdown(
        agreement=agreement,
        risk=risk_component,
        volatility=vol_component,
        sentiment=sentiment_component,
    )

    score = (
        _W_AGREEMENT * agreement
        + _W_RISK * risk_component
        + _W_VOLATILITY * vol_component
        + _W_SENTIMENT * sentiment_component
    )
    if vetoed:
        score *= 0.4  # an active veto caps confidence hard
    return round(max(0.0, min(100.0, score)), 1), breakdown

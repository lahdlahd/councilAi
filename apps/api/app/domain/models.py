"""Domain models. Pydantic for validation + clean JSON serialization.

These mirror `packages/shared-types/src/domain.ts`. Field names use camelCase
aliases so the JSON on the wire matches the TypeScript frontend exactly, while
Python code keeps snake_case attribute access.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AgentId, DataSource, Side, Stance


def _camel(s: str) -> str:
    head, *tail = s.split("_")
    return head + "".join(w.capitalize() for w in tail)


class _Base(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
    )

    # Force camelCase on the wire for ALL serialization, regardless of call site.
    # (ser_json_by_alias config is not honored across all pydantic versions, so we
    # default by_alias=True here once and inherit it everywhere.)
    def model_dump_json(self, **kwargs) -> str:  # type: ignore[override]
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(**kwargs)

    def model_dump(self, **kwargs):  # type: ignore[override]
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)


class Macd(_Base):
    macd: float
    signal: float
    histogram: float


class Ema(_Base):
    ema12: float
    ema26: float
    ema50: float


class Indicators(_Base):
    """Technical indicators derived from candles (consumed by the Technical Analyst)."""

    rsi: float = Field(description="14-period RSI, 0-100")
    macd: Macd
    ema: Ema


class Candle(_Base):
    """One OHLC bar for charting. `time` is seconds epoch (TradingView format)."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketSnapshot(_Base):
    """A single point-in-time view of a symbol. The atomic unit the council reasons over."""

    symbol: str
    price: float
    change24h: float = Field(description="24h change as a percentage, e.g. 2.34 = +2.34%")
    high24h: float
    low24h: float
    base_volume: float = Field(description="24h volume in base asset")
    quote_volume: float = Field(description="24h volume in quote (USDT)")
    volatility: float = Field(
        description="Realized volatility (%) from recent candle returns"
    )
    indicators: Indicators | None = None
    ts: int = Field(description="Source timestamp, ms epoch")
    source: DataSource = DataSource.BITGET


# ---------------------------------------------------------------------------
# Council models (Step 2)
# ---------------------------------------------------------------------------


class AgentProfile(_Base):
    """Static identity of an agent, surfaced to the UI (avatar, specialty, persona)."""

    id: AgentId
    name: str
    specialty: str
    personality: str
    avatar: str = Field(description="Emoji or asset key the frontend renders")
    casts_vote: bool = True


class AgentMessage(_Base):
    """One spoken contribution in the debate."""

    message_id: str
    agent_id: AgentId
    text: str
    stance: Stance = Stance.OPENING
    references: list[AgentId] = Field(
        default_factory=list, description="Prior agents this message responds to"
    )
    confidence: float = Field(default=50.0, description="Agent's own conviction 0-100")
    ts: int


class Vote(_Base):
    agent_id: AgentId
    side: Side
    rationale: str = ""


class VetoInfo(_Base):
    by_agent: AgentId = AgentId.RISK
    reason: str
    risk_score: float = Field(default=0.0, description="0-1 danger reading at veto time")
    factors: list[str] = Field(
        default_factory=list, description="Specific risk factors that triggered the block"
    )


class ConfidenceBreakdown(_Base):
    """Components feeding the 0-100 Council Confidence Score."""

    agreement: float
    risk: float
    volatility: float
    sentiment: float


class Recommendation(_Base):
    session_id: str
    symbol: str
    side: Side
    confidence: float = Field(description="Council Confidence Score 0-100")
    summary: str
    consensus_ratio: float = Field(
        default=0.0, description="Share of votes held by the leading side, 0-1"
    )
    consensus_reached: bool = Field(
        default=False, description="True when the leading side meets the quorum threshold"
    )
    vetoed: bool = False
    veto_reason: str | None = None
    ts: int


# ---------------------------------------------------------------------------
# Trade Journal (Step 7)
# ---------------------------------------------------------------------------


class JournalSummary(_Base):
    """Row in the journal list — enough to scan past decisions at a glance."""

    session_id: str
    symbol: str
    started_at: int
    ended_at: int | None = None
    side: Side | None = None
    confidence: float | None = None
    consensus_reached: bool = False
    vetoed: bool = False


class JournalEntry(_Base):
    """Full stored decision — mirrors a session snapshot, replayable in Step 8."""

    session_id: str
    symbol: str
    started_at: int
    ended_at: int | None = None
    phase: str
    snapshot: MarketSnapshot
    messages: list[AgentMessage] = Field(default_factory=list)
    votes: list[Vote] = Field(default_factory=list)
    veto: VetoInfo | None = None
    confidence: float | None = None
    confidence_breakdown: ConfidenceBreakdown | None = None
    recommendation: Recommendation | None = None

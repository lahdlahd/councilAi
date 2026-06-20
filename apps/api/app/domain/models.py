"""Domain models. Pydantic for validation + clean JSON serialization.

These mirror `packages/shared-types/src/domain.ts`. Field names use camelCase
aliases so the JSON on the wire matches the TypeScript frontend exactly, while
Python code keeps snake_case attribute access.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AgentId,
    DataSource,
    MarketType,
    Side,
    Stance,
    TradeAction,
    TradeDirection,
    TradeStatus,
)


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
    market: MarketType = MarketType.SPOT


class SymbolInfo(_Base):
    """A selectable instrument (for the symbol picker)."""

    symbol: str
    base: str
    quote: str
    market: MarketType


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


# ---- Paper trading ---------------------------------------------------------
class PaperTrade(_Base):
    """A simulated position from open to close. Fills are against live Bitget
    prices; nothing is ever sent to an exchange."""

    id: str
    session_id: str | None = Field(default=None, description="Council decision that opened it")
    symbol: str
    market: MarketType = MarketType.SPOT
    direction: TradeDirection
    quantity: float
    entry_price: float
    exit_price: float | None = None
    last_mark_price: float | None = None
    status: TradeStatus = TradeStatus.OPEN
    confidence: float | None = None
    reasoning: str | None = None
    fee: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float | None = None
    current_value: float | None = None   # quantity × current mark
    pnl_pct: float | None = None          # unrealized PnL as % of entry notional
    opened_at: int = Field(description="ms epoch")
    closed_at: int | None = None


class PortfolioState(_Base):
    """A snapshot of the simulated account for the UI."""

    portfolio_id: str
    base_currency: str = "USDT"
    starting_balance: float
    cash: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    total_return_pct: float
    daily_return_pct: float = 0.0
    avg_confidence: float = 0.0
    open_positions: list[PaperTrade] = Field(default_factory=list)
    closed_positions: list[PaperTrade] = Field(default_factory=list)
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0


# ---- Live PnL --------------------------------------------------------------
class LivePosition(_Base):
    """A live, marked-to-market view of one open paper position."""

    id: str
    symbol: str
    market: MarketType
    direction: TradeDirection
    quantity: float
    entry_price: float
    mark_price: float
    current_value: float       # quantity × mark
    unrealized_pnl: float
    pnl_pct: float             # unrealized PnL as % of entry notional


class PnlSnapshot(_Base):
    """A streamed snapshot of live PnL across the whole account."""

    ts: int                    # ms epoch
    cash: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    total_return_pct: float
    positions: list[LivePosition] = Field(default_factory=list)


# ---- Trade Ledger ----------------------------------------------------------
class LedgerEntry(_Base):
    """One row of the trade ledger — unified across open and closed trades.

    For open trades, current_price/pnl are live (marked-to-market); for closed
    trades they reflect the exit price and realized PnL.
    """

    trade_id: str
    opened_at: int                 # timestamp (ms epoch)
    symbol: str                    # trading pair
    market: MarketType
    direction: TradeDirection
    entry_price: float
    quantity: float
    current_price: float
    pnl_pct: float
    pnl_usd: float
    status: TradeStatus
    confidence: float | None = None
    session_id: str | None = None  # council session id


class LedgerPage(_Base):
    items: list[LedgerEntry] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool


class TradeDetail(_Base):
    """Everything needed to explain WHY a trade happened: the trade outcome plus
    the full council session that produced it (snapshot, debate, votes, confidence,
    decision)."""

    trade: LedgerEntry
    session: JournalEntry | None = None


# ---- Performance analytics -------------------------------------------------
class TradeRef(_Base):
    trade_id: str
    symbol: str
    direction: TradeDirection
    return_pct: float
    pnl_usd: float
    session_id: str | None = None


class AgentAccuracy(_Base):
    agent_id: AgentId
    accuracy: float    # % of directional votes that matched the market's move
    correct: int
    total: int


class PerformanceAnalytics(_Base):
    sample_size: int = 0            # number of closed trades
    win_rate: float = 0.0
    avg_return_pct: float = 0.0
    best_trade: TradeRef | None = None
    worst_trade: TradeRef | None = None
    sharpe_ratio: float | None = None      # per-trade, rf=0; None if < 2 trades
    profit_factor: float | None = None     # gross profit / gross loss; None if no losses
    agent_accuracy: list[AgentAccuracy] = Field(default_factory=list)
    veto_success_rate: float | None = None # % of evaluated vetoes that avoided a loss
    veto_count: int = 0
    veto_evaluated: int = 0


# ---- Compliance / trading record -------------------------------------------
class TradeEvent(_Base):
    """One immutable line of the trading record: a fill (open/increase/close)
    with its balance change and any realized PnL."""

    ts: int                        # timestamp (ms epoch)
    event_type: TradeAction
    trade_id: str
    session_id: str | None = None
    symbol: str                    # trading pair
    market: MarketType
    direction: TradeDirection
    price: float                   # fill price
    quantity: float
    cash_delta: float              # balance change (+/-)
    realized_pnl_delta: float = 0.0
    balance_after: float


class ComplianceReport(_Base):
    """Self-contained paper-trading record for hackathon submission."""

    generated_at: int
    portfolio_id: str
    base_currency: str
    starting_balance: float
    equity: float
    cash: float
    realized_pnl: float
    total_pnl: float
    total_return_pct: float
    trades_count: int
    win_rate: float
    records: list[TradeEvent] = Field(default_factory=list)
    note: str

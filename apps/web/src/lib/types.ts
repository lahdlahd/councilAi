// Wire contract — mirrors the backend's Pydantic models (camelCase JSON).
// Kept in one place so the WebSocket decoders and the UI share one source of truth.

export type AgentId = "technical" | "news" | "quant" | "risk" | "execution";
export type Side = "BUY" | "SELL" | "HOLD";
export type Stance = "opening" | "agree" | "disagree" | "challenge" | "neutral";
export type Phase = "idle" | "debating" | "voting" | "decided" | "blocked";
export type ConnectionState = "ok" | "degraded";
export type MarketType = "spot" | "futures";

export interface Macd {
  macd: number;
  signal: number;
  histogram: number;
}
export interface Ema {
  ema12: number;
  ema26: number;
  ema50: number;
}
export interface Indicators {
  rsi: number;
  macd: Macd;
  ema: Ema;
}
export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
export interface MarketSnapshot {
  symbol: string;
  price: number;
  change24h: number;
  high24h: number;
  low24h: number;
  baseVolume: number;
  quoteVolume: number;
  volatility: number;
  indicators: Indicators | null;
  ts: number;
  source: "bitget" | "coingecko";
  market: MarketType;
}

export type SizingMode = "percent" | "fixed";
export type RiskLevel = "conservative" | "moderate" | "aggressive";

export interface TradeConfig {
  sizingMode: SizingMode;
  sizeValue: number;
  riskLevel: RiskLevel;
}

export interface SymbolInfo {
  symbol: string;
  base: string;
  quote: string;
  market: MarketType;
}

export interface AgentProfile {
  id: AgentId;
  name: string;
  specialty: string;
  personality: string;
  avatar: string;
  castsVote: boolean;
}
export interface AgentMessage {
  messageId: string;
  agentId: AgentId;
  text: string;
  stance: Stance;
  references: AgentId[];
  confidence: number;
  ts: number;
}
export interface Vote {
  agentId: AgentId;
  side: Side;
  rationale: string;
}
export interface VetoInfo {
  byAgent: AgentId;
  reason: string;
  riskScore: number;
  factors: string[];
}
export interface ConfidenceBreakdown {
  agreement: number;
  risk: number;
  volatility: number;
  sentiment: number;
}
export interface Recommendation {
  sessionId: string;
  symbol: string;
  side: Side;
  confidence: number;
  summary: string;
  consensusRatio: number;
  consensusReached: boolean;
  vetoed: boolean;
  vetoReason: string | null;
  ts: number;
}

// ---- Trade Journal ---------------------------------------------------------
export interface JournalSummary {
  sessionId: string;
  symbol: string;
  startedAt: number;
  endedAt: number | null;
  side: Side | null;
  confidence: number | null;
  consensusReached: boolean;
  vetoed: boolean;
}
export interface JournalEntry {
  sessionId: string;
  symbol: string;
  startedAt: number;
  endedAt: number | null;
  phase: Phase;
  snapshot: MarketSnapshot;
  messages: AgentMessage[];
  votes: Vote[];
  veto: VetoInfo | null;
  confidence: number | null;
  confidenceBreakdown: ConfidenceBreakdown | null;
  recommendation: Recommendation | null;
}

// ---- Discriminated union of every server event -----------------------------
export type WsEvent =
  | { type: "market.tick"; snapshot: MarketSnapshot }
  | { type: "connection.status"; state: ConnectionState; detail: string | null }
  | {
      type: "session.started";
      sessionId: string;
      symbol: string;
      snapshot: MarketSnapshot;
      startedAt: number;
      agents: AgentProfile[];
    }
  | {
      type: "session.snapshot";
      sessionId: string;
      symbol: string;
      snapshot: MarketSnapshot;
      startedAt: number;
      phase: Phase;
      agents: AgentProfile[];
      messages: AgentMessage[];
      votes: Vote[];
      veto: VetoInfo | null;
      confidence: number | null;
      confidenceBreakdown: ConfidenceBreakdown | null;
      recommendation: Recommendation | null;
    }
  | { type: "council.phase"; phase: Phase }
  | { type: "agent.thinking"; agentId: AgentId }
  | { type: "agent.token"; agentId: AgentId; messageId: string; delta: string }
  | { type: "agent.message"; message: AgentMessage }
  | { type: "debate.reference"; fromAgent: AgentId; toAgents: AgentId[]; stance: Stance }
  | { type: "vote.cast"; vote: Vote }
  | { type: "council.confidence"; score: number; breakdown: ConfidenceBreakdown }
  | { type: "council.veto"; veto: VetoInfo }
  | { type: "council.recommendation"; recommendation: Recommendation }
  | { type: "paper.trade"; trade: PaperTrade };

// ---- Paper trading / ledger ------------------------------------------------
export type TradeDirection = "long" | "short";
export type TradeStatus = "open" | "closed" | "cancelled" | "vetoed";

export interface LedgerEntry {
  tradeId: string;
  openedAt: number;
  symbol: string;
  market: MarketType;
  direction: TradeDirection;
  entryPrice: number;
  quantity: number;
  currentPrice: number;
  pnlPct: number;
  pnlUsd: number;
  status: TradeStatus;
  confidence: number | null;
  sessionId: string | null;
  // Canonical trade schema (shared with PaperTrade).
  id: string;
  asset: string;
  timestamp: number;
  directionSignal: "BUY" | "SELL";
  quantityExecuted: number;
  quantityRequested: number | null;
  riskAdjustedQuantity: number | null;
  confidenceScore: number | null;
  councilReasoning: string | null;
  reasoning: string | null;
  pnlPercent: number;
}

export interface LedgerPage {
  items: LedgerEntry[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
}

export interface TradeDetail {
  trade: LedgerEntry;
  session: JournalEntry | null;
}

export interface PaperTrade {
  id: string;
  sessionId: string | null;
  symbol: string;
  market: MarketType;
  direction: TradeDirection;
  quantity: number;
  entryPrice: number;
  exitPrice: number | null;
  lastMarkPrice: number | null;
  status: TradeStatus;
  confidence: number | null;
  reasoning: string | null;
  fee: number;
  userRequestedSize: number | null;
  riskAdjustedSize: number | null;
  finalExecutedSize: number | null;
  realizedPnl: number;
  // Canonical trade schema (shared with LedgerEntry across journal/replay/portfolio).
  asset: string;
  timestamp: number;
  directionSignal: "BUY" | "SELL";
  quantityRequested: number | null;
  quantityExecuted: number;
  riskAdjustedQuantity: number | null;
  confidenceScore: number | null;
  councilReasoning: string | null;
  pnlUsd: number;
  pnlPercent: number;
  unrealizedPnl: number | null;
  currentValue: number | null;
  pnlPct: number | null;
  openedAt: number;
  closedAt: number | null;
}

export interface PortfolioState {
  portfolioId: string;
  baseCurrency: string;
  startingBalance: number;
  cash: number;
  equity: number;
  realizedPnl: number;
  unrealizedPnl: number;
  totalPnl: number;
  totalReturnPct: number;
  dailyReturnPct: number;
  avgConfidence: number;
  openPositions: PaperTrade[];
  closedPositions: PaperTrade[];
  tradesCount: number;
  wins: number;
  losses: number;
  winRate: number;
}

export interface TradeRef {
  tradeId: string;
  symbol: string;
  direction: TradeDirection;
  returnPct: number;
  pnlUsd: number;
  sessionId: string | null;
}

export interface AgentAccuracy {
  agentId: AgentId;
  accuracy: number;
  correct: number;
  total: number;
}

export interface PerformanceAnalytics {
  sampleSize: number;
  winRate: number;
  avgReturnPct: number;
  bestTrade: TradeRef | null;
  worstTrade: TradeRef | null;
  sharpeRatio: number | null;
  profitFactor: number | null;
  agentAccuracy: AgentAccuracy[];
  vetoSuccessRate: number | null;
  vetoCount: number;
  vetoEvaluated: number;
}

export type TradeAction = "open" | "increase" | "reduce" | "close" | "flip";

export interface TradeEvent {
  ts: number;
  eventType: TradeAction;
  tradeId: string;
  sessionId: string | null;
  symbol: string;
  market: MarketType;
  direction: TradeDirection;
  price: number;
  quantity: number;
  cashDelta: number;
  realizedPnlDelta: number;
  balanceAfter: number;
}

export interface ComplianceReport {
  generatedAt: number;
  portfolioId: string;
  baseCurrency: string;
  startingBalance: number;
  equity: number;
  cash: number;
  realizedPnl: number;
  totalPnl: number;
  totalReturnPct: number;
  tradesCount: number;
  winRate: number;
  records: TradeEvent[];
  note: string;
}

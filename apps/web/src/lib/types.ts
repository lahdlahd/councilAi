// Wire contract — mirrors the backend's Pydantic models (camelCase JSON).
// Kept in one place so the WebSocket decoders and the UI share one source of truth.

export type AgentId = "technical" | "news" | "quant" | "risk" | "execution";
export type Side = "BUY" | "SELL" | "HOLD";
export type Stance = "opening" | "agree" | "disagree" | "challenge" | "neutral";
export type Phase = "idle" | "debating" | "voting" | "decided" | "blocked";
export type ConnectionState = "ok" | "degraded";

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
  | { type: "council.recommendation"; recommendation: Recommendation };

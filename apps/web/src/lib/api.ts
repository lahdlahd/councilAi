import type {
  Candle,
  JournalEntry,
  JournalSummary,
  ComplianceReport,
  LedgerPage,
  PerformanceAnalytics,
  PortfolioState,
  TradeDetail,
  MarketSnapshot,
  MarketType,
  SymbolInfo,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- Market data -----------------------------------------------------------
export async function fetchSymbols(market: MarketType): Promise<SymbolInfo[]> {
  const r = await fetch(`${API_BASE}/symbols?market=${market}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`symbols failed: ${r.status}`);
  return r.json();
}

export async function fetchMarketSnapshot(
  symbol: string,
  market: MarketType
): Promise<MarketSnapshot> {
  const r = await fetch(`${API_BASE}/market?symbol=${symbol}&market=${market}`, {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`market failed: ${r.status}`);
  return r.json();
}

export async function fetchCandles(
  symbol: string,
  market: MarketType,
  limit = 150
): Promise<Candle[]> {
  const r = await fetch(
    `${API_BASE}/market/candles?symbol=${symbol}&market=${market}&limit=${limit}`,
    { cache: "no-store" }
  );
  if (!r.ok) throw new Error(`candles failed: ${r.status}`);
  return r.json();
}

// ---- Council control -------------------------------------------------------
export async function startCouncil(symbol: string, market: MarketType): Promise<void> {
  const r = await fetch(`${API_BASE}/council/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, market }),
  });
  if (!r.ok) throw new Error(`start failed: ${r.status}`);
}

// ---- Trade Journal ---------------------------------------------------------
export async function fetchJournal(limit = 50): Promise<JournalSummary[]> {
  const r = await fetch(`${API_BASE}/journal?limit=${limit}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`journal list failed: ${r.status}`);
  return r.json();
}

export async function fetchJournalEntry(sessionId: string): Promise<JournalEntry> {
  const r = await fetch(`${API_BASE}/journal/${sessionId}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`journal entry failed: ${r.status}`);
  return r.json();
}

// ---- Trade Ledger ----------------------------------------------------------
export async function fetchLedger(limit = 10, offset = 0): Promise<LedgerPage> {
  const r = await fetch(`${API_BASE}/portfolio/ledger?limit=${limit}&offset=${offset}`, {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`ledger failed: ${r.status}`);
  return r.json();
}

export async function fetchTradeDetail(tradeId: string): Promise<TradeDetail> {
  const r = await fetch(`${API_BASE}/portfolio/trades/${tradeId}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`trade detail failed: ${r.status}`);
  return r.json();
}

// ---- Portfolio dashboard ---------------------------------------------------
export async function fetchPortfolio(): Promise<PortfolioState> {
  const r = await fetch(`${API_BASE}/portfolio`, { cache: "no-store" });
  if (!r.ok) throw new Error(`portfolio failed: ${r.status}`);
  return r.json();
}

export async function fetchAnalytics(): Promise<PerformanceAnalytics> {
  const r = await fetch(`${API_BASE}/portfolio/analytics`, { cache: "no-store" });
  if (!r.ok) throw new Error(`analytics failed: ${r.status}`);
  return r.json();
}

// ---- Hackathon compliance --------------------------------------------------
export async function fetchCompliance(): Promise<ComplianceReport> {
  const r = await fetch(`${API_BASE}/portfolio/compliance`, { cache: "no-store" });
  if (!r.ok) throw new Error(`compliance failed: ${r.status}`);
  return r.json();
}

export function complianceCsvUrl(): string {
  return `${API_BASE}/portfolio/compliance.csv`;
}

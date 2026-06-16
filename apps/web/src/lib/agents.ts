import type { AgentId, Side } from "./types";

// Semantic, disciplined accents — no blue/purple. Risk carries the warning red;
// the chairman (execution) wears cream + a gold ring. The two analysts split the
// gold/bronze house colors; quant takes a pale gold so all five stay legible.
export const AGENT_ACCENT: Record<AgentId, string> = {
  technical: "#C9A227", // gold
  news: "#A16B3B", // bronze
  quant: "#CBB57B", // pale gold
  risk: "#A54B4B", // warning red
  execution: "#F4F1EA", // cream (chairman)
};

export const AGENT_ORDER: AgentId[] = ["technical", "news", "quant", "risk", "execution"];

export const SIDE_COLOR: Record<Side, string> = {
  BUY: "#2B8A6E",
  SELL: "#A54B4B",
  HOLD: "#A16B3B",
};

const FALLBACK_PROFILE: Record<
  AgentId,
  { name: string; specialty: string; avatar: string }
> = {
  technical: { name: "Technical Analyst", specialty: "RSI · MACD · EMA · S/R", avatar: "📈" },
  news: { name: "News Analyst", specialty: "sentiment · ETF · macro", avatar: "📰" },
  quant: { name: "Quant Analyst", specialty: "probability · statistics", avatar: "🧮" },
  risk: { name: "Risk Manager", specialty: "drawdown · volatility · exposure", avatar: "🛡️" },
  execution: { name: "Execution Agent", specialty: "synthesis · decision", avatar: "⚖️" },
};
export const profileFor = (id: AgentId) => FALLBACK_PROFILE[id];

// ---- number formatting -----------------------------------------------------
export function fmtPrice(n: number): string {
  if (n >= 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (n >= 1) return n.toFixed(2);
  return n.toFixed(5);
}
export function fmtPct(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}
export function fmtCompact(n: number): string {
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

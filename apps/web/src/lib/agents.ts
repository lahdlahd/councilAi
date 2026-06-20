import type { AgentId, Side, Stance } from "./types";

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
  { name: string; specialty: string; avatar: string; persona: string }
> = {
  technical: {
    name: "Technical Analyst", specialty: "RSI · MACD · EMA · S/R", avatar: "📈",
    persona: "Chart purist — structure over noise, opens the case",
  },
  news: {
    name: "News Analyst", specialty: "sentiment · ETF · macro", avatar: "📰",
    persona: "Momentum chaser — reads the room, trusts the tape",
  },
  quant: {
    name: "Quant Analyst", specialty: "probability · statistics", avatar: "🧮",
    persona: "Cold and mathematical — fades stretched extremes",
  },
  risk: {
    name: "Risk Manager", specialty: "drawdown · volatility · exposure", avatar: "🛡️",
    persona: "Paranoid guardian — holds the veto, protects capital",
  },
  execution: {
    name: "Execution Agent", specialty: "synthesis · decision", avatar: "⚖️",
    persona: "The chairman — weighs the room, calls the verdict",
  },
};
export const profileFor = (id: AgentId) => FALLBACK_PROFILE[id];

// How each debate stance reads on an agent card.
export const STANCE_META: Record<Stance, { label: string; color: string }> = {
  opening: { label: "Opening", color: "#C9A227" },
  agree: { label: "Agrees", color: "#2B8A6E" },
  disagree: { label: "Disagrees", color: "#A16B3B" },
  challenge: { label: "Challenges", color: "#A54B4B" },
  neutral: { label: "Neutral", color: "#8C8579" },
};

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

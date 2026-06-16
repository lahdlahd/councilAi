import type { Candle, JournalEntry, JournalSummary } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export async function fetchCandles(symbol: string, limit = 150): Promise<Candle[]> {
  const r = await fetch(`${API_BASE}/market/${symbol}/candles?limit=${limit}`, {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`candles failed: ${r.status}`);
  return r.json();
}

export async function setCouncilSymbol(symbol: string): Promise<void> {
  await fetch(`${API_BASE}/council/symbol`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
}

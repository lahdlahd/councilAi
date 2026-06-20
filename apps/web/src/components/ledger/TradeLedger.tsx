"use client";

import { ChevronDown, ChevronUp, Play } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchLedger } from "@/lib/api";
import { fmtPrice } from "@/lib/agents";
import type { LedgerEntry, LedgerPage, PaperTrade } from "@/lib/types";
import { useTradeFeed } from "@/stores/tradeFeedStore";

// Map a freshly-executed trade into a ledger row for instant optimistic display.
function toLedgerEntry(t: PaperTrade): LedgerEntry {
  return {
    tradeId: t.id,
    openedAt: t.openedAt,
    symbol: t.symbol,
    market: t.market,
    direction: t.direction,
    entryPrice: t.entryPrice,
    quantity: t.quantity,
    currentPrice: t.lastMarkPrice ?? t.entryPrice,
    pnlPct: t.pnlPct ?? 0,
    pnlUsd: t.unrealizedPnl ?? 0,
    status: t.status,
    confidence: t.confidence,
    sessionId: t.sessionId,
    // Canonical fields (present on the trade payload).
    id: t.id,
    asset: t.asset ?? t.symbol,
    timestamp: t.timestamp ?? t.openedAt,
    directionSignal: t.directionSignal ?? (t.direction === "long" ? "BUY" : "SELL"),
    quantityExecuted: t.quantityExecuted ?? t.quantity,
    quantityRequested: t.quantityRequested ?? null,
    riskAdjustedQuantity: t.riskAdjustedQuantity ?? null,
    confidenceScore: t.confidenceScore ?? t.confidence,
    councilReasoning: t.councilReasoning ?? t.reasoning ?? null,
    reasoning: t.reasoning ?? null,
    pnlPercent: t.pnlPercent ?? t.pnlPct ?? 0,
  };
}

const PAGE_SIZE = 10;
const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";
const GOLD = "#C9A227";

const COLUMNS = [
  "Trade ID", "Time", "Pair", "Direction", "Entry", "Qty",
  "Current", "PnL %", "PnL USD", "Status", "Conf.", "Session",
] as const;

function pnlColor(n: number): string {
  return n > 0 ? POSITIVE : n < 0 ? NEGATIVE : "#8C8579";
}

function fmtTime(ms: number): string {
  if (!ms) return "—";
  const d = new Date(ms);
  return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })} ${d.toLocaleTimeString(
    undefined,
    { hour: "2-digit", minute: "2-digit" }
  )}`;
}

function Row({ e }: { e: LedgerEntry }) {
  const router = useRouter();
  const dirColor = e.direction === "long" ? POSITIVE : NEGATIVE;
  const statusColor = e.status === "open" ? GOLD : "#8C8579";
  return (
    <tr
      onClick={() => router.push(`/trade/${e.tradeId}`)}
      className="cursor-pointer border-t border-hairline/60 hover:bg-surface-2/40"
      title="View trade details"
    >
      <td className="px-3 py-2 font-mono text-[11px] text-muted">
        {e.tradeId.replace("trade-", "").slice(0, 8)}
      </td>
      <td className="px-3 py-2 font-mono text-[11px] text-muted whitespace-nowrap">
        {fmtTime(e.openedAt)}
      </td>
      <td className="px-3 py-2 font-mono text-xs text-text">
        {e.symbol}
        <span className="ml-1 text-[9px] uppercase text-muted/70">{e.market}</span>
      </td>
      <td className="px-3 py-2">
        <span className="font-mono text-[11px] font-semibold uppercase" style={{ color: dirColor }}>
          {e.direction}
        </span>
      </td>
      <td className="px-3 py-2 text-right font-mono text-xs text-text">{fmtPrice(e.entryPrice)}</td>
      <td className="px-3 py-2 text-right font-mono text-xs text-muted">{e.quantity.toFixed(4)}</td>
      <td className="px-3 py-2 text-right font-mono text-xs text-text">{fmtPrice(e.currentPrice)}</td>
      <td className="px-3 py-2 text-right font-mono text-xs font-semibold" style={{ color: pnlColor(e.pnlPct) }}>
        {e.pnlPct > 0 ? "+" : ""}{e.pnlPct.toFixed(2)}%
      </td>
      <td className="px-3 py-2 text-right font-mono text-xs font-semibold" style={{ color: pnlColor(e.pnlUsd) }}>
        {e.pnlUsd > 0 ? "+" : ""}{e.pnlUsd.toFixed(2)}
      </td>
      <td className="px-3 py-2">
        <span
          className="rounded-sm px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide"
          style={{ color: statusColor, background: `${statusColor}1a` }}
        >
          {e.status}
        </span>
      </td>
      <td className="px-3 py-2 text-right font-mono text-[11px] text-muted">
        {e.confidence == null ? "—" : `${Math.round(e.confidence)}%`}
      </td>
      <td className="px-3 py-2 font-mono text-[10px] text-muted/80">
        <span className="inline-flex items-center gap-2">
          {e.sessionId ? e.sessionId.replace("sess-", "") : "—"}
          {e.sessionId && (
            <Link
              href={`/replay/trade/${e.tradeId}`}
              onClick={(ev) => ev.stopPropagation()}
              title="Replay decision"
              className="text-muted transition-colors hover:text-gold"
            >
              <Play size={12} />
            </Link>
          )}
        </span>
      </td>
    </tr>
  );
}

export function TradeLedger() {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<LedgerPage | null>(null);
  const [error, setError] = useState(false);
  const tradeTick = useTradeFeed((s) => s.tick);
  const lastTrade = useTradeFeed((s) => s.lastTrade);
  const offsetRef = useRef(0);
  offsetRef.current = offset;

  const load = useCallback(async (off: number) => {
    try {
      setPage(await fetchLedger(PAGE_SIZE, off));
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  // Always keep the ledger fresh — even collapsed — so the count is accurate.
  // Poll faster while open (live current price / PnL); slower while collapsed.
  useEffect(() => {
    load(offset);
    const id = setInterval(() => load(offset), open ? 3000 : 6000);
    return () => clearInterval(id);
  }, [open, offset, load]);

  // Real-time: a "paper.trade" WS event fired — append the new trade instantly
  // (optimistic, newest-first, deduped) and refetch to reconcile authoritatively.
  useEffect(() => {
    if (!lastTrade || tradeTick === 0) return;
    if (offsetRef.current === 0) {
      const entry = toLedgerEntry(lastTrade);
      setPage((prev) =>
        prev && !prev.items.some((i) => i.tradeId === entry.tradeId)
          ? { ...prev, items: [entry, ...prev.items].slice(0, PAGE_SIZE), total: prev.total + 1 }
          : prev
      );
      load(0);
    } else {
      setOffset(0); // jump to newest page; the poll/load effect fetches it
    }
  }, [tradeTick, lastTrade, load]);

  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = page?.hasMore ?? false;

  return (
    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-hairline bg-surface shadow-[0_-8px_24px_rgba(0,0,0,0.35)]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-2 transition-colors hover:bg-surface-2/40"
      >
        <span className="flex items-center gap-3">
          <span className="eyebrow">Trade Ledger</span>
          <span className="font-mono text-[11px] text-muted">{total} trades</span>
        </span>
        {open ? <ChevronDown size={16} className="text-muted" /> : <ChevronUp size={16} className="text-muted" />}
      </button>

      {open && (
        <div className="border-t border-hairline/60">
          <div className="max-h-[55vh] overflow-auto">
            <table className="w-full border-collapse">
              <thead className="sticky top-0 bg-surface">
                <tr>
                  {COLUMNS.map((c, i) => (
                    <th
                      key={c}
                      className={`px-3 py-2 font-mono text-[10px] uppercase tracking-wide text-muted ${
                        i >= 4 && i <= 8 ? "text-right" : "text-left"
                      }`}
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {page?.items.map((e) => <Row key={e.tradeId} e={e} />)}
              </tbody>
            </table>

            {page && page.items.length === 0 && (
              <div className="px-4 py-10 text-center font-mono text-xs text-muted">
                {error ? "Could not load the ledger." : "No paper trades yet — convene the council to begin."}
              </div>
            )}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between border-t border-hairline px-4 py-2">
            <span className="font-mono text-[11px] text-muted">
              {total === 0 ? "—" : `${start}–${end} of ${total}`}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => canPrev && setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={!canPrev}
                className="border border-hairline px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-text transition-colors enabled:hover:border-[#C9A227] disabled:cursor-not-allowed disabled:text-muted/40"
              >
                Prev
              </button>
              <button
                onClick={() => canNext && setOffset(offset + PAGE_SIZE)}
                disabled={!canNext}
                className="border border-hairline px-3 py-1 font-mono text-[11px] uppercase tracking-wide text-text transition-colors enabled:hover:border-[#C9A227] disabled:cursor-not-allowed disabled:text-muted/40"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

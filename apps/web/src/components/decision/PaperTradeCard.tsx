"use client";

import { useEffect, useState } from "react";
import { fmtCompact, fmtPrice } from "@/lib/agents";
import { fetchPortfolio } from "@/lib/api";
import type { PaperTrade } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";
const GOLD = "#C9A227";
const MUTED = "#8C8579";

function tradeNo(id: string): string {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return String(1000 + (h % 9000));
}

function fmtTime(ts: number): string {
  const ms = ts < 1e12 ? ts * 1000 : ts;
  return new Date(ms).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border border-hairline bg-surface-2/40 px-3 py-2">
      <div className="eyebrow">{label}</div>
      <div className="mt-0.5 font-mono text-sm text-text">{children}</div>
    </div>
  );
}

export function PaperTradeCard() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const phase = useSessionStore((s) => s.phase);
  const rec = useSessionStore((s) => s.recommendation);

  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [equity, setEquity] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetchPortfolio()
        .then((p) => {
          if (!alive) return;
          setTrades([...p.openPositions, ...p.closedPositions]);
          setEquity(p.equity);
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 3500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const deciding = phase === "debating" || phase === "voting";
  const vetoed = rec?.vetoed ?? false;
  const isHold = rec?.side === "HOLD";

  // The trade this session produced, if any.
  const sessionTrade = sessionId ? trades.find((t) => t.sessionId === sessionId) ?? null : null;
  // Fallback: most recent trade overall (proof of execution when idle).
  const latest = trades.length
    ? trades.reduce((a, b) => (b.openedAt > a.openedAt ? b : a))
    : null;
  const trade = sessionTrade ?? (phase === "idle" ? latest : null);

  return (
    <div className="border border-hairline bg-surface shadow-panel">
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <div>
          <div className="eyebrow">Paper Trade</div>
          <h2 className="font-serif text-lg text-text">Execution Record</h2>
        </div>
        {trade && (
          <span
            className="rounded-sm px-2.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wider"
            style={{
              color: trade.status === "open" ? POSITIVE : MUTED,
              background: `${trade.status === "open" ? POSITIVE : MUTED}1f`,
            }}
          >
            {trade.status}
          </span>
        )}
      </div>

      {!trade ? (
        <div className="px-5 py-6 text-center font-mono text-xs text-muted">
          {deciding
            ? "Awaiting execution…"
            : vetoed
              ? "Blocked by Risk Manager — no paper trade executed."
              : isHold
                ? "Council held — no paper trade executed."
                : "No paper trades yet."}
        </div>
      ) : (
        (() => {
          const notional = trade.quantity * trade.entryPrice;
          const bookPct = equity ? (notional / equity) * 100 : null;
          const side = trade.direction === "long" ? "BUY" : "SELL";
          const sideColor = trade.direction === "long" ? POSITIVE : NEGATIVE;
          return (
            <div className="px-5 py-4">
              <div className="flex items-baseline justify-between">
                <span className="font-mono text-xl font-semibold" style={{ color: GOLD }}>
                  Trade #{tradeNo(trade.id)}
                </span>
                <span className="font-mono text-sm text-text">{trade.symbol}</span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <Field label="Direction">
                  <span style={{ color: sideColor }} className="font-semibold">
                    {side} · {trade.direction.toUpperCase()}
                  </span>
                </Field>
                <Field label="Entry Price">{fmtPrice(trade.entryPrice)}</Field>
                <Field label="Position Size">
                  {fmtCompact(notional)} USDT
                  {bookPct != null && <span className="text-muted"> · {bookPct.toFixed(1)}%</span>}
                </Field>
                <Field label="Status">
                  <span style={{ color: trade.status === "open" ? POSITIVE : MUTED }} className="font-semibold uppercase">
                    {trade.status}
                  </span>
                </Field>
              </div>

              <div className="mt-2 flex items-center justify-between border-t border-hairline pt-2 font-mono text-[11px] text-muted">
                <span>Opened {fmtTime(trade.openedAt)}</span>
                <span className="truncate pl-3" title={trade.id}>id {trade.id.slice(0, 8)}…</span>
              </div>

              {trade.finalExecutedSize != null && (
                <div className="mt-3 grid grid-cols-3 gap-1 border-t border-hairline pt-3 text-center">
                  <div>
                    <div className="eyebrow">Requested</div>
                    <div className="mt-0.5 font-mono text-xs text-text">
                      {trade.userRequestedSize != null ? `${fmtCompact(trade.userRequestedSize)}` : "—"}
                    </div>
                  </div>
                  <div>
                    <div className="eyebrow">Risk-adj.</div>
                    <div className="mt-0.5 font-mono text-xs" style={{ color: GOLD }}>
                      {trade.riskAdjustedSize != null ? `${fmtCompact(trade.riskAdjustedSize)}` : "—"}
                    </div>
                  </div>
                  <div>
                    <div className="eyebrow">Executed</div>
                    <div className="mt-0.5 font-mono text-xs font-semibold" style={{ color: POSITIVE }}>
                      {fmtCompact(trade.finalExecutedSize)}
                    </div>
                  </div>
                </div>
              )}

              <p className="mt-3 font-mono text-[11px]" style={{ color: MUTED }}>
                Simulated fill at the live mark — Council executed this decision, not just advised it.
              </p>
            </div>
          );
        })()
      )}
    </div>
  );
}

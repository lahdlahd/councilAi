"use client";

import { ArrowLeft, Play } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AGENT_ACCENT,
  fmtCompact,
  fmtPct,
  fmtPrice,
  profileFor,
  SIDE_COLOR,
  STANCE_META,
} from "@/lib/agents";
import { fetchTradeDetail } from "@/lib/api";
import type { TradeDetail } from "@/lib/types";

const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";
const GOLD = "#C9A227";

function pnlColor(n: number): string {
  return n > 0 ? POSITIVE : n < 0 ? NEGATIVE : "#8C8579";
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-hairline bg-surface">
      <div className="border-b border-hairline px-4 py-2">
        <span className="eyebrow">{title}</span>
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="mt-1 font-mono text-sm" style={{ color: color ?? "#F4F1EA" }}>
        {value}
      </div>
    </div>
  );
}

export default function TradeDetailsPage() {
  const params = useParams<{ tradeId: string }>();
  const tradeId = params?.tradeId;
  const [data, setData] = useState<TradeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tradeId) return;
    let alive = true;
    fetchTradeDetail(tradeId)
      .then((d) => alive && setData(d))
      .catch(() => alive && setError("Could not load this trade."));
    return () => {
      alive = false;
    };
  }, [tradeId]);

  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 py-6">
      <Link
        href="/"
        className="mb-4 inline-flex items-center gap-1.5 font-mono text-xs text-muted transition-colors hover:text-text"
      >
        <ArrowLeft size={14} /> Back to council
      </Link>

      {error && <div className="font-mono text-sm text-negative">{error}</div>}
      {!data && !error && <div className="font-mono text-sm text-muted">Loading trade…</div>}

      {data && <TradeView data={data} />}
    </div>
  );
}

function TradeView({ data }: { data: TradeDetail }) {
  const { trade, session } = data;
  const dirColor = trade.direction === "long" ? POSITIVE : NEGATIVE;
  const isOpen = trade.status === "open";
  const snap = session?.snapshot;
  const rec = session?.recommendation;
  const cb = session?.confidenceBreakdown;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border border-hairline bg-surface px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-baseline gap-3">
            <span className="font-serif text-2xl font-semibold text-text">{trade.symbol}</span>
            <span className="font-mono text-xs font-semibold uppercase" style={{ color: dirColor }}>
              {trade.direction}
            </span>
            <span className="text-[9px] uppercase text-muted">{trade.market}</span>
          </div>
          <span
            className="rounded-sm px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide"
            style={{ color: isOpen ? GOLD : "#8C8579", background: isOpen ? "#C9A2271a" : "#8C85791a" }}
          >
            {trade.status}
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between gap-3">
          <p className="font-mono text-[11px] text-muted">
            Trade {trade.tradeId.replace("trade-", "")} · session {trade.sessionId ?? "—"} ·{" "}
            {trade.openedAt ? new Date(trade.openedAt).toLocaleString() : "—"}
          </p>
          {trade.sessionId && (
            <Link
              href={`/replay/trade/${trade.tradeId}`}
              className="inline-flex shrink-0 items-center gap-1.5 border border-hairline px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-gold hover:text-gold"
            >
              <Play size={12} /> Replay decision
            </Link>
          )}
        </div>
      </div>

      {/* Trade Outcome + PnL */}
      <Section title="Trade Outcome & PnL">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Entry Price" value={fmtPrice(trade.entryPrice)} />
          <Stat label={isOpen ? "Current Price" : "Exit Price"} value={fmtPrice(trade.currentPrice)} />
          <Stat label="Quantity" value={trade.quantity.toFixed(6)} />
          <Stat label="Confidence" value={trade.confidence == null ? "—" : `${Math.round(trade.confidence)}%`} />
          <Stat
            label={isOpen ? "Unrealized PnL" : "Realized PnL"}
            value={`${trade.pnlUsd > 0 ? "+" : ""}${trade.pnlUsd.toFixed(2)} USD`}
            color={pnlColor(trade.pnlUsd)}
          />
          <Stat
            label="PnL %"
            value={`${trade.pnlPct > 0 ? "+" : ""}${trade.pnlPct.toFixed(2)}%`}
            color={pnlColor(trade.pnlPct)}
          />
        </div>
      </Section>

      {!session && (
        <div className="border border-hairline bg-surface px-4 py-6 text-center font-mono text-xs text-muted">
          The full council record for this trade isn&apos;t available
          {trade.sessionId ? "" : " (no linked session)"}. Outcome and PnL are shown above.
        </div>
      )}

      {/* Market Snapshot */}
      {snap && (
        <Section title="Market Snapshot — at the moment of decision">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Price" value={fmtPrice(snap.price)} />
            <Stat label="24h Change" value={fmtPct(snap.change24h)} color={pnlColor(snap.change24h)} />
            <Stat label="24h High" value={fmtPrice(snap.high24h)} />
            <Stat label="24h Low" value={fmtPrice(snap.low24h)} />
            <Stat label="Volume (quote)" value={fmtCompact(snap.quoteVolume)} />
            <Stat label="Volatility" value={fmtPct(snap.volatility * 100)} />
            {snap.indicators && (
              <>
                <Stat label="RSI" value={snap.indicators.rsi.toFixed(1)} />
                <Stat
                  label="MACD"
                  value={snap.indicators.macd.histogram.toFixed(2)}
                  color={pnlColor(snap.indicators.macd.histogram)}
                />
              </>
            )}
          </div>
        </Section>
      )}

      {/* Confidence Score */}
      {session?.confidence != null && (
        <Section title="Confidence Score">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-4xl font-semibold" style={{ color: GOLD }}>
              {Math.round(session.confidence)}
            </span>
            <span className="eyebrow">out of 100</span>
          </div>
          {cb && (
            <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
              {([
                ["Agreement", cb.agreement, 40],
                ["Risk", cb.risk, 30],
                ["Volatility", cb.volatility, 15],
                ["Sentiment", cb.sentiment, 15],
              ] as const).map(([label, val, weight]) => (
                <div key={label}>
                  <div className="flex justify-between">
                    <span className="eyebrow">{label} · {weight}%</span>
                    <span className="font-mono text-[10px] text-muted">{Math.round(val)}</span>
                  </div>
                  <div className="mt-1 h-1.5 bg-surface-2">
                    <div className="h-full" style={{ width: `${Math.max(0, Math.min(100, val))}%`, background: GOLD }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Section>
      )}

      {/* Council Debate */}
      {session && session.messages.length > 0 && (
        <Section title="Council Debate">
          <div className="space-y-3">
            {session.messages.map((m) => {
              const p = profileFor(m.agentId);
              const stance = STANCE_META[m.stance];
              return (
                <div key={m.messageId} className="border-l-2 pl-3" style={{ borderColor: AGENT_ACCENT[m.agentId] }}>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold" style={{ color: AGENT_ACCENT[m.agentId] }}>
                      {p.name}
                    </span>
                    <span className="eyebrow" style={{ color: stance.color }}>{stance.label}</span>
                    {m.references.length > 0 && (
                      <span className="font-mono text-[10px] text-muted">
                        → {m.references.map((r) => profileFor(r).name).join(", ")}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-text/90">{m.text}</p>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Agent Votes */}
      {session && session.votes.length > 0 && (
        <Section title="Agent Votes">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {session.votes.map((v) => (
              <div key={v.agentId} className="flex items-start justify-between border border-hairline/60 px-3 py-2">
                <div>
                  <div className="font-mono text-xs font-semibold text-text">{profileFor(v.agentId).name}</div>
                  {v.rationale && <div className="mt-0.5 text-[11px] text-muted">{v.rationale}</div>}
                </div>
                <span className="font-mono text-sm font-semibold" style={{ color: SIDE_COLOR[v.side] }}>
                  {v.side}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Final Decision */}
      {(rec || session?.veto) && (
        <Section title="Final Decision">
          {session?.veto ? (
            <div>
              <div className="font-serif text-xl font-semibold" style={{ color: NEGATIVE }}>
                VETOED — trade blocked
              </div>
              <p className="mt-1 text-sm text-text/90">{session.veto.reason}</p>
              <p className="mt-1 font-mono text-[11px] text-muted">
                by {profileFor(session.veto.byAgent).name} · risk {Math.round(session.veto.riskScore * 100)}%
              </p>
            </div>
          ) : rec ? (
            <div>
              <div className="flex items-baseline gap-3">
                <span className="font-serif text-2xl font-semibold" style={{ color: SIDE_COLOR[rec.side] }}>
                  {rec.side}
                </span>
                <span className="eyebrow">
                  {rec.consensusReached ? "consensus" : "split"} · {Math.round(rec.consensusRatio * 100)}%
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-text/90">{rec.summary}</p>
            </div>
          ) : null}
        </Section>
      )}
    </div>
  );
}

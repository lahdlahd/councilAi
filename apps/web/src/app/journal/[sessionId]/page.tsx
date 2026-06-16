"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { use } from "react";
import { AgentMessage } from "@/components/chamber/AgentMessage";
import { TopBar } from "@/components/TopBar";
import { fetchJournalEntry } from "@/lib/api";
import { fmtPct, fmtPrice, SIDE_COLOR } from "@/lib/agents";
import type { JournalEntry } from "@/lib/types";

export default function JournalEntryPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  const [entry, setEntry] = useState<JournalEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJournalEntry(sessionId)
      .then(setEntry)
      .catch((e) => setError(String(e)));
  }, [sessionId]);

  const rec = entry?.recommendation;
  const color = rec ? (rec.vetoed ? "#A54B4B" : SIDE_COLOR[rec.side]) : "#8C8579";

  return (
    <div className="flex h-screen flex-col">
      <TopBar showJournalLink={false} />
      <main className="mx-auto w-full max-w-5xl flex-1 overflow-y-auto px-6 py-8">
        <div className="flex items-center justify-between">
          <Link href="/journal" className="eyebrow transition-colors hover:text-gold">
            ← All decisions
          </Link>
          {entry && (
            <Link
              href={`/replay/${sessionId}`}
              className="flex items-center gap-2 border border-gold/50 px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider text-gold transition-colors hover:bg-gold/10"
            >
              ▶ Replay this session
            </Link>
          )}
        </div>

        {error && <p className="mt-4 font-mono text-xs text-negative">Could not load ({error}).</p>}

        {entry && (
          <>
            <div className="mt-3 flex flex-wrap items-baseline justify-between gap-3 border-b border-hairline pb-5">
              <div>
                <div className="eyebrow">Recorded Decision</div>
                <h1 className="font-serif text-2xl text-text">
                  {entry.symbol}
                  <span className="ml-3 font-mono text-base text-muted">
                    {fmtPrice(entry.snapshot.price)}
                  </span>
                  <span
                    className="ml-2 font-mono text-sm"
                    style={{ color: entry.snapshot.change24h >= 0 ? "#2B8A6E" : "#A54B4B" }}
                  >
                    {fmtPct(entry.snapshot.change24h)}
                  </span>
                </h1>
                <p className="mt-1 font-mono text-[11px] text-muted">
                  {new Date(entry.startedAt).toLocaleString()} · {entry.sessionId}
                </p>
              </div>
              <div className="text-right">
                <div className="font-serif text-4xl font-semibold" style={{ color }}>
                  {rec ? (rec.vetoed ? "BLOCKED" : rec.side) : "—"}
                </div>
                {entry.confidence !== null && (
                  <div className="font-mono text-sm text-muted">{Math.round(entry.confidence)}/100</div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-8 py-6 lg:grid-cols-[minmax(0,1fr)_280px]">
              {/* Transcript */}
              <div className="space-y-5">
                <div className="eyebrow">The Debate</div>
                {entry.messages.map((m) => (
                  <AgentMessage key={m.messageId} message={{ ...m, streaming: false }} />
                ))}
              </div>

              {/* Side panel: snapshot, votes, breakdown, veto */}
              <aside className="space-y-4">
                {entry.veto && (
                  <div className="border border-negative/50 bg-surface px-4 py-3">
                    <div className="eyebrow text-negative">Risk Veto</div>
                    <ul className="mt-2 space-y-1">
                      {entry.veto.factors.map((f, i) => (
                        <li key={i} className="flex gap-2 text-[13px] text-text/85">
                          <span className="text-negative">▍</span>
                          {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="border border-hairline bg-surface px-4 py-3">
                  <div className="eyebrow">Votes</div>
                  <div className="mt-2 space-y-1">
                    {entry.votes.map((v) => (
                      <div key={v.agentId} className="flex justify-between text-[13px]">
                        <span className="text-muted">{v.agentId}</span>
                        <span className="font-mono font-semibold" style={{ color: SIDE_COLOR[v.side] }}>
                          {v.side}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {entry.confidenceBreakdown && (
                  <div className="border border-hairline bg-surface px-4 py-3">
                    <div className="eyebrow">Confidence Breakdown</div>
                    <div className="mt-2 space-y-1">
                      {Object.entries(entry.confidenceBreakdown).map(([k, val]) => (
                        <div key={k} className="flex justify-between font-mono text-[12px]">
                          <span className="capitalize text-muted">{k}</span>
                          <span className="text-text/80">{Math.round(val as number)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {entry.snapshot.indicators && (
                  <div className="border border-hairline bg-surface px-4 py-3">
                    <div className="eyebrow">Market Snapshot</div>
                    <div className="mt-2 space-y-1 font-mono text-[12px] text-muted">
                      <div className="flex justify-between"><span>RSI</span><span className="text-text/80">{entry.snapshot.indicators.rsi}</span></div>
                      <div className="flex justify-between"><span>MACD hist</span><span className="text-text/80">{entry.snapshot.indicators.macd.histogram}</span></div>
                      <div className="flex justify-between"><span>volatility</span><span className="text-text/80">{entry.snapshot.volatility}%</span></div>
                    </div>
                  </div>
                )}
              </aside>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

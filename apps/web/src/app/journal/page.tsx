"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { fetchJournal } from "@/lib/api";
import { SIDE_COLOR } from "@/lib/agents";
import type { JournalSummary } from "@/lib/types";

function timeAgo(ms: number): string {
  const d = Date.now() - ms;
  const m = Math.floor(d / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(ms).toLocaleDateString();
}

export default function JournalPage() {
  const [rows, setRows] = useState<JournalSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJournal()
      .then(setRows)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="flex h-screen flex-col">
      <TopBar showJournalLink={false} />
      <main className="mx-auto w-full max-w-4xl flex-1 overflow-y-auto px-6 py-8">
        <div className="mb-6">
          <div className="eyebrow">Trade Journal</div>
          <h1 className="font-serif text-2xl text-text">Past Council Decisions</h1>
          <p className="mt-1 text-sm text-muted">
            Every completed session is recorded — debate, votes, confidence, and verdict.
          </p>
        </div>

        {error && (
          <p className="font-mono text-xs text-negative">
            Could not load the journal ({error}). Is the backend running with Supabase configured?
          </p>
        )}

        {rows && rows.length === 0 && !error && (
          <p className="font-mono text-xs text-muted">
            No decisions recorded yet. Let a session or two complete on the live floor.
          </p>
        )}

        <div className="divide-y divide-hairline border border-hairline">
          {rows?.map((r) => (
            <Link
              key={r.sessionId}
              href={`/journal/${r.sessionId}`}
              className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-4 py-3 transition-colors hover:bg-surface"
            >
              <div className="flex items-center gap-3">
                <span className="font-semibold text-text">{r.symbol}</span>
                <span className="font-mono text-[11px] text-muted">{r.sessionId}</span>
              </div>
              <span className="font-mono text-xs text-muted">{timeAgo(r.startedAt)}</span>
              <span className="font-mono text-xs text-muted">
                {r.confidence !== null ? `${Math.round(r.confidence)}/100` : "—"}
              </span>
              <span
                className="w-20 text-right font-mono text-sm font-semibold"
                style={{ color: r.vetoed ? "#A54B4B" : r.side ? SIDE_COLOR[r.side] : "#8C8579" }}
              >
                {r.vetoed ? "BLOCKED" : r.side ?? "—"}
              </span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}

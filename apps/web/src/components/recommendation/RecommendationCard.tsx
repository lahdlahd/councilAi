"use client";

import { SIDE_COLOR } from "@/lib/agents";
import { useSessionStore } from "@/stores/sessionStore";

export function RecommendationCard() {
  const rec = useSessionStore((s) => s.recommendation);

  if (!rec) {
    return (
      <div className="border border-hairline bg-surface px-4 py-4">
        <span className="eyebrow">Recommendation</span>
        <p className="mt-2 font-mono text-xs text-muted">Awaiting the committee’s verdict…</p>
      </div>
    );
  }

  const color = rec.vetoed ? "#A54B4B" : SIDE_COLOR[rec.side];
  return (
    <div className="border bg-surface px-4 py-4" style={{ borderColor: `${color}55` }}>
      <span className="eyebrow">Recommendation</span>
      <div className="mt-2 flex items-baseline gap-3">
        <span className="font-serif text-4xl font-semibold" style={{ color }}>
          {rec.vetoed ? "BLOCKED" : rec.side}
        </span>
        <span className="font-mono text-sm text-muted">{rec.confidence}/100</span>
      </div>
      {!rec.vetoed && (
        <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted">
          {rec.consensusReached ? "consensus" : "majority"} · {Math.round(rec.consensusRatio * 100)}%
          of votes
        </div>
      )}
      <p className="mt-2 text-[13px] leading-relaxed text-text/80">
        {rec.vetoed ? rec.vetoReason : rec.summary}
      </p>
    </div>
  );
}

"use client";

import { useSessionStore } from "@/stores/sessionStore";

// Mirrors backend compute_confidence: weighted sum, then x0.4 on an active veto.
const WEIGHTS = {
  agreement: 0.4,
  risk: 0.3,
  volatility: 0.15,
  sentiment: 0.15,
} as const;

const GOLD = "#C9A227";
const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";
const MUTED = "#8C8579";

type Row = { label: string; hint: string; pts: number; max: number; value: number };

export function ExplainableConfidence() {
  const breakdown = useSessionStore((s) => s.breakdown);
  const confidence = useSessionStore((s) => s.confidence);
  const rec = useSessionStore((s) => s.recommendation);
  const vetoed = rec?.vetoed ?? false;

  const rows: Row[] = breakdown
    ? [
        { label: "Vote Agreement", hint: "how aligned the committee voted", pts: WEIGHTS.agreement * breakdown.agreement, max: WEIGHTS.agreement * 100, value: breakdown.agreement },
        { label: "Risk-Adjusted Safety", hint: "lower assessed risk earns more", pts: WEIGHTS.risk * breakdown.risk, max: WEIGHTS.risk * 100, value: breakdown.risk },
        { label: "Market Calm", hint: "lower volatility earns more", pts: WEIGHTS.volatility * breakdown.volatility, max: WEIGHTS.volatility * 100, value: breakdown.volatility },
        { label: "Sentiment Conviction", hint: "strength of directional sentiment", pts: WEIGHTS.sentiment * breakdown.sentiment, max: WEIGHTS.sentiment * 100, value: breakdown.sentiment },
      ]
    : [];

  const subtotal = rows.reduce((s, r) => s + r.pts, 0);
  const vetoPenalty = vetoed ? -(subtotal * 0.6) : 0;
  const final = confidence;

  return (
    <div className="border border-hairline bg-surface shadow-panel">
      <div className="flex items-baseline justify-between border-b border-hairline px-5 py-3">
        <div>
          <div className="eyebrow">Explainable Confidence</div>
          <div className="font-mono text-[10px] text-muted">why the score landed here</div>
        </div>
        <div className="font-mono text-3xl font-semibold tabular-nums" style={{ color: final == null ? MUTED : GOLD }}>
          {final == null ? "—" : Math.round(final)}
          <span className="ml-0.5 text-sm text-muted">/100</span>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="px-5 py-6 text-center font-mono text-[11px] text-muted">Awaiting committee inputs…</div>
      ) : (
        <div className="px-5 py-4">
          <div className="space-y-3">
            {rows.map((r) => (
              <div key={r.label}>
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-xs text-text">{r.label}</span>
                  <span className="font-mono text-sm font-semibold tabular-nums" style={{ color: POSITIVE }}>
                    +{r.pts.toFixed(0)}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <div className="h-1.5 flex-1 bg-surface-2">
                    <div className="h-full transition-[width] duration-500" style={{ width: `${r.value}%`, background: GOLD }} />
                  </div>
                  <span className="w-12 text-right font-mono text-[10px] text-muted">of {r.max.toFixed(0)}</span>
                </div>
                <div className="mt-0.5 font-mono text-[10px] text-muted">{r.hint}</div>
              </div>
            ))}
          </div>

          {/* Reconciliation */}
          <div className="mt-4 space-y-1.5 border-t border-hairline pt-3 font-mono text-xs">
            <div className="flex justify-between text-muted">
              <span>Subtotal</span>
              <span className="tabular-nums text-text">{subtotal.toFixed(0)}</span>
            </div>
            {vetoed && (
              <div className="flex justify-between" style={{ color: NEGATIVE }}>
                <span>Risk Manager veto (×0.4)</span>
                <span className="tabular-nums">{vetoPenalty.toFixed(0)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-hairline pt-1.5 text-sm font-semibold">
              <span className="text-text">Confidence</span>
              <span className="tabular-nums" style={{ color: GOLD }}>{final == null ? "—" : Math.round(final)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

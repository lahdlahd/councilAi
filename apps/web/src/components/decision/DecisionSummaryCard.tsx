"use client";

import { Ban, CheckCircle2, Loader2, MinusCircle } from "lucide-react";
import { SIDE_COLOR } from "@/lib/agents";
import type { Side } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

const SIDES: Side[] = ["BUY", "HOLD", "SELL"];
const POSITIVE = "#2B8A6E";
const GOLD = "#C9A227";
const NEGATIVE = "#A54B4B";
const MUTED = "#8C8579";

export function DecisionSummaryCard() {
  const phase = useSessionStore((s) => s.phase);
  const rec = useSessionStore((s) => s.recommendation);
  const liveConfidence = useSessionStore((s) => s.confidence);
  const votes = useSessionStore((s) => s.votes);

  const counts: Record<Side, number> = { BUY: 0, HOLD: 0, SELL: 0 };
  votes.forEach((v) => {
    counts[v.side] += 1;
  });

  const deciding = phase === "debating" || phase === "voting";
  const vetoed = rec?.vetoed ?? false;
  const side = rec?.side ?? null;
  const confidence = rec?.confidence ?? liveConfidence;

  const headline = vetoed ? "BLOCKED" : side ?? (deciding ? "DELIBERATING" : "—");
  const headColor = vetoed ? NEGATIVE : side ? SIDE_COLOR[side] : deciding ? GOLD : MUTED;

  // Paper trade status mirrors the engine: BUY/SELL (not vetoed) -> trade; HOLD/veto -> none.
  const trade = (() => {
    if (vetoed) return { label: "Blocked — No Paper Trade", color: NEGATIVE, Icon: Ban };
    if (!rec || deciding) return { label: "Awaiting decision", color: MUTED, Icon: Loader2 };
    if (side === "HOLD") return { label: "No Trade — Council Holds", color: MUTED, Icon: MinusCircle };
    return { label: "Paper Trade Created", color: POSITIVE, Icon: CheckCircle2 };
  })();

  return (
    <div className="relative overflow-hidden border bg-surface shadow-panel" style={{ borderColor: `${headColor}66` }}>
      <div className="absolute left-0 top-0 h-full w-1.5" style={{ background: headColor }} />

      <div className="px-7 py-6">
        <div className="eyebrow">Council Decision</div>

        {/* Recommendation + confidence */}
        <div className="mt-3 flex flex-wrap items-center gap-x-12 gap-y-4">
          <div>
            <div
              className={`font-serif ${headline.length <= 4 ? "text-7xl" : "text-4xl"} font-bold leading-none tracking-tight ${deciding && !side ? "animate-pulse-soft" : ""}`}
              style={{ color: headColor }}
            >
              {headline}
            </div>
          </div>

          {!vetoed && (
            <div>
              <div className="eyebrow">Confidence</div>
              <div className="mt-1 flex items-baseline gap-1 font-mono font-semibold tabular-nums" style={{ color: confidence == null ? MUTED : GOLD }}>
                <span className="text-6xl leading-none">{confidence == null ? "—" : Math.round(confidence)}</span>
                <span className="text-2xl text-muted">%</span>
              </div>
              {confidence != null && (
                <div className="mt-2 h-1.5 w-44 bg-surface-2">
                  <div className="h-full transition-[width] duration-500" style={{ width: `${confidence}%`, background: GOLD }} />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Vote breakdown + reasoning */}
        <div className="mt-6 grid grid-cols-1 gap-6 border-t border-hairline pt-5 md:grid-cols-[auto_minmax(0,1fr)]">
          <div>
            <div className="eyebrow">Vote Breakdown</div>
            <div className="mt-2 flex gap-5">
              {SIDES.map((s) => (
                <div key={s} className="text-center">
                  <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: SIDE_COLOR[s] }}>
                    {counts[s]}
                  </div>
                  <div className="font-mono text-[10px] uppercase tracking-wide" style={{ color: SIDE_COLOR[s] }}>
                    {s}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="eyebrow">Reasoning Summary</div>
            <p className="mt-2 text-sm leading-relaxed text-text/85">
              {rec?.summary ?? (deciding ? "The committee is still deliberating…" : "No session in progress.")}
            </p>
          </div>
        </div>

        {/* Paper trade status */}
        <div
          className="mt-6 flex items-center gap-2.5 border px-4 py-3"
          style={{ borderColor: `${trade.color}55`, background: `${trade.color}12` }}
        >
          <trade.Icon size={18} className={trade.Icon === Loader2 ? "animate-spin" : ""} style={{ color: trade.color }} />
          <span className="eyebrow" style={{ color: MUTED }}>Paper Trade Status</span>
          <span className="ml-auto font-mono text-sm font-semibold" style={{ color: trade.color }}>
            {trade.label}
          </span>
        </div>
      </div>
    </div>
  );
}

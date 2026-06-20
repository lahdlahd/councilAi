"use client";

import { useEffect, useState } from "react";
import { fmtCompact, profileFor } from "@/lib/agents";
import { fetchPortfolio } from "@/lib/api";
import { useSessionStore } from "@/stores/sessionStore";

// Mirrors the paper engine's sizing: notional = equity x 10% x (confidence/100).
const POSITION_FRACTION = 0.1;
const EXPOSURE_CAP = 0.15; // for the bar scale

const POSITIVE = "#2B8A6E";
const GOLD = "#C9A227";
const NEGATIVE = "#A54B4B";
const MUTED = "#8C8579";

type Status = "APPROVED" | "WARNING" | "BLOCKED" | "REVIEWING";

const STATUS_COLOR: Record<Status, string> = {
  APPROVED: POSITIVE,
  WARNING: GOLD,
  BLOCKED: NEGATIVE,
  REVIEWING: MUTED,
};

function Metric({
  label,
  value,
  display,
  scale,
  color,
}: {
  label: string;
  value: number | null;
  display: string;
  scale?: number; // 0..1 fill; if omitted, no bar
  color: string;
}) {
  return (
    <div className="border border-hairline bg-surface-2/40 px-3 py-2.5">
      <div className="eyebrow">{label}</div>
      <div className="mt-1 font-mono text-lg font-semibold tabular-nums" style={{ color: value == null ? MUTED : color }}>
        {display}
      </div>
      {scale != null && (
        <div className="mt-1.5 h-1 bg-surface-2">
          <div className="h-full transition-[width] duration-500" style={{ width: `${Math.min(scale, 1) * 100}%`, background: color }} />
        </div>
      )}
    </div>
  );
}

export function RiskReviewCard() {
  const phase = useSessionStore((s) => s.phase);
  const breakdown = useSessionStore((s) => s.breakdown);
  const confidence = useSessionStore((s) => s.confidence);
  const rec = useSessionStore((s) => s.recommendation);

  const [equity, setEquity] = useState<number | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => fetchPortfolio().then((p) => alive && setEquity(p.equity)).catch(() => {});
    load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const risk = breakdown?.risk ?? null;
  const volatility = breakdown?.volatility ?? null;
  const vetoed = rec?.vetoed ?? false;
  const side = rec?.side ?? null;
  const deciding = phase === "debating" || phase === "voting";

  // Proposed position for this decision.
  const takesPosition = !!side && side !== "HOLD" && !vetoed;
  const exposureFrac = takesPosition && confidence != null ? POSITION_FRACTION * (confidence / 100) : 0;
  const positionSize = equity != null ? equity * exposureFrac : null;

  let status: Status;
  if (vetoed) status = "BLOCKED";
  else if (!rec || deciding) status = "REVIEWING";
  else if ((risk ?? 0) >= 60 || (volatility ?? 0) >= 70) status = "WARNING";
  else status = "APPROVED";

  const sColor = STATUS_COLOR[status];
  const riskColor = (risk ?? 0) >= 60 ? NEGATIVE : (risk ?? 0) >= 35 ? GOLD : POSITIVE;
  const volColor = (volatility ?? 0) >= 70 ? NEGATIVE : (volatility ?? 0) >= 45 ? GOLD : POSITIVE;

  return (
    <div className="relative overflow-hidden border bg-surface shadow-panel" style={{ borderColor: vetoed ? NEGATIVE : "#2A2F35" }}>
      <div className="absolute left-0 top-0 h-full w-1" style={{ background: NEGATIVE }} />

      {/* Header — the Risk Manager, speaking with authority */}
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <div className="flex items-center gap-2.5">
          <span className="text-xl">{profileFor("risk").avatar}</span>
          <div>
            <div className="eyebrow">Risk Review</div>
            <div className="font-mono text-xs" style={{ color: NEGATIVE }}>Risk Manager</div>
          </div>
        </div>
        <span
          className="rounded-sm px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider"
          style={{ color: sColor, background: `${sColor}1f`, border: `1px solid ${sColor}55` }}
        >
          {status}
        </span>
      </div>

      {/* Veto headline */}
      {vetoed && (
        <div className="border-b border-hairline px-5 py-4 text-center" style={{ background: `${NEGATIVE}12` }}>
          <div className="font-serif text-xl font-bold tracking-tight" style={{ color: NEGATIVE }}>
            COUNCIL DECISION BLOCKED
          </div>
          {rec?.vetoReason && <p className="mt-1.5 font-mono text-[11px] text-text/80">{rec.vetoReason}</p>}
        </div>
      )}

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-2 p-4">
        <Metric label="Risk Score" value={risk} display={risk == null ? "—" : Math.round(risk).toString()} scale={risk == null ? undefined : risk / 100} color={riskColor} />
        <Metric label="Volatility" value={volatility} display={volatility == null ? "—" : Math.round(volatility).toString()} scale={volatility == null ? undefined : volatility / 100} color={volColor} />
        <Metric
          label="Exposure"
          value={takesPosition ? exposureFrac * 100 : null}
          display={takesPosition ? `${(exposureFrac * 100).toFixed(1)}%` : vetoed ? "0%" : "—"}
          scale={takesPosition ? exposureFrac / EXPOSURE_CAP : undefined}
          color={vetoed ? NEGATIVE : GOLD}
        />
        <Metric
          label="Position Size"
          value={positionSize != null && takesPosition ? positionSize : null}
          display={vetoed ? "0 USDT" : positionSize != null && takesPosition ? `${fmtCompact(positionSize)} USDT` : "—"}
          color={vetoed ? NEGATIVE : GOLD}
        />
      </div>
    </div>
  );
}

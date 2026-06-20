"use client";

import { animate, useMotionValue } from "framer-motion";
import { useEffect, useState } from "react";
import { useSessionStore } from "@/stores/sessionStore";

const SIZE = 216;
const STROKE = 16;
const R = (SIZE - STROKE) / 2;
const CX = SIZE / 2;
const CY = SIZE / 2;
const SWEEP = 270; // 270° instrument-cluster gauge with a gap at the bottom
const START = 135;

function polar(angleDeg: number) {
  const a = ((angleDeg - 90) * Math.PI) / 180;
  return { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) };
}
function arcPath(fromDeg: number, toDeg: number) {
  const start = polar(fromDeg);
  const end = polar(toDeg);
  const large = toDeg - fromDeg > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${R} ${R} 0 ${large} 1 ${end.x} ${end.y}`;
}

// Color band by conviction level.
function band(v: number): string {
  if (v >= 70) return "#2B8A6E"; // strong — green
  if (v >= 40) return "#C9A227"; // moderate — gold
  return "#A16B3B"; // weak — bronze
}

function Driver({ label, weight, value }: { label: string; weight: number; value: number }) {
  const color = band(value);
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="eyebrow">
          {label} <span className="text-muted/60">· {Math.round(weight * 100)}%</span>
        </span>
        <span className="font-mono text-[10px] text-muted">{Math.round(value)}</span>
      </div>
      <div className="mt-1 h-1.5 bg-surface-2">
        <div
          className="h-full transition-[width] duration-700"
          style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }}
        />
      </div>
    </div>
  );
}

export function ConfidenceDial() {
  const confidence = useSessionStore((s) => s.confidence);
  const breakdown = useSessionStore((s) => s.breakdown);
  const vetoed = useSessionStore((s) => s.recommendation?.vetoed ?? false);

  // Count-up that re-runs after every session (when confidence updates).
  const mv = useMotionValue(0);
  const [disp, setDisp] = useState(0);
  useEffect(() => {
    if (confidence === null) {
      mv.set(0);
      setDisp(0);
      return;
    }
    const controls = animate(mv, confidence, {
      duration: 1.1,
      ease: [0.2, 0.7, 0.2, 1],
      onUpdate: (v) => setDisp(v),
    });
    return () => controls.stop();
  }, [confidence, mv]);

  const arcColor = vetoed ? "#A54B4B" : band(disp);
  const trackPath = arcPath(START, START + SWEEP);
  const valuePath = arcPath(START, START + (SWEEP * disp) / 100);

  const label = vetoed
    ? "Decision blocked"
    : confidence === null
      ? "Awaiting vote"
      : disp >= 70
        ? "High conviction"
        : disp >= 40
          ? "Moderate conviction"
          : "Low conviction";

  return (
    <div className="border border-hairline bg-surface px-4 py-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow">Council Confidence</span>
        <span className="eyebrow" style={{ color: arcColor }}>
          {label}
        </span>
      </div>

      <div className="relative mx-auto mt-2" style={{ width: SIZE, height: SIZE * 0.82 }}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="overflow-visible">
          <path d={trackPath} fill="none" stroke="#2A2F35" strokeWidth={STROKE} strokeLinecap="round" />
          <path d={valuePath} fill="none" stroke={arcColor} strokeWidth={STROKE} strokeLinecap="round" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono text-6xl font-semibold tabular-nums leading-none"
            style={{ color: confidence === null ? "#8C8579" : arcColor }}
          >
            {confidence === null ? "—" : Math.round(disp)}
          </span>
          <span className="eyebrow mt-2">{vetoed ? "overridden" : "out of 100"}</span>
        </div>
      </div>

      {/* The four drivers of the engine, with their weights. */}
      {breakdown && (
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5">
          <Driver label="Agreement" weight={0.4} value={breakdown.agreement} />
          <Driver label="Risk" weight={0.3} value={breakdown.risk} />
          <Driver label="Volatility" weight={0.15} value={breakdown.volatility} />
          <Driver label="Sentiment" weight={0.15} value={breakdown.sentiment} />
        </div>
      )}
    </div>
  );
}

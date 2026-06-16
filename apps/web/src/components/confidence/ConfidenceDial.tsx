"use client";

import { useSessionStore } from "@/stores/sessionStore";

const SIZE = 200;
const STROKE = 14;
const R = (SIZE - STROKE) / 2;
const CX = SIZE / 2;
const CY = SIZE / 2;
// 270° sweep gauge (gap at the bottom), like an instrument cluster.
const SWEEP = 270;
const START = 135; // degrees, measured clockwise from 3 o'clock baseline

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

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between">
        <span className="eyebrow">{label}</span>
        <span className="font-mono text-[10px] text-muted">{Math.round(value)}</span>
      </div>
      <div className="mt-1 h-1 bg-surface-2">
        <div className="h-full bg-gold/70" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}

export function ConfidenceDial() {
  const confidence = useSessionStore((s) => s.confidence);
  const breakdown = useSessionStore((s) => s.breakdown);
  const vetoed = useSessionStore((s) => s.recommendation?.vetoed ?? false);

  const value = confidence ?? 0;
  const trackPath = arcPath(START, START + SWEEP);
  const valuePath = arcPath(START, START + (SWEEP * value) / 100);
  const arcColor = vetoed ? "#A54B4B" : "#C9A227";

  return (
    <div className="border border-hairline bg-surface px-4 py-4">
      <span className="eyebrow">Council Confidence</span>

      <div className="relative mx-auto mt-2" style={{ width: SIZE, height: SIZE * 0.82 }}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="overflow-visible">
          <path d={trackPath} fill="none" stroke="#2A2F35" strokeWidth={STROKE} strokeLinecap="round" />
          <path
            d={valuePath}
            fill="none"
            stroke={arcColor}
            strokeWidth={STROKE}
            strokeLinecap="round"
            style={{ transition: "all 0.8s cubic-bezier(0.2,0.7,0.2,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-5xl font-semibold tabular-nums text-text">
            {confidence === null ? "—" : Math.round(value)}
          </span>
          <span className="eyebrow mt-1">{vetoed ? "blocked" : "out of 100"}</span>
        </div>
      </div>

      {breakdown && (
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
          <Bar label="Agreement" value={breakdown.agreement} />
          <Bar label="Risk" value={breakdown.risk} />
          <Bar label="Volatility" value={breakdown.volatility} />
          <Bar label="Sentiment" value={breakdown.sentiment} />
        </div>
      )}
    </div>
  );
}

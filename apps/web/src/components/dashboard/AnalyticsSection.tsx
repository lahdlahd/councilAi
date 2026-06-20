"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AGENT_ACCENT, profileFor } from "@/lib/agents";
import { fetchAnalytics } from "@/lib/api";
import type { AgentAccuracy, PerformanceAnalytics, TradeRef } from "@/lib/types";

const GOLD = "#C9A227";
const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";

function pnlColor(n: number): string {
  return n > 0 ? POSITIVE : n < 0 ? NEGATIVE : "#8C8579";
}
function signed(n: number, d = 2): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(d)}`;
}

function Card({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="border border-hairline bg-surface px-4 py-3">
      <div className="eyebrow">{label}</div>
      <div className="mt-1.5 font-mono text-xl font-semibold tabular-nums" style={{ color: color ?? "#F4F1EA" }}>
        {value}
      </div>
      {sub && <div className="mt-0.5 font-mono text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

function TradeCard({ label, t }: { label: string; t: TradeRef | null }) {
  const router = useRouter();
  if (!t) return <Card label={label} value="—" />;
  return (
    <button
      onClick={() => router.push(`/trade/${t.tradeId}`)}
      className="border border-hairline bg-surface px-4 py-3 text-left transition-colors hover:border-[#C9A227]"
    >
      <div className="eyebrow">{label}</div>
      <div className="mt-1.5 font-mono text-xl font-semibold tabular-nums" style={{ color: pnlColor(t.returnPct) }}>
        {signed(t.returnPct)}%
      </div>
      <div className="mt-0.5 font-mono text-[11px] text-muted">
        {t.symbol} · {signed(t.pnlUsd)} USDT
      </div>
    </button>
  );
}

export function AnalyticsSection() {
  const [a, setA] = useState<PerformanceAnalytics | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => fetchAnalytics().then((d) => alive && setA(d)).catch(() => {});
    load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!a) return null;

  const profitFactor =
    a.profitFactor != null
      ? a.profitFactor.toFixed(2)
      : a.sampleSize > 0 && a.winRate > 0
        ? "∞"
        : "—";
  const sharpe = a.sharpeRatio != null ? a.sharpeRatio.toFixed(2) : "—";

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-lg font-semibold text-text">Performance Analytics</h2>
        <span className="font-mono text-[11px] text-muted">{a.sampleSize} closed trades</span>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        <Card label="Win Rate" value={`${a.winRate.toFixed(1)}%`} color={GOLD} />
        <Card
          label="Avg Return"
          value={`${signed(a.avgReturnPct)}%`}
          color={pnlColor(a.avgReturnPct)}
        />
        <Card label="Sharpe Ratio" value={sharpe} />
        <Card label="Profit Factor" value={profitFactor} />
        <TradeCard label="Best Trade" t={a.bestTrade} />
        <TradeCard label="Worst Trade" t={a.worstTrade} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Agent accuracy */}
        <div className="border border-hairline bg-surface px-4 py-3 lg:col-span-2">
          <span className="eyebrow">Agent Accuracy</span>
          <div className="mt-3 space-y-2.5">
            {a.agentAccuracy.map((ag: AgentAccuracy) => (
              <div key={ag.agentId}>
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-xs" style={{ color: AGENT_ACCENT[ag.agentId] }}>
                    {profileFor(ag.agentId).name}
                  </span>
                  <span className="font-mono text-[11px] text-muted">
                    {ag.total === 0 ? "no calls yet" : `${ag.accuracy.toFixed(0)}% · ${ag.correct}/${ag.total}`}
                  </span>
                </div>
                <div className="mt-1 h-1.5 bg-surface-2">
                  <div
                    className="h-full transition-[width] duration-500"
                    style={{ width: `${ag.accuracy}%`, background: AGENT_ACCENT[ag.agentId] }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk manager veto success */}
        <div className="border border-hairline bg-surface px-4 py-3">
          <span className="eyebrow">Risk Manager Veto Success</span>
          <div className="mt-2 font-mono text-4xl font-semibold" style={{ color: a.vetoSuccessRate != null ? GOLD : "#8C8579" }}>
            {a.vetoSuccessRate != null ? `${a.vetoSuccessRate.toFixed(0)}%` : "—"}
          </div>
          <div className="mt-1 font-mono text-[11px] text-muted">
            {a.vetoCount === 0
              ? "no vetoes yet"
              : `${a.vetoEvaluated} of ${a.vetoCount} veto${a.vetoCount === 1 ? "" : "es"} evaluated`}
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted">
            Share of blocked trades that would have lost money had they been taken.
          </p>
        </div>
      </div>
    </div>
  );
}

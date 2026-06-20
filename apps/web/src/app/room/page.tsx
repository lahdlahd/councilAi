"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CouncilChamber } from "@/components/chamber/CouncilChamber";
import { ConfidenceDial } from "@/components/confidence/ConfidenceDial";
import { ConveneControls } from "@/components/convene/ConveneControls";
import { SessionTimeline } from "@/components/session/SessionTimeline";
import { VetoOverlay } from "@/components/veto/VetoOverlay";
import { useCouncilStream } from "@/hooks/useStreams";
import { AGENT_ACCENT, fmtPrice, profileFor } from "@/lib/agents";
import { fetchAnalytics, fetchPortfolio } from "@/lib/api";
import type { PaperTrade, PerformanceAnalytics, PortfolioState } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

const GOLD = "#C9A227";
const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";

function color(n: number): string {
  return n > 0 ? POSITIVE : n < 0 ? NEGATIVE : "#8C8579";
}
function signed(n: number, d = 2): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(d)}`;
}
function usd(n: number): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function HeroStat({ label, value, sub, c, big }: { label: string; value: string; sub?: string; c?: string; big?: boolean }) {
  return (
    <div className="px-5 py-3">
      <div className="eyebrow">{label}</div>
      <div
        className={`mt-1 font-mono font-semibold tabular-nums ${big ? "font-serif text-4xl" : "text-2xl"}`}
        style={{ color: c ?? "#F4F1EA" }}
      >
        {value}
      </div>
      {sub && <div className="font-mono text-[11px]" style={{ color: c ?? "#8C8579" }}>{sub}</div>}
    </div>
  );
}

export default function PerformanceRoom() {
  useCouncilStream(); // live debate + confidence
  const router = useRouter();

  const [p, setP] = useState<PortfolioState | null>(null);
  const [a, setA] = useState<PerformanceAnalytics | null>(null);

  const symbol = useSessionStore((s) => s.symbol);
  const phase = useSessionStore((s) => s.phase);

  useEffect(() => {
    let alive = true;
    const loadP = () => fetchPortfolio().then((d) => alive && setP(d)).catch(() => {});
    const loadA = () => fetchAnalytics().then((d) => alive && setA(d)).catch(() => {});
    loadP();
    loadA();
    const idP = setInterval(loadP, 3000);
    const idA = setInterval(loadA, 7000);
    return () => {
      alive = false;
      clearInterval(idP);
      clearInterval(idA);
    };
  }, []);

  const live = phase !== "idle";
  const open = p?.openPositions ?? [];
  const recent = [...(p?.closedPositions ?? [])].reverse().slice(0, 6);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Header — the pitch, at a glance */}
      <header className="flex items-center justify-between border-b border-hairline px-6 py-3">
        <div className="flex items-baseline gap-4">
          <span className="font-serif text-xl font-semibold tracking-wide text-text">COUNCIL</span>
          <span className="hidden font-mono text-[11px] text-muted md:inline">
            Autonomous AI Investment Committee · Live Paper Portfolio · Real Bitget Market Data
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${live ? "animate-pulse-soft" : ""}`}
              style={{ background: live ? POSITIVE : "#8C8579" }}
            />
            <span className="eyebrow" style={{ color: live ? POSITIVE : "#8C8579" }}>
              {live ? `In session · ${symbol ?? ""}` : "Council idle"}
            </span>
          </span>
          <Link href="/" className="eyebrow transition-colors hover:text-gold">← Console</Link>
        </div>
      </header>

      {/* Hero stat strip */}
      <div className="grid grid-cols-2 divide-x divide-hairline border-b border-hairline md:grid-cols-5">
        <HeroStat
          label="Portfolio Value"
          value={p ? usd(p.equity) : "—"}
          sub={p ? `${p.baseCurrency} · started ${usd(p.startingBalance)}` : undefined}
          big
        />
        <HeroStat
          label="Total Return"
          value={p ? `${signed(p.totalReturnPct)}%` : "—"}
          sub={p ? `${signed(p.totalPnl)} ${p.baseCurrency}` : undefined}
          c={p ? color(p.totalPnl) : undefined}
        />
        <HeroStat
          label="Daily Return"
          value={p ? `${signed(p.dailyReturnPct)}%` : "—"}
          c={p ? color(p.dailyReturnPct) : undefined}
        />
        <HeroStat label="Active Trades" value={String(open.length)} sub={p ? `${p.tradesCount} closed` : undefined} c={GOLD} />
        <HeroStat label="Win Rate" value={a ? `${a.winRate.toFixed(0)}%` : "—"} sub={a ? `${a.sampleSize} trades` : undefined} c={GOLD} />
      </div>

      {/* Floor */}
      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {/* Live Debate */}
        <section className="flex min-h-0 flex-col gap-3">
          <SessionTimeline />
          <div className="flex items-center gap-2">
            <span className="eyebrow">Live Debate</span>
            {live && <span className="font-mono text-[11px] text-muted">· {phase}</span>}
          </div>
          <div className="min-h-0 flex-1">
            <CouncilChamber />
          </div>
        </section>

        {/* Right rail */}
        <aside className="flex min-h-0 flex-col gap-4 overflow-y-auto">
          <ConveneControls />
          <ConfidenceDial />

          {/* Open positions — live */}
          <Panel title="Open Positions" count={open.length}>
            {open.length === 0 ? (
              <Empty>No active positions</Empty>
            ) : (
              open.map((t) => <PositionRow key={t.id} t={t} onClick={() => router.push(`/trade/${t.id}`)} />)
            )}
          </Panel>

          {/* Recent decisions */}
          <Panel title="Recent Decisions" count={recent.length}>
            {recent.length === 0 ? (
              <Empty>No decisions yet</Empty>
            ) : (
              recent.map((t) => (
                <button
                  key={t.id}
                  onClick={() => router.push(`/replay/trade/${t.id}`)}
                  className="flex w-full items-center justify-between border-t border-hairline/60 px-1 py-1.5 text-left hover:bg-surface-2/40"
                >
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-xs text-text">{t.symbol}</span>
                    <span
                      className="font-mono text-[10px] font-semibold uppercase"
                      style={{ color: t.direction === "long" ? POSITIVE : NEGATIVE }}
                    >
                      {t.direction}
                    </span>
                  </span>
                  <span className="font-mono text-xs font-semibold" style={{ color: color(t.realizedPnl) }}>
                    {signed(t.realizedPnl)}
                  </span>
                </button>
              ))
            )}
          </Panel>

          {/* Agent accuracy */}
          <Panel title="Agent Accuracy">
            <div className="space-y-2 pt-1">
              {(a?.agentAccuracy ?? []).map((ag) => (
                <div key={ag.agentId}>
                  <div className="flex justify-between">
                    <span className="font-mono text-[11px]" style={{ color: AGENT_ACCENT[ag.agentId] }}>
                      {profileFor(ag.agentId).name}
                    </span>
                    <span className="font-mono text-[10px] text-muted">
                      {ag.total === 0 ? "—" : `${ag.accuracy.toFixed(0)}%`}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 bg-surface-2">
                    <div className="h-full transition-[width] duration-500" style={{ width: `${ag.accuracy}%`, background: AGENT_ACCENT[ag.agentId] }} />
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </aside>
      </main>

      <VetoOverlay />
    </div>
  );
}

function Panel({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <div className="border border-hairline bg-surface px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="eyebrow">{title}</span>
        {count !== undefined && <span className="font-mono text-[11px] text-muted">{count}</span>}
      </div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="py-4 text-center font-mono text-[11px] text-muted">{children}</div>;
}

function PositionRow({ t, onClick }: { t: PaperTrade; onClick: () => void }) {
  const pnl = t.unrealizedPnl ?? 0;
  const pct = t.pnlPct ?? 0;
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-between border-t border-hairline/60 px-1 py-1.5 text-left hover:bg-surface-2/40"
    >
      <span className="flex items-center gap-2">
        <span className="font-mono text-xs text-text">{t.symbol}</span>
        <span className="font-mono text-[10px] font-semibold uppercase" style={{ color: t.direction === "long" ? POSITIVE : NEGATIVE }}>
          {t.direction}
        </span>
        <span className="font-mono text-[10px] text-muted">@ {fmtPrice(t.entryPrice)}</span>
      </span>
      <span className="text-right">
        <span className="font-mono text-xs font-semibold" style={{ color: color(pnl) }}>{signed(pnl)}</span>
        <span className="ml-2 font-mono text-[10px]" style={{ color: color(pct) }}>{signed(pct)}%</span>
      </span>
    </button>
  );
}

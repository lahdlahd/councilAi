"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnalyticsSection } from "@/components/dashboard/AnalyticsSection";
import { TopBar } from "@/components/TopBar";
import { fmtPrice } from "@/lib/agents";
import { fetchPortfolio } from "@/lib/api";
import type { PaperTrade, PortfolioState } from "@/lib/types";

const GOLD = "#C9A227";
const BRONZE = "#A16B3B";
const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";

function usd(n: number): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function signed(n: number, digits = 2): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}`;
}
function pnlColor(n: number): string {
  return n > 0 ? POSITIVE : n < 0 ? NEGATIVE : "#8C8579";
}

function Metric({
  label, value, sub, color, accent,
}: {
  label: string; value: string; sub?: string; color?: string; accent?: string;
}) {
  return (
    <div className="relative overflow-hidden border border-hairline bg-surface px-4 py-3">
      {accent && <div className="absolute left-0 top-0 h-full w-0.5" style={{ background: accent }} />}
      <div className="eyebrow">{label}</div>
      <div className="mt-1.5 font-mono text-2xl font-semibold tabular-nums" style={{ color: color ?? "#F4F1EA" }}>
        {value}
      </div>
      {sub && <div className="mt-0.5 font-mono text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const [p, setP] = useState<PortfolioState | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetchPortfolio()
        .then((d) => alive && (setP(d), setError(false)))
        .catch(() => alive && setError(true));
    load();
    const id = setInterval(load, 3000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-4 flex items-baseline justify-between">
          <h1 className="font-serif text-2xl font-semibold text-text">Portfolio</h1>
          <Link href="/console" className="eyebrow transition-colors hover:text-gold">← Live session</Link>
        </div>

        {error && !p && <div className="font-mono text-sm text-negative">Could not load the portfolio.</div>}
        {!p && !error && <div className="font-mono text-sm text-muted">Loading…</div>}

        {p && <Dashboard p={p} />}
      </main>
    </div>
  );
}

function Dashboard({ p }: { p: PortfolioState }) {
  const winLossTotal = p.wins + p.losses;
  const winShare = winLossTotal ? (p.wins / winLossTotal) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Hero — Total Equity */}
      <div className="relative overflow-hidden border border-hairline bg-surface p-6">
        <div className="absolute left-0 top-0 h-full w-1" style={{ background: GOLD }} />
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="eyebrow">Total Equity</div>
            <div className="mt-1 font-serif text-5xl font-semibold tabular-nums text-text">
              {usd(p.equity)}
              <span className="ml-2 font-mono text-base text-muted">{p.baseCurrency}</span>
            </div>
            <div className="mt-1 font-mono text-[11px] text-muted">
              Started at {usd(p.startingBalance)} {p.baseCurrency} · Cash {usd(p.cash)}
            </div>
          </div>
          <div className="flex gap-3">
            <ReturnBadge label="Total Return" pct={p.totalReturnPct} usdVal={p.totalPnl} />
            <ReturnBadge label="Daily Return" pct={p.dailyReturnPct} />
          </div>
        </div>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <Metric label="Cash Balance" value={usd(p.cash)} sub={p.baseCurrency} accent={BRONZE} />
        <Metric label="Open Positions" value={String(p.openPositions.length)} accent={GOLD} />
        <Metric label="Closed Positions" value={String(p.closedPositions.length)} accent={BRONZE} />
        <Metric
          label="Daily Return"
          value={`${signed(p.dailyReturnPct)}%`}
          color={pnlColor(p.dailyReturnPct)}
          accent={pnlColor(p.dailyReturnPct)}
        />
        <Metric
          label="Total Return"
          value={`${signed(p.totalReturnPct)}%`}
          sub={`${signed(p.totalPnl)} ${p.baseCurrency}`}
          color={pnlColor(p.totalPnl)}
          accent={pnlColor(p.totalPnl)}
        />
        <Metric label="Winning Trades" value={String(p.wins)} color={POSITIVE} accent={POSITIVE} />
        <Metric label="Losing Trades" value={String(p.losses)} color={NEGATIVE} accent={NEGATIVE} />
        <Metric label="Average Confidence" value={`${Math.round(p.avgConfidence)}%`} accent={GOLD} />
      </div>

      {/* Win / loss conviction strip */}
      <div className="border border-hairline bg-surface px-4 py-4">
        <div className="flex items-center justify-between">
          <span className="eyebrow">Win Rate</span>
          <span className="font-mono text-sm font-semibold" style={{ color: GOLD }}>
            {p.winRate.toFixed(1)}% · {p.wins}W / {p.losses}L
          </span>
        </div>
        <div className="mt-2 flex h-2 overflow-hidden rounded-sm bg-surface-2">
          <div style={{ width: `${winShare}%`, background: POSITIVE }} />
          <div style={{ width: `${100 - winShare}%`, background: NEGATIVE }} />
        </div>
      </div>

      {/* Performance analytics */}
      <AnalyticsSection />

      {/* Open positions */}
      <PositionsTable title="Open Positions" rows={p.openPositions} live />
      {p.closedPositions.length > 0 && (
        <PositionsTable title="Closed Positions" rows={[...p.closedPositions].reverse().slice(0, 8)} />
      )}
    </div>
  );
}

function ReturnBadge({ label, pct, usdVal }: { label: string; pct: number; usdVal?: number }) {
  const color = pnlColor(pct);
  return (
    <div className="border border-hairline px-4 py-2 text-right" style={{ borderColor: `${color}55` }}>
      <div className="eyebrow">{label}</div>
      <div className="mt-0.5 font-mono text-xl font-semibold tabular-nums" style={{ color }}>
        {signed(pct)}%
      </div>
      {usdVal !== undefined && (
        <div className="font-mono text-[11px]" style={{ color }}>{signed(usdVal)} USDT</div>
      )}
    </div>
  );
}

function PositionsTable({ title, rows, live }: { title: string; rows: PaperTrade[]; live?: boolean }) {
  const router = useRouter();
  return (
    <div className="border border-hairline bg-surface">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2">
        <span className="eyebrow">{title}</span>
        <span className="font-mono text-[11px] text-muted">{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <div className="px-4 py-8 text-center font-mono text-xs text-muted">
          No {title.toLowerCase()} yet.
        </div>
      ) : (
        <table className="w-full border-collapse">
          <tbody>
            {rows.map((t) => {
              const pnl = live
                ? t.unrealizedPnl ?? 0
                : t.realizedPnl;
              const pct = t.pnlPct ?? 0;
              const dirColor = t.direction === "long" ? POSITIVE : NEGATIVE;
              return (
                <tr
                  key={t.id}
                  onClick={() => router.push(`/trade/${t.id}`)}
                  className="cursor-pointer border-t border-hairline/60 hover:bg-surface-2/40"
                >
                  <td className="px-4 py-2 font-mono text-xs text-text">
                    {t.symbol}
                    <span className="ml-1 text-[9px] uppercase text-muted/70">{t.market}</span>
                  </td>
                  <td className="px-2 py-2">
                    <span className="font-mono text-[11px] font-semibold uppercase" style={{ color: dirColor }}>
                      {t.direction}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-right font-mono text-xs text-muted">{t.quantity.toFixed(4)}</td>
                  <td className="px-2 py-2 text-right font-mono text-xs text-muted">{fmtPrice(t.entryPrice)}</td>
                  <td className="px-2 py-2 text-right font-mono text-xs text-text">
                    {fmtPrice(live ? t.lastMarkPrice ?? t.entryPrice : t.exitPrice ?? t.entryPrice)}
                  </td>
                  <td className="px-2 py-2 text-right font-mono text-xs font-semibold" style={{ color: pnlColor(pnl) }}>
                    {signed(pnl)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-xs font-semibold" style={{ color: pnlColor(pct) }}>
                    {signed(pct)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

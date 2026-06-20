"use client";

import { Check, Copy, Download, FileJson } from "lucide-react";
import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { fmtPrice } from "@/lib/agents";
import { complianceCsvUrl, fetchCompliance } from "@/lib/api";
import type { ComplianceReport, TradeEvent } from "@/lib/types";

const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";
const GOLD = "#C9A227";

function color(n: number): string {
  return n > 0 ? POSITIVE : n < 0 ? NEGATIVE : "#8C8579";
}
function signed(n: number, d = 2): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(d)}`;
}
function fmtTime(ms: number): string {
  return new Date(ms).toISOString().replace("T", " ").slice(0, 19) + "Z";
}

function Summary({ label, value, sub, c }: { label: string; value: string; sub?: string; c?: string }) {
  return (
    <div className="border border-hairline bg-surface px-4 py-3">
      <div className="eyebrow">{label}</div>
      <div className="mt-1 font-mono text-lg font-semibold tabular-nums" style={{ color: c ?? "#F4F1EA" }}>
        {value}
      </div>
      {sub && <div className="font-mono text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

export default function CompliancePage() {
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => fetchCompliance().then((d) => alive && setReport(d)).catch(() => {});
    load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  function exportJson() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "council_paper_trading_log.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function copyUrl() {
    if (typeof window === "undefined") return;
    navigator.clipboard?.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div className="min-h-screen">
      <TopBar showJournalLink={false} />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="eyebrow">Bitget Hackathon · Submission Record</div>
            <h1 className="mt-1 font-serif text-2xl font-semibold text-text">Paper Trading Log</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href={complianceCsvUrl()}
              className="inline-flex items-center gap-1.5 border border-hairline px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-gold hover:text-gold"
            >
              <Download size={13} /> Export CSV
            </a>
            <button
              onClick={exportJson}
              className="inline-flex items-center gap-1.5 border border-hairline px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-gold hover:text-gold"
            >
              <FileJson size={13} /> Export JSON
            </button>
            <button
              onClick={copyUrl}
              className="inline-flex items-center gap-1.5 border border-hairline px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-text transition-colors hover:border-gold hover:text-gold"
            >
              {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copied" : "Public link"}
            </button>
          </div>
        </div>

        {report && (
          <>
            <p className="mt-3 border-l-2 pl-3 text-[12px] leading-relaxed text-muted" style={{ borderColor: GOLD }}>
              {report.note}
            </p>

            {/* Summary */}
            <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
              <Summary label="Starting" value={`${report.startingBalance.toLocaleString()} ${report.baseCurrency}`} />
              <Summary label="Equity" value={report.equity.toLocaleString(undefined, { maximumFractionDigits: 2 })} />
              <Summary
                label="Total PnL"
                value={`${signed(report.totalPnl)}`}
                c={color(report.totalPnl)}
              />
              <Summary label="Return" value={`${signed(report.totalReturnPct)}%`} c={color(report.totalReturnPct)} />
              <Summary label="Closed Trades" value={String(report.tradesCount)} />
              <Summary label="Win Rate" value={`${report.winRate.toFixed(1)}%`} c={GOLD} />
            </div>

            {/* Trading record */}
            <div className="mt-4 border border-hairline bg-surface">
              <div className="flex items-center justify-between border-b border-hairline px-4 py-2">
                <span className="eyebrow">Trading Record</span>
                <span className="font-mono text-[11px] text-muted">{report.records.length} entries</span>
              </div>
              <div className="max-h-[60vh] overflow-auto">
                <table className="w-full border-collapse">
                  <thead className="sticky top-0 bg-surface">
                    <tr>
                      {["Timestamp (UTC)", "Pair", "Event", "Direction", "Price", "Quantity",
                        "Balance Change", "PnL", "Balance After"].map((h, i) => (
                        <th
                          key={h}
                          className={`px-3 py-2 font-mono text-[10px] uppercase tracking-wide text-muted ${
                            i >= 4 ? "text-right" : "text-left"
                          }`}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.records.map((e: TradeEvent, i) => (
                      <tr key={`${e.tradeId}-${i}`} className="border-t border-hairline/60">
                        <td className="px-3 py-1.5 font-mono text-[11px] text-muted whitespace-nowrap">{fmtTime(e.ts)}</td>
                        <td className="px-3 py-1.5 font-mono text-xs text-text">
                          {e.symbol}<span className="ml-1 text-[9px] uppercase text-muted/70">{e.market}</span>
                        </td>
                        <td className="px-3 py-1.5 font-mono text-[10px] uppercase text-muted">{e.eventType}</td>
                        <td className="px-3 py-1.5 font-mono text-[11px] font-semibold uppercase"
                            style={{ color: e.direction === "long" ? POSITIVE : NEGATIVE }}>
                          {e.direction}
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono text-xs text-text">{fmtPrice(e.price)}</td>
                        <td className="px-3 py-1.5 text-right font-mono text-xs text-muted">{e.quantity.toFixed(6)}</td>
                        <td className="px-3 py-1.5 text-right font-mono text-xs" style={{ color: color(e.cashDelta) }}>
                          {signed(e.cashDelta)}
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono text-xs font-semibold" style={{ color: color(e.realizedPnlDelta) }}>
                          {e.realizedPnlDelta === 0 ? "—" : signed(e.realizedPnlDelta)}
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono text-xs text-muted">{e.balanceAfter.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {report.records.length === 0 && (
                  <div className="px-4 py-10 text-center font-mono text-xs text-muted">
                    No paper trades recorded yet — convene the council to generate the log.
                  </div>
                )}
              </div>
            </div>

            <p className="mt-3 font-mono text-[10px] text-muted">
              Generated {fmtTime(report.generatedAt)} · This page and its CSV/JSON exports are publicly shareable.
            </p>
          </>
        )}
      </main>
    </div>
  );
}

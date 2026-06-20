"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ConveneControls } from "@/components/convene/ConveneControls";
import { AGENT_ACCENT, AGENT_ORDER, fmtCompact, fmtPct, fmtPrice, profileFor } from "@/lib/agents";
import { fetchMarketSnapshot } from "@/lib/api";
import type { AgentId, MarketSnapshot } from "@/lib/types";

const GOLD = "#C9A227";
const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";

const OVERVIEW = ["BTCUSDT", "ETHUSDT", "BNBUSDT"];

const ROLES: Record<AgentId, string> = {
  technical: "Reads price structure, trend, and key levels to open the case.",
  news: "Weighs sentiment, ETF flows, and macro to gauge momentum.",
  quant: "Applies probability and statistics, fading stretched extremes.",
  risk: "Guards capital — flags volatility and drawdown, holds the veto.",
  execution: "Chairs the committee, weighs the debate, and calls the verdict.",
};

const STEPS = ["Market Scan", "Debate", "Voting", "Risk Review", "Execution"];

function MarketTile({ symbol }: { symbol: string }) {
  const [s, setS] = useState<MarketSnapshot | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => fetchMarketSnapshot(symbol, "spot").then((d) => alive && setS(d)).catch(() => {});
    load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [symbol]);

  const up = (s?.change24h ?? 0) >= 0;
  return (
    <div className="border border-hairline bg-surface px-5 py-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-semibold text-text">{symbol}</span>
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full animate-pulse-soft" style={{ background: POSITIVE }} />
          <span className="eyebrow">live</span>
        </span>
      </div>
      <div className="mt-3 font-mono text-2xl font-semibold tabular-nums text-text">
        {s ? fmtPrice(s.price) : "—"}
      </div>
      <div className="mt-2 flex items-center justify-between font-mono text-xs">
        <span style={{ color: up ? POSITIVE : NEGATIVE }}>{s ? fmtPct(s.change24h) : "—"}</span>
        <span className="text-muted">Vol {s ? fmtCompact(s.quoteVolume) : "—"}</span>
      </div>
    </div>
  );
}

export default function Landing() {
  const router = useRouter();

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-hairline px-6 py-3">
        <span className="font-serif text-lg font-semibold tracking-wide text-text">COUNCIL</span>
        <nav className="flex items-center gap-5">
          <Link href="/console" className="eyebrow transition-colors hover:text-gold">Console</Link>
          <Link href="/room" className="eyebrow transition-colors hover:text-gold">Performance Room</Link>
          <Link href="/dashboard" className="eyebrow transition-colors hover:text-gold">Portfolio</Link>
          <Link href="/compliance" className="eyebrow transition-colors hover:text-gold">Submission</Link>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-6">
        {/* SECTION 1 — HERO */}
        <section className="border-b border-hairline py-16 text-center">
          <h1 className="font-serif text-6xl font-semibold tracking-tight text-text">Council</h1>
          <p className="mt-2 font-mono text-sm uppercase tracking-[0.2em]" style={{ color: GOLD }}>
            The Autonomous Investment Committee
          </p>
          <p className="mx-auto mt-6 max-w-2xl text-[15px] leading-relaxed text-text/80">
            Council brings together specialized AI agents that analyze live crypto markets, debate
            opportunities, assess risk, and reach transparent investment decisions.
          </p>
          <div className="mx-auto mt-5 flex max-w-md flex-col gap-1 font-mono text-xs text-muted">
            <span>Every decision is visible.</span>
            <span>Every vote is auditable.</span>
            <span>Every trade is explainable.</span>
          </div>
          <div className="mt-8 flex items-center justify-center gap-3">
            <a
              href="#launcher"
              className="border px-6 py-2.5 font-mono text-xs font-semibold uppercase tracking-wide transition-colors"
              style={{ borderColor: GOLD, background: GOLD, color: "#0F1113" }}
            >
              Convene Council
            </a>
            <Link
              href="/dashboard"
              className="border border-hairline px-6 py-2.5 font-mono text-xs font-semibold uppercase tracking-wide text-text transition-colors hover:border-gold hover:text-gold"
            >
              View Performance
            </Link>
          </div>
        </section>

        {/* SECTION 2 — LIVE MARKET OVERVIEW */}
        <section className="border-b border-hairline py-12">
          <SectionHead n="01" title="Live Market Overview" sub="Real-time data from Bitget" />
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {OVERVIEW.map((sym) => <MarketTile key={sym} symbol={sym} />)}
          </div>
        </section>

        {/* SECTION 3 — MEET THE COMMITTEE */}
        <section className="border-b border-hairline py-12">
          <SectionHead n="02" title="Meet the Committee" sub="Five specialized agents, one transparent process" />
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {AGENT_ORDER.map((id) => {
              const p = profileFor(id);
              return (
                <div key={id} className="border border-hairline bg-surface px-5 py-4">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{p.avatar}</span>
                    <div>
                      <div className="font-mono text-sm font-semibold" style={{ color: AGENT_ACCENT[id] }}>
                        {p.name}
                      </div>
                      <div className="eyebrow">{p.specialty}</div>
                    </div>
                  </div>
                  <p className="mt-3 text-[13px] leading-relaxed text-text/80">{ROLES[id]}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* SECTION 4 — HOW COUNCIL WORKS */}
        <section className="border-b border-hairline py-12">
          <SectionHead n="03" title="How Council Works" sub="Every session follows the same transparent path" />
          <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
            {STEPS.map((step, i) => (
              <div key={step} className="flex items-center gap-2">
                <div className="flex flex-col items-center gap-2">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-full border font-mono text-sm font-semibold"
                    style={{ borderColor: GOLD, color: GOLD }}
                  >
                    {i + 1}
                  </div>
                  <span className="font-mono text-[11px] uppercase tracking-wide text-text">{step}</span>
                </div>
                {i < STEPS.length - 1 && <ArrowRight size={16} className="mb-5 text-muted" />}
              </div>
            ))}
          </div>
        </section>

        {/* SECTION 5 — SESSION LAUNCHER */}
        <section id="launcher" className="py-12">
          <SectionHead n="04" title="Convene a Session" sub="Choose an asset and market, then launch the committee" />
          <div className="mx-auto mt-6 max-w-md">
            <ConveneControls onConvened={() => router.push("/console")} />
            <p className="mt-3 text-center font-mono text-[11px] text-muted">
              The committee stays idle until you convene. Launching opens the live console.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-hairline px-6 py-6 text-center font-mono text-[11px] text-muted">
        Council · Autonomous AI Investment Committee · Paper portfolio on live Bitget market data
      </footer>
    </div>
  );
}

function SectionHead({ n, title, sub }: { n: string; title: string; sub: string }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="font-mono text-xs" style={{ color: GOLD }}>{n}</span>
      <div>
        <h2 className="font-serif text-2xl font-semibold text-text">{title}</h2>
        <p className="mt-0.5 font-mono text-[11px] text-muted">{sub}</p>
      </div>
    </div>
  );
}

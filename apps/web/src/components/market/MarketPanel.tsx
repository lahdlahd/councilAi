"use client";

import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import { fmtCompact, fmtPct, fmtPrice } from "@/lib/agents";
import { fetchMarketSnapshot } from "@/lib/api";
import type { MarketSnapshot, MarketType } from "@/lib/types";
import { useSelectionStore } from "@/stores/selectionStore";
import { useSessionStore } from "@/stores/sessionStore";

const POLL_MS = 3000; // continuous refresh; backend cache shields Bitget

const rsiRead = (rsi: number) =>
  rsi >= 70 ? "overbought" : rsi <= 30 ? "oversold" : "neutral";

function Stat({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="border border-hairline bg-surface-2/40 px-3 py-2">
      <div className="eyebrow">{label}</div>
      <div className="font-mono text-sm tabular-nums" style={color ? { color } : undefined}>
        {value}
      </div>
      {sub && <div className="font-mono text-[10px] text-muted">{sub}</div>}
    </div>
  );
}

export function MarketPanel() {
  // Follow the live session's instrument if one is running, else the user's selection.
  const sessionSymbol = useSessionStore((s) => s.symbol);
  const sessionMarket = useSessionStore((s) => s.snapshot?.market);
  const selSymbol = useSelectionStore((s) => s.symbol);
  const selMarket = useSelectionStore((s) => s.market);
  const symbol = sessionSymbol ?? selSymbol;
  const market = (sessionMarket ?? selMarket) as MarketType;

  const [snap, setSnap] = useState<MarketSnapshot | null>(null);
  const [stale, setStale] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSnap(null);
    setUpdatedAt(null);

    const tick = async () => {
      try {
        const s = await fetchMarketSnapshot(symbol, market);
        if (cancelled) return;
        setSnap(s);
        setStale(false);
        setUpdatedAt(Date.now());
      } catch {
        if (!cancelled) setStale(true);
      } finally {
        if (!cancelled) timer.current = setTimeout(tick, POLL_MS);
      }
    };
    tick();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [symbol, market]);

  const up = (snap?.change24h ?? 0) >= 0;
  const ind = snap?.indicators;
  const color = up ? "#2B8A6E" : "#A54B4B";

  return (
    <div className="border border-hairline bg-surface">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="eyebrow">Live Market — Bitget</span>
          <span className="border border-hairline px-1.5 font-mono text-[9px] uppercase text-muted">
            {market}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={clsx(
              "h-1.5 w-1.5 rounded-full",
              stale ? "bg-bronze" : "bg-positive animate-pulse-soft"
            )}
          />
          <span className="eyebrow">{stale ? "reconnecting" : "live"}</span>
        </div>
      </div>

      <div className="px-4 py-3">
        <div className="flex items-baseline justify-between">
          <span className="font-semibold text-text">{symbol}</span>
          {snap && (
            <span className="font-mono text-[10px] text-muted">
              {snap.source === "coingecko" ? "fallback" : "bitget"}
            </span>
          )}
        </div>

        {/* Price + 24h change */}
        <div className="mt-1 flex items-baseline gap-3">
          <span className="font-mono text-2xl tabular-nums text-text">
            {snap ? fmtPrice(snap.price) : "—"}
          </span>
          <span className="font-mono text-sm tabular-nums" style={{ color }}>
            {snap ? fmtPct(snap.change24h) : ""}
          </span>
        </div>

        {/* Six live metrics */}
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Stat
            label="Volume (24h)"
            value={snap ? `$${fmtCompact(snap.quoteVolume)}` : "—"}
          />
          <Stat
            label="Volatility"
            value={snap ? `${snap.volatility.toFixed(2)}%` : "—"}
          />
          <Stat
            label="RSI (14)"
            value={ind ? ind.rsi.toFixed(1) : "—"}
            sub={ind ? rsiRead(ind.rsi) : undefined}
            color={ind ? (ind.rsi >= 70 ? "#A54B4B" : ind.rsi <= 30 ? "#2B8A6E" : undefined) : undefined}
          />
          <Stat
            label="MACD hist"
            value={ind ? ind.macd.histogram.toFixed(2) : "—"}
            sub={ind ? (ind.macd.histogram >= 0 ? "bullish" : "bearish") : undefined}
            color={ind ? (ind.macd.histogram >= 0 ? "#2B8A6E" : "#A54B4B") : undefined}
          />
        </div>

        <div className="mt-2 text-right font-mono text-[10px] text-muted">
          {updatedAt ? `updated ${new Date(updatedAt).toLocaleTimeString()}` : "loading…"}
        </div>
      </div>
    </div>
  );
}

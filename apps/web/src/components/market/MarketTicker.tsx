"use client";

import clsx from "clsx";
import { fmtCompact, fmtPct, fmtPrice } from "@/lib/agents";
import { setCouncilSymbol } from "@/lib/api";
import { useMarketStore } from "@/stores/marketStore";
import { useSessionStore } from "@/stores/sessionStore";

const ORDER = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"];
const LABEL: Record<string, string> = {
  BTCUSDT: "BTC",
  ETHUSDT: "ETH",
  SOLUSDT: "SOL",
  XRPUSDT: "XRP",
  DOGEUSDT: "DOGE",
};

export function MarketTicker() {
  const bySymbol = useMarketStore((s) => s.bySymbol);
  const degraded = useMarketStore((s) => s.degraded);
  const active = useSessionStore((s) => s.symbol);

  // Selecting a symbol convenes the council on it (takes effect next round).
  const select = (sym: string) => {
    if (sym !== active) setCouncilSymbol(sym).catch(() => {});
  };

  return (
    <div className="border border-hairline bg-surface">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2">
        <span className="eyebrow">Live Market — Bitget</span>
        {degraded ? (
          <span className="font-mono text-[10px] text-bronze">fallback</span>
        ) : (
          <span className="eyebrow">tap to convene</span>
        )}
      </div>
      <div className="divide-y divide-hairline">
        {ORDER.map((sym) => {
          const s = bySymbol[sym];
          const up = (s?.change24h ?? 0) >= 0;
          const isActive = sym === active;
          return (
            <button
              key={sym}
              onClick={() => select(sym)}
              className={clsx(
                "grid w-full grid-cols-[1fr_auto] gap-2 px-4 py-2 text-left transition-colors hover:bg-surface-2",
                isActive && "bg-surface-2"
              )}
            >
              <div className="flex items-baseline gap-2">
                <span
                  className={clsx("h-1.5 w-1.5 self-center rounded-full", isActive ? "bg-gold" : "bg-transparent")}
                />
                <span className="w-10 font-semibold text-text">{LABEL[sym]}</span>
                <span className="font-mono text-sm text-text/90">{s ? fmtPrice(s.price) : "—"}</span>
              </div>
              <div className="text-right">
                <span className={clsx("font-mono text-sm", up ? "text-positive" : "text-negative")}>
                  {s ? fmtPct(s.change24h) : "—"}
                </span>
                <div className="font-mono text-[10px] text-muted">
                  vol {s ? fmtCompact(s.quoteVolume) : "—"} · σ {s ? `${s.volatility.toFixed(2)}%` : "—"}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

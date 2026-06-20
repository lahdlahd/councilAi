"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchPortfolio, fetchSymbols, startCouncil } from "@/lib/api";
import type { MarketType, RiskLevel, SizingMode, SymbolInfo, TradeConfig } from "@/lib/types";
import { useSelectionStore } from "@/stores/selectionStore";
import { useSessionStore } from "@/stores/sessionStore";

const GOLD = "#C9A227";
const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";
const MUTED = "#8C8579";

// Mirrors backend sizing for the pre-session estimate.
const RISK_MULT: Record<RiskLevel, number> = { conservative: 0.5, moderate: 1.0, aggressive: 1.5 };
const ADVERSE_MOVE: Record<RiskLevel, number> = { conservative: 8, moderate: 10, aggressive: 15 };
const BASE_FRACTION = 10; // % of book the council sizes at full confidence
const ASSUMED_CONF = 75;  // nominal confidence for the pre-session estimate

const usd = (n: number) =>
  n.toLocaleString(undefined, { maximumFractionDigits: 0 });

export function ConveneControls({ onConvened }: { onConvened?: () => void } = {}) {
  const symbol = useSelectionStore((s) => s.symbol);
  const market = useSelectionStore((s) => s.market);
  const setSymbol = useSelectionStore((s) => s.setSymbol);
  const setMarket = useSelectionStore((s) => s.setMarket);
  const phase = useSessionStore((s) => s.phase);

  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [convening, setConvening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [sizingMode, setSizingMode] = useState<SizingMode>("percent");
  const [sizePct, setSizePct] = useState(10);
  const [sizeUsd, setSizeUsd] = useState(1000);
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("moderate");
  const [equity, setEquity] = useState<number | null>(null);

  const busy = phase === "debating" || phase === "voting";

  useEffect(() => {
    let alive = true;
    fetchSymbols(market).then((s) => alive && setSymbols(s)).catch(() => alive && setSymbols([]));
    return () => { alive = false; };
  }, [market]);

  useEffect(() => {
    let alive = true;
    const load = () => fetchPortfolio().then((p) => alive && setEquity(p.equity)).catch(() => {});
    load();
    const id = setInterval(load, 8000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  useEffect(() => {
    if (phase !== "idle") setConvening(false);
  }, [phase]);

  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase();
    return (q ? symbols.filter((s) => s.symbol.includes(q)) : symbols).slice(0, 30);
  }, [symbols, query]);

  // Live preview (pre-session estimate).
  const preview = useMemo(() => {
    const book = equity ?? 100000;
    const exposureUsd = sizingMode === "percent" ? (book * sizePct) / 100 : sizeUsd;
    const userMaxPct = book > 0 ? (exposureUsd / book) * 100 : 0;
    const maxLossPct = (userMaxPct / 100) * ADVERSE_MOVE[riskLevel];
    const councilEstPct = BASE_FRACTION * (ASSUMED_CONF / 100) * RISK_MULT[riskLevel];
    const finalPct = Math.min(councilEstPct, userMaxPct);
    return { exposureUsd, userMaxPct, maxLossPct, councilEstPct, finalPct };
  }, [equity, sizingMode, sizePct, sizeUsd, riskLevel]);

  async function convene() {
    setError(null);
    setConvening(true);
    try {
      const tradeConfig: TradeConfig = {
        sizingMode,
        sizeValue: sizingMode === "percent" ? sizePct : sizeUsd,
        riskLevel,
      };
      await startCouncil(symbol, market, tradeConfig);
      onConvened?.();
    } catch {
      setError("Could not convene — is the API reachable?");
      setConvening(false);
    }
  }

  return (
    <div className="overflow-hidden border border-hairline bg-surface shadow-panel">
      {/* Header */}
      <div
        className="flex items-center justify-between border-b border-hairline px-4 py-3"
        style={{ background: "linear-gradient(180deg, rgba(201,162,39,0.06), transparent)" }}
      >
        <div>
          <div className="eyebrow" style={{ color: GOLD }}>Trade Configuration</div>
          <div className="font-mono text-[10px] text-muted">autonomous execution control</div>
        </div>
        <span className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${busy ? "animate-pulse-soft" : ""}`} style={{ background: busy ? POSITIVE : MUTED }} />
          <span className="eyebrow" style={{ color: busy ? POSITIVE : MUTED }}>{busy ? "In session" : "Idle"}</span>
        </span>
      </div>

      <div className="px-4 py-3">
        {/* Market toggle */}
        <div className="grid grid-cols-2 gap-0.5 border border-hairline p-0.5">
          {(["spot", "futures"] as MarketType[]).map((m) => (
            <button
              key={m}
              onClick={() => { setMarket(m); setQuery(""); }}
              className="py-1.5 font-mono text-[11px] uppercase tracking-wide transition-colors"
              style={market === m ? { background: GOLD, color: "#0F1113" } : { color: MUTED }}
            >
              {m}
            </button>
          ))}
        </div>

        {/* Symbol search */}
        <div className="relative mt-2">
          <div className="flex items-center border border-hairline px-2">
            <Search size={13} className="text-muted" />
            <input
              value={open ? query : query || symbol}
              onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
              onFocus={() => { setOpen(true); setQuery(""); }}
              onBlur={() => setTimeout(() => setOpen(false), 120)}
              placeholder="Search pair…"
              className="w-full bg-transparent px-2 py-1.5 font-mono text-xs text-text outline-none placeholder:text-muted/60"
            />
          </div>
          {open && (
            <div className="absolute z-20 mt-1 max-h-56 w-full overflow-auto border border-hairline bg-surface shadow-panel">
              {filtered.length === 0 ? (
                <div className="px-3 py-2 font-mono text-[11px] text-muted">
                  {symbols.length === 0 ? "Loading pairs…" : "No matches"}
                </div>
              ) : (
                filtered.map((s) => (
                  <button
                    key={s.symbol}
                    onMouseDown={() => { setSymbol(s.symbol); setQuery(""); setOpen(false); }}
                    className="flex w-full items-center justify-between px-3 py-1.5 text-left hover:bg-surface-2/40"
                  >
                    <span className="font-mono text-xs text-text">{s.symbol}</span>
                    <span className="font-mono text-[10px] text-muted">{s.base}/{s.quote}</span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Position size */}
        <div className="mt-3 border-t border-hairline pt-3">
          <div className="flex items-center justify-between">
            <span className="eyebrow">Position Size</span>
            <div className="flex gap-0.5 border border-hairline p-0.5">
              {(["percent", "fixed"] as SizingMode[]).map((m) => (
                <button
                  key={m}
                  onClick={() => setSizingMode(m)}
                  className="px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors"
                  style={sizingMode === m ? { background: GOLD, color: "#0F1113" } : { color: MUTED }}
                >
                  {m === "percent" ? "% Book" : "USDT"}
                </button>
              ))}
            </div>
          </div>

          {sizingMode === "percent" ? (
            <div className="mt-2">
              <div className="flex items-baseline justify-between">
                <span className="font-mono text-[10px] text-muted">share of portfolio</span>
                <span className="font-mono text-xl font-semibold tabular-nums" style={{ color: GOLD }}>{sizePct}%</span>
              </div>
              <input
                type="range" min={0} max={100} step={1} value={sizePct}
                onChange={(e) => setSizePct(Number(e.target.value))}
                className="mt-1.5 w-full accent-[#C9A227]"
              />
              <div className="flex justify-between font-mono text-[9px] text-muted/70">
                <span>0%</span><span>50%</span><span>100%</span>
              </div>
            </div>
          ) : (
            <div className="mt-2 flex items-center border border-hairline px-2">
              <span className="font-mono text-[11px] text-muted">$</span>
              <input
                type="number" min={0} step={50} value={sizeUsd}
                onChange={(e) => setSizeUsd(Math.max(0, Number(e.target.value)))}
                className="w-full bg-transparent px-2 py-1.5 font-mono text-sm text-text outline-none"
              />
              <span className="font-mono text-[10px] text-muted">USDT</span>
            </div>
          )}
        </div>

        {/* Risk level chips */}
        <div className="mt-3">
          <span className="eyebrow">Risk Level</span>
          <div className="mt-1.5 grid grid-cols-3 gap-1">
            {(["conservative", "moderate", "aggressive"] as RiskLevel[]).map((r) => (
              <button
                key={r}
                onClick={() => setRiskLevel(r)}
                className="rounded-sm border py-1.5 font-mono text-[10px] uppercase tracking-wide transition-colors"
                style={riskLevel === r
                  ? { borderColor: GOLD, background: `${GOLD}1f`, color: GOLD }
                  : { borderColor: "#2A2F35", color: MUTED }}
              >
                {r === "conservative" ? "Cons." : r === "moderate" ? "Mod." : "Aggr."}
              </button>
            ))}
          </div>
        </div>

        {/* Live preview */}
        <div className="mt-3 border px-3 py-2.5" style={{ borderColor: `${GOLD}55`, background: `${GOLD}0d` }}>
          <div className="flex items-center justify-between">
            <span className="eyebrow" style={{ color: GOLD }}>Estimated Exposure</span>
            <span className="font-mono text-base font-semibold tabular-nums text-text">${usd(preview.exposureUsd)}</span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className="eyebrow">Max Loss Estimate</span>
            <span className="font-mono text-sm font-semibold tabular-nums" style={{ color: NEGATIVE }}>
              −{preview.maxLossPct.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Council vs user vs final */}
        <div className="mt-2 grid grid-cols-3 gap-1 text-center">
          <div className="border border-hairline px-1 py-1.5">
            <div className="eyebrow">Council est.</div>
            <div className="mt-0.5 font-mono text-sm font-semibold tabular-nums" style={{ color: MUTED }}>
              {preview.councilEstPct.toFixed(0)}%
            </div>
          </div>
          <div className="border border-hairline px-1 py-1.5">
            <div className="eyebrow">User max</div>
            <div className="mt-0.5 font-mono text-sm font-semibold tabular-nums text-text">
              {preview.userMaxPct.toFixed(0)}%
            </div>
          </div>
          <div className="border px-1 py-1.5" style={{ borderColor: `${GOLD}66`, background: `${GOLD}12` }}>
            <div className="eyebrow" style={{ color: GOLD }}>Final</div>
            <div className="mt-0.5 font-mono text-sm font-semibold tabular-nums" style={{ color: GOLD }}>
              {preview.finalPct.toFixed(0)}%
            </div>
          </div>
        </div>
        <p className="mt-1.5 font-mono text-[10px] text-muted">
          Council suggests an optimal size; execution never exceeds your cap.
        </p>

        {/* Convene */}
        <button
          onClick={convene}
          disabled={busy || convening}
          className="mt-3 w-full border py-2.5 font-mono text-xs font-semibold uppercase tracking-wider transition-colors disabled:cursor-not-allowed"
          style={busy || convening
            ? { borderColor: "#2A2F35", color: MUTED }
            : { borderColor: GOLD, background: GOLD, color: "#0F1113" }}
        >
          {busy ? "Council in session…" : convening ? "Convening…" : "Convene Council"}
        </button>
        {error && <p className="mt-1 font-mono text-[10px] text-negative">{error}</p>}
      </div>
    </div>
  );
}

"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchSymbols, startCouncil } from "@/lib/api";
import type { MarketType, SymbolInfo } from "@/lib/types";
import { useSelectionStore } from "@/stores/selectionStore";
import { useSessionStore } from "@/stores/sessionStore";

const GOLD = "#C9A227";
const POSITIVE = "#2B8A6E";

export function ConveneControls() {
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

  // A round is actively running during debate/voting; afterwards the council is
  // free to convene again.
  const busy = phase === "debating" || phase === "voting";

  useEffect(() => {
    let alive = true;
    fetchSymbols(market)
      .then((s) => alive && setSymbols(s))
      .catch(() => alive && setSymbols([]));
    return () => {
      alive = false;
    };
  }, [market]);

  // Clear the "convening…" flag once the session actually starts streaming.
  useEffect(() => {
    if (phase !== "idle") setConvening(false);
  }, [phase]);

  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase();
    const list = q ? symbols.filter((s) => s.symbol.includes(q)) : symbols;
    return list.slice(0, 30);
  }, [symbols, query]);

  async function convene() {
    setError(null);
    setConvening(true);
    try {
      await startCouncil(symbol, market);
    } catch {
      setError("Could not convene — is the API reachable?");
      setConvening(false);
    }
  }

  return (
    <div className="border border-hairline bg-surface px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="eyebrow">Convene Council</span>
        <span className="flex items-center gap-1.5">
          <span
            className={`h-1.5 w-1.5 rounded-full ${busy ? "animate-pulse-soft" : ""}`}
            style={{ background: busy ? POSITIVE : "#8C8579" }}
          />
          <span className="eyebrow" style={{ color: busy ? POSITIVE : "#8C8579" }}>
            {busy ? "In session" : "Idle"}
          </span>
        </span>
      </div>

      {/* Market toggle */}
      <div className="mt-3 grid grid-cols-2 gap-0.5 border border-hairline p-0.5">
        {(["spot", "futures"] as MarketType[]).map((m) => (
          <button
            key={m}
            onClick={() => {
              setMarket(m);
              setQuery("");
            }}
            className="py-1.5 font-mono text-[11px] uppercase tracking-wide transition-colors"
            style={market === m ? { background: GOLD, color: "#0F1113" } : { color: "#8C8579" }}
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
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => {
              setOpen(true);
              setQuery("");
            }}
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
                  onMouseDown={() => {
                    setSymbol(s.symbol);
                    setQuery("");
                    setOpen(false);
                  }}
                  className="flex w-full items-center justify-between px-3 py-1.5 text-left hover:bg-surface-2/40"
                >
                  <span className="font-mono text-xs text-text">{s.symbol}</span>
                  <span className="font-mono text-[10px] text-muted">
                    {s.base}/{s.quote}
                  </span>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {/* Selected pair */}
      <div className="mt-2 font-mono text-xs text-text">
        {symbol}
        <span className="ml-1 text-[9px] uppercase text-muted">{market}</span>
      </div>

      {/* Convene */}
      <button
        onClick={convene}
        disabled={busy || convening}
        className="mt-2 w-full border py-2 font-mono text-xs font-semibold uppercase tracking-wide transition-colors disabled:cursor-not-allowed"
        style={
          busy || convening
            ? { borderColor: "#2A2F35", color: "#8C8579" }
            : { borderColor: GOLD, color: GOLD }
        }
      >
        {busy ? "Council in session…" : convening ? "Convening…" : "Convene Council"}
      </button>
      {error && <p className="mt-1 font-mono text-[10px] text-negative">{error}</p>}
    </div>
  );
}

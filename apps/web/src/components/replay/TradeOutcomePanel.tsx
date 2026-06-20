"use client";

import { motion } from "framer-motion";
import { fmtPrice } from "@/lib/agents";
import type { LedgerEntry } from "@/lib/types";

const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";
const GOLD = "#C9A227";

function pnlColor(n: number): string {
  return n > 0 ? POSITIVE : n < 0 ? NEGATIVE : "#8C8579";
}
function signed(n: number, d = 2): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(d)}`;
}

/** The final beat of a trade replay: the paper trade the decision produced. */
export function TradeOutcomePanel({ trade, revealed }: { trade: LedgerEntry; revealed: boolean }) {
  if (!revealed) {
    return (
      <div className="border border-hairline bg-surface px-4 py-3 opacity-60">
        <span className="eyebrow">Trade Outcome</span>
        <p className="mt-2 font-mono text-xs text-muted">Awaiting the council&apos;s decision…</p>
      </div>
    );
  }

  const dirColor = trade.direction === "long" ? POSITIVE : NEGATIVE;
  const isOpen = trade.status === "open";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="relative overflow-hidden border bg-surface px-4 py-3"
      style={{ borderColor: `${GOLD}66` }}
    >
      <div className="absolute left-0 top-0 h-full w-0.5" style={{ background: GOLD }} />
      <div className="flex items-center justify-between">
        <span className="eyebrow">Trade Outcome</span>
        <span className="font-mono text-[10px] uppercase tracking-wide" style={{ color: isOpen ? GOLD : "#8C8579" }}>
          {trade.status}
        </span>
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className="font-mono text-sm font-semibold uppercase" style={{ color: dirColor }}>
          {trade.direction}
        </span>
        <span className="font-mono text-sm text-text">{trade.quantity.toFixed(4)}</span>
        <span className="eyebrow">@ {fmtPrice(trade.entryPrice)}</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div>
          <div className="eyebrow">{isOpen ? "Current" : "Exit"}</div>
          <div className="mt-0.5 font-mono text-sm text-text">{fmtPrice(trade.currentPrice)}</div>
        </div>
        <div>
          <div className="eyebrow">PnL %</div>
          <div className="mt-0.5 font-mono text-sm font-semibold" style={{ color: pnlColor(trade.pnlPct) }}>
            {signed(trade.pnlPct)}%
          </div>
        </div>
        <div className="col-span-2">
          <div className="eyebrow">{isOpen ? "Unrealized" : "Realized"} PnL</div>
          <div className="mt-0.5 font-mono text-lg font-semibold" style={{ color: pnlColor(trade.pnlUsd) }}>
            {signed(trade.pnlUsd)} USDT
          </div>
        </div>
      </div>
    </motion.div>
  );
}

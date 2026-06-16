"use client";

import { AnimatePresence, motion } from "framer-motion";
import { profileFor, SIDE_COLOR } from "@/lib/agents";
import type { Side } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

// Full-bleed, dramatic state when the Risk Manager overrides the council. Shows the
// detailed reasoning and what the analysts WOULD have decided — so the override reads
// as a deliberate act of authority, not a missing result.
export function VetoOverlay() {
  const veto = useSessionStore((s) => s.veto);
  const phase = useSessionStore((s) => s.phase);
  const votes = useSessionStore((s) => s.votes);
  const show = !!veto && phase === "blocked";

  // What the analysts leaned, ignoring the Risk Manager's protective HOLD.
  const analystVotes = votes.filter((v) => v.agentId !== "risk");
  const counts = analystVotes.reduce<Record<string, number>>((acc, v) => {
    acc[v.side] = (acc[v.side] ?? 0) + 1;
    return acc;
  }, {});
  const lean = (Object.entries(counts).sort((a, b) => b[1] - a[1])[0] ?? null) as
    | [Side, number]
    | null;

  return (
    <AnimatePresence>
      {show && veto && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-bg/92 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Red alert wash. */}
          <motion.div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{ background: "radial-gradient(60% 50% at 50% 40%, rgba(165,75,75,0.18), transparent 70%)" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: [0.4, 0.8, 0.4] }}
            transition={{ duration: 2.4, repeat: Infinity }}
          />

          <motion.div
            className="relative mx-6 w-full max-w-xl border border-negative/60 bg-surface px-8 py-8 shadow-panel"
            initial={{ scale: 0.93, y: 10 }}
            animate={{ scale: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 240, damping: 19 }}
          >
            <div className="flex items-center justify-between">
              <div className="eyebrow text-negative">Risk Veto · Override</div>
              <div className="font-mono text-[11px] text-muted">
                risk {veto.riskScore.toFixed(2)}
              </div>
            </div>

            <h2 className="mt-3 text-center font-serif text-4xl font-semibold tracking-tight text-text">
              Council Decision Blocked
            </h2>

            {lean && lean[0] !== "HOLD" && (
              <p className="mt-3 text-center text-sm text-muted">
                The committee was leaning{" "}
                <span className="font-semibold" style={{ color: SIDE_COLOR[lean[0]] }}>
                  {lean[0]}
                </span>{" "}
                ({lean[1]}/{analystVotes.length}) — overridden by the Risk Manager.
              </p>
            )}

            <div className="mx-auto mt-5 h-px w-16 bg-negative/50" />

            {/* Detailed, itemized reasoning. */}
            <ul className="mt-5 space-y-2">
              {veto.factors.map((f, i) => (
                <motion.li
                  key={i}
                  className="flex items-start gap-3 text-[14px] text-text/90"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.15 + i * 0.1 }}
                >
                  <span className="mt-[2px] font-mono text-xs text-negative">▍</span>
                  <span>{f}</span>
                </motion.li>
              ))}
            </ul>

            <p className="mt-6 text-center font-mono text-[11px] uppercase tracking-wider text-muted">
              Vetoed by {profileFor(veto.byAgent).name} · capital preservation first
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

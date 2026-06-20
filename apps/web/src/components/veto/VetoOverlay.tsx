"use client";

import { AnimatePresence, motion } from "framer-motion";
import { profileFor, SIDE_COLOR } from "@/lib/agents";
import type { Side } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

// Full-bleed override moment when the Risk Manager blocks the council. It reads as a
// deliberate act of authority: a red alert wash, a slamming VETO stamp, the council's
// overridden lean, and the itemized reasoning.
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
          {/* Sharp red flash on entry. */}
          <motion.div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-negative"
            initial={{ opacity: 0.55 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          />
          {/* Pulsing alert wash. */}
          <motion.div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{ background: "radial-gradient(60% 50% at 50% 40%, rgba(165,75,75,0.20), transparent 70%)" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: [0.45, 0.85, 0.45] }}
            transition={{ duration: 2.4, repeat: Infinity }}
          />

          <motion.div
            className="relative mx-6 w-full max-w-xl border border-negative/60 bg-surface px-8 py-9 shadow-panel"
            initial={{ scale: 0.93, y: 10 }}
            animate={{ scale: 1, y: 0, x: [0, -7, 6, -4, 3, 0] }}
            transition={{ scale: { type: "spring", stiffness: 240, damping: 19 }, x: { duration: 0.45 } }}
          >
            {/* Slamming VETO stamp. */}
            <motion.div
              aria-hidden
              className="pointer-events-none absolute -top-6 left-1/2 select-none border-4 border-negative px-5 py-1 font-mono text-3xl font-black uppercase tracking-[0.3em] text-negative"
              style={{ x: "-50%" }}
              initial={{ scale: 2.6, opacity: 0, rotate: -18 }}
              animate={{ scale: 1, opacity: 0.92, rotate: -9 }}
              transition={{ type: "spring", stiffness: 320, damping: 14, delay: 0.08 }}
            >
              Veto
            </motion.div>

            <div className="mt-3 flex items-center justify-between">
              <div className="eyebrow text-negative">Risk Override</div>
              <div className="font-mono text-[11px] text-muted">risk {veto.riskScore.toFixed(2)}</div>
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

            {/* The Risk Manager's reasoning, itemized. */}
            <div className="mt-5 font-mono text-[10px] uppercase tracking-wider text-negative/80">
              Reasoning
            </div>
            <ul className="mt-2 space-y-2">
              {veto.factors.map((f, i) => (
                <motion.li
                  key={i}
                  className="flex items-start gap-3 text-[14px] text-text/90"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.35 + i * 0.1 }}
                >
                  <span className="mt-[2px] font-mono text-xs text-negative">&#9613;</span>
                  <span>{f}</span>
                </motion.li>
              ))}
            </ul>

            <p className="mt-6 text-center font-mono text-[11px] uppercase tracking-wider text-muted">
              Vetoed by {profileFor(veto.byAgent).name} &middot; capital preservation first
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

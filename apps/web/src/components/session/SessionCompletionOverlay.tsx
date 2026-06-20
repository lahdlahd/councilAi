"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { SIDE_COLOR } from "@/lib/agents";
import { useSessionStore } from "@/stores/sessionStore";

const GOLD = "#C9A227";
const POSITIVE = "#2B8A6E";
const MUTED = "#8C8579";

const STEPS = ["Voting complete", "Risk review complete", "Decision reached"];

export function SessionCompletionOverlay() {
  const phase = useSessionStore((s) => s.phase);
  const rec = useSessionStore((s) => s.recommendation);
  const confidence = useSessionStore((s) => s.confidence);

  const prev = useRef(phase);
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (prev.current !== "decided" && phase === "decided") setShow(true);
    prev.current = phase;
  }, [phase]);

  // Dismiss on Escape.
  useEffect(() => {
    if (!show) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setShow(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [show]);

  const side = rec?.side ?? null;
  const sideColor = side ? SIDE_COLOR[side] : GOLD;
  const conf = rec?.confidence ?? confidence;
  const consensusPct = Math.round((rec?.consensusRatio ?? 0) * 100);
  const tradeLabel = side === "HOLD" ? "No Trade — Council Held" : "Paper Trade Created";
  const tradeColor = side === "HOLD" ? MUTED : POSITIVE;

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => setShow(false)}
        >
          <motion.div
            className="w-full max-w-md overflow-hidden border bg-surface shadow-panel"
            style={{ borderColor: `${sideColor}66` }}
            initial={{ scale: 0.94, y: 12, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 22 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-7 py-6">
              <div className="text-center eyebrow">Session Concluded</div>

              {/* Animated checklist */}
              <div className="mx-auto mt-4 max-w-xs space-y-2.5">
                {STEPS.map((label, i) => (
                  <motion.div
                    key={label}
                    className="flex items-center gap-2.5"
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.15 + i * 0.32 }}
                  >
                    <motion.span
                      className="flex h-5 w-5 items-center justify-center rounded-full"
                      style={{ background: `${POSITIVE}22` }}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.25 + i * 0.32, type: "spring", stiffness: 500, damping: 16 }}
                    >
                      <Check size={12} style={{ color: POSITIVE }} />
                    </motion.span>
                    <span className="font-mono text-xs text-text">{label}</span>
                  </motion.div>
                ))}
              </div>

              {/* Verdict reveal */}
              <motion.div
                className="mt-6 border-t border-hairline pt-6 text-center"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 + STEPS.length * 0.32 + 0.15 }}
              >
                <div className="eyebrow">Final Recommendation</div>
                <div className="mt-1 font-serif text-7xl font-bold leading-none tracking-tight" style={{ color: sideColor }}>
                  {side ?? "—"}
                </div>

                <div className="mt-5 grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="eyebrow">Confidence</div>
                    <div className="mt-0.5 font-mono text-lg font-semibold" style={{ color: GOLD }}>
                      {conf == null ? "—" : `${Math.round(conf)}%`}
                    </div>
                  </div>
                  <div>
                    <div className="eyebrow">Consensus</div>
                    <div className="mt-0.5 font-mono text-lg font-semibold" style={{ color: rec?.consensusReached ? POSITIVE : MUTED }}>
                      {rec?.consensusReached ? "Reached" : "Split"}
                    </div>
                    <div className="font-mono text-[10px] text-muted">{consensusPct}%</div>
                  </div>
                  <div>
                    <div className="eyebrow">Trade</div>
                    <div className="mt-0.5 font-mono text-[13px] font-semibold leading-tight" style={{ color: tradeColor }}>
                      {side === "HOLD" ? "None" : "Created"}
                    </div>
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-center gap-2">
                  <button
                    onClick={() => setShow(false)}
                    className="border px-5 py-2 font-mono text-xs font-semibold uppercase tracking-wide transition-colors"
                    style={{ borderColor: GOLD, background: GOLD, color: "#0F1113" }}
                  >
                    Continue
                  </button>
                  <Link
                    href="/dashboard"
                    className="border border-hairline px-5 py-2 font-mono text-xs font-semibold uppercase tracking-wide text-text transition-colors hover:border-gold hover:text-gold"
                  >
                    View Portfolio
                  </Link>
                </div>
                <div className="mt-3 font-mono text-[10px]" style={{ color: tradeColor }}>
                  {tradeLabel}
                </div>
              </motion.div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

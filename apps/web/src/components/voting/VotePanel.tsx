"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AGENT_ACCENT, profileFor, SIDE_COLOR } from "@/lib/agents";
import type { AgentId, Side } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

const SIDES: Side[] = ["BUY", "HOLD", "SELL"];
// Analysts that get a vote (the chairman abstains) — drives the quorum count.
const VOTING_SEATS = 4;

export function VotePanel() {
  const votes = useSessionStore((s) => s.votes);
  const phase = useSessionStore((s) => s.phase);
  const rec = useSessionStore((s) => s.recommendation);

  const counts: Record<Side, AgentId[]> = { BUY: [], HOLD: [], SELL: [] };
  votes.forEach((v) => counts[v.side].push(v.agentId));

  const leading = (Object.keys(counts) as Side[]).reduce((a, b) =>
    counts[b].length > counts[a].length ? b : a
  );
  const leadCount = counts[leading].length;
  const reached = rec ? rec.consensusReached : votes.length > 0 && leadCount / votes.length >= 0.6;
  const active = phase === "voting";

  return (
    <div
      className="border bg-surface px-4 py-3 transition-colors"
      style={{ borderColor: active ? "rgba(201,162,39,0.5)" : "#2A2F35" }}
    >
      <div className="flex items-center justify-between">
        <span className="eyebrow">Votes</span>
        <span className="font-mono text-[10px] text-muted">
          {votes.length}/{VOTING_SEATS} cast
        </span>
      </div>

      {/* Consensus readout — the headline of the voting beat. */}
      <div className="mt-2 flex items-baseline gap-2">
        {votes.length === 0 ? (
          <span className="font-mono text-xs text-muted">awaiting votes…</span>
        ) : (
          <>
            <span
              className="font-serif text-xl font-semibold"
              style={{ color: SIDE_COLOR[leading] }}
            >
              {leading}
            </span>
            <span className="eyebrow">
              {reached ? "consensus" : "split"} · {leadCount}/{votes.length}
            </span>
          </>
        )}
      </div>

      <div className="mt-3 space-y-2">
        {SIDES.map((side) => {
          const cast = counts[side];
          const pct = votes.length ? (cast.length / votes.length) * 100 : 0;
          return (
            <div key={side} className="flex items-center gap-3">
              <span
                className="w-9 font-mono text-xs font-semibold"
                style={{ color: SIDE_COLOR[side] }}
              >
                {side}
              </span>
              <div className="relative h-1.5 flex-1 bg-surface-2">
                <motion.div
                  className="absolute inset-y-0 left-0"
                  style={{ background: SIDE_COLOR[side] }}
                  animate={{ width: `${pct}%` }}
                  transition={{ type: "spring", stiffness: 180, damping: 24 }}
                />
              </div>
              <div className="flex w-16 justify-end gap-1">
                <AnimatePresence>
                  {cast.map((id) => (
                    <motion.span
                      key={id}
                      title={profileFor(id).name}
                      aria-hidden
                      className="text-xs"
                      style={{ color: AGENT_ACCENT[id] }}
                      initial={{ scale: 0, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: "spring", stiffness: 500, damping: 18 }}
                    >
                      {profileFor(id).avatar}
                    </motion.span>
                  ))}
                </AnimatePresence>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

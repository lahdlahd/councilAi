"use client";

import { motion } from "framer-motion";
import { AGENT_ACCENT, AGENT_ORDER, profileFor, SIDE_COLOR } from "@/lib/agents";
import type { AgentId, Side } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

const SIDES: Side[] = ["BUY", "HOLD", "SELL"];
// The four analysts cast ballots; the Execution Agent chairs and returns the verdict.
const ANALYSTS = AGENT_ORDER.filter((id) => id !== "execution");
const SEATS = ANALYSTS.length;
const MUTED = "#8C8579";
const POSITIVE = "#2B8A6E";

function VoteChip({ side }: { side: Side | null }) {
  if (!side) return <span className="font-mono text-[11px] text-muted">—</span>;
  return (
    <span
      className="rounded-sm px-2.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide"
      style={{ color: SIDE_COLOR[side], background: `${SIDE_COLOR[side]}1f` }}
    >
      {side}
    </span>
  );
}

export function CouncilVotingPanel() {
  const votes = useSessionStore((s) => s.votes);
  const phase = useSessionStore((s) => s.phase);
  const rec = useSessionStore((s) => s.recommendation);

  const voteFor = (id: AgentId): Side | null =>
    votes.find((v) => v.agentId === id)?.side ?? null;

  const counts: Record<Side, number> = { BUY: 0, HOLD: 0, SELL: 0 };
  votes.forEach((v) => {
    counts[v.side] += 1;
  });
  const cast = votes.length;

  const leading = SIDES.reduce((a, b) => (counts[b] > counts[a] ? b : a));
  const leadCount = counts[leading];
  const reached = rec ? rec.consensusReached : cast > 0 && leadCount / cast >= 0.6;
  const active = phase === "voting";
  const execVerdict = rec?.side ?? null;

  return (
    <div
      className="border bg-surface shadow-panel transition-colors"
      style={{ borderColor: active ? "rgba(201,162,39,0.55)" : "#2A2F35" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <div>
          <div className="eyebrow">Council Vote</div>
          <h2 className="font-serif text-lg text-text">Committee Ballot</h2>
        </div>
        <span className="font-mono text-[11px] text-muted">{cast}/{SEATS} cast</span>
      </div>

      {/* Per-agent votes */}
      <div className="divide-y divide-hairline/60 px-5">
        {ANALYSTS.map((id) => {
          const p = profileFor(id);
          return (
            <div key={id} className="flex items-center justify-between py-2.5">
              <span className="flex items-center gap-2.5">
                <span className="text-lg">{p.avatar}</span>
                <span className="font-mono text-xs" style={{ color: AGENT_ACCENT[id] }}>
                  {p.name}
                </span>
              </span>
              <VoteChip side={voteFor(id)} />
            </div>
          );
        })}

        {/* Execution Agent — chairman's verdict */}
        <div className="flex items-center justify-between py-2.5">
          <span className="flex items-center gap-2.5">
            <span className="text-lg">{profileFor("execution").avatar}</span>
            <span className="font-mono text-xs" style={{ color: AGENT_ACCENT.execution }}>
              {profileFor("execution").name}
              <span className="ml-1.5 text-[9px] uppercase tracking-wider text-muted">chair</span>
            </span>
          </span>
          <VoteChip side={execVerdict} />
        </div>
      </div>

      {/* Vote totals — bars + counters */}
      <div className="space-y-2.5 border-t border-hairline px-5 py-4">
        <div className="eyebrow">Vote Totals</div>
        {SIDES.map((side) => {
          const pct = SEATS ? (counts[side] / SEATS) * 100 : 0;
          return (
            <div key={side} className="flex items-center gap-3">
              <span className="w-10 font-mono text-xs font-semibold" style={{ color: SIDE_COLOR[side] }}>
                {side}
              </span>
              <div className="relative h-2 flex-1 bg-surface-2">
                <motion.div
                  className="absolute inset-y-0 left-0"
                  style={{ background: SIDE_COLOR[side] }}
                  animate={{ width: `${pct}%` }}
                  transition={{ type: "spring", stiffness: 180, damping: 24 }}
                />
              </div>
              <span
                className="w-6 text-right font-mono text-lg font-semibold tabular-nums"
                style={{ color: SIDE_COLOR[side] }}
              >
                {counts[side]}
              </span>
            </div>
          );
        })}
      </div>

      {/* Council Consensus */}
      <div className="border-t border-hairline px-5 py-4">
        <div className="eyebrow">Council Consensus</div>
        {cast === 0 ? (
          <p className="mt-1 font-mono text-sm text-muted">Awaiting the committee&apos;s votes…</p>
        ) : (
          <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-serif text-3xl font-bold" style={{ color: SIDE_COLOR[leading] }}>
              {leading}
            </span>
            <span className="font-mono text-xs" style={{ color: reached ? POSITIVE : MUTED }}>
              {reached ? "Consensus reached" : "Split — no consensus"} · {leadCount}/{cast}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

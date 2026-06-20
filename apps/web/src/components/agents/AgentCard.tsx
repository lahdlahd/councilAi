"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import { AGENT_ACCENT, profileFor, SIDE_COLOR, STANCE_META } from "@/lib/agents";
import type { AgentProfile, Side, Stance } from "@/lib/types";

interface Props {
  profile: AgentProfile;
  thinking: boolean;
  spoke: boolean;
  vote: Side | null;
  stance: Stance | null;
  confidence: number | null;
}

// Persistent identity card: avatar, specialty, persona, plus the agent's live
// stance and confidence as the debate unfolds. Visual identity is keyed to the
// agent id so it stays consistent whatever the data source.
export function AgentCard({ profile, thinking, spoke, vote, stance, confidence }: Props) {
  const accent = AGENT_ACCENT[profile.id];
  const identity = profileFor(profile.id);
  const stanceMeta = stance ? STANCE_META[stance] : null;

  return (
    <div
      className={clsx(
        "relative overflow-hidden border border-hairline bg-surface px-3 py-3 transition-colors",
        thinking && "border-l-2"
      )}
      style={thinking ? { borderLeftColor: accent } : undefined}
    >
      {/* Active sweep while the agent is thinking. */}
      {thinking && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ background: `linear-gradient(90deg, ${accent}14, transparent)` }}
          initial={{ opacity: 0 }}
          animate={{ opacity: [0.2, 0.6, 0.2] }}
          transition={{ duration: 1.4, repeat: Infinity }}
        />
      )}

      <div className="relative flex items-start gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center border text-xl"
          style={{ borderColor: `${accent}55`, color: accent, background: `${accent}0D` }}
        >
          <span aria-hidden>{identity.avatar}</span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[13px] font-semibold text-text">{identity.name}</span>
            {vote ? (
              <span className="font-mono text-[10px] font-semibold" style={{ color: SIDE_COLOR[vote] }}>
                {vote}
              </span>
            ) : (
              profile.castsVote === false && (
                <span className="font-mono text-[9px] uppercase text-muted/70">chair</span>
              )
            )}
          </div>

          <p className="truncate text-[10px] uppercase tracking-wider text-muted">
            {identity.specialty}
          </p>
          {/* Personality — what makes this agent itself. */}
          <p className="mt-1 text-[11px] italic leading-snug text-muted/90">{identity.persona}</p>

          {/* Current stance + confidence (appear once the agent has spoken). */}
          <div className="mt-2 flex items-center gap-2">
            {stanceMeta ? (
              <span
                className="border px-1.5 py-[1px] font-mono text-[9px] uppercase tracking-wide"
                style={{ color: stanceMeta.color, borderColor: `${stanceMeta.color}66` }}
              >
                {stanceMeta.label}
              </span>
            ) : (
              <span className="font-mono text-[9px] uppercase tracking-wide text-muted/60">
                {thinking ? "analyzing…" : "awaiting"}
              </span>
            )}
            {confidence !== null && (
              <span className="ml-auto font-mono text-[10px] text-muted">
                conf {Math.round(confidence)}
              </span>
            )}
          </div>

          {/* Confidence meter. */}
          <div className="mt-1.5 h-1 w-full overflow-hidden bg-surface-2">
            <motion.div
              className="h-full"
              style={{ background: accent }}
              initial={false}
              animate={{ width: `${confidence ?? 0}%` }}
              transition={{ type: "spring", stiffness: 120, damping: 20 }}
            />
          </div>

          {/* Live status. */}
          {thinking && (
            <div className="mt-2 flex items-center gap-1.5">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-1 w-1 rounded-full animate-pulse-soft"
                    style={{ background: accent, animationDelay: `${i * 0.18}s` }}
                  />
                ))}
              </span>
              <span className="font-mono text-[9px] text-text">deliberating</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

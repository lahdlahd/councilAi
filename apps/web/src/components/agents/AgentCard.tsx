"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import { AGENT_ACCENT, SIDE_COLOR } from "@/lib/agents";
import type { AgentProfile, Side } from "@/lib/types";

interface Props {
  profile: AgentProfile;
  thinking: boolean;
  spoke: boolean;
  vote: Side | null;
}

export function AgentCard({ profile, thinking, spoke, vote }: Props) {
  const accent = AGENT_ACCENT[profile.id];

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
          className="flex h-9 w-9 shrink-0 items-center justify-center border text-lg"
          style={{ borderColor: `${accent}55`, color: accent }}
        >
          <span aria-hidden>{profile.avatar}</span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[13px] font-semibold text-text">{profile.name}</span>
            {vote && (
              <span
                className="font-mono text-[10px] font-semibold"
                style={{ color: SIDE_COLOR[vote] }}
              >
                {vote}
              </span>
            )}
          </div>
          <p className="truncate text-[10px] uppercase tracking-wider text-muted">
            {profile.specialty}
          </p>

          <div className="mt-2 flex items-center gap-2">
            <span
              className={clsx(
                "font-mono text-[10px]",
                thinking ? "text-text" : spoke ? "text-muted" : "text-muted/60"
              )}
            >
              {thinking ? "analyzing…" : spoke ? "spoke" : "waiting"}
            </span>
            {thinking && (
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-1 w-1 rounded-full animate-pulse-soft"
                    style={{ background: accent, animationDelay: `${i * 0.18}s` }}
                  />
                ))}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

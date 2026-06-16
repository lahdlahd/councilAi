"use client";

import { AGENT_ACCENT, profileFor } from "@/lib/agents";
import type { AgentId } from "@/lib/types";

export function TypingIndicator({ agentId }: { agentId: AgentId }) {
  const accent = AGENT_ACCENT[agentId];
  const name = profileFor(agentId).name;
  return (
    <div className="flex items-center gap-3 px-1 py-2 text-muted">
      <span className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 rounded-full animate-pulse-soft"
            style={{ background: accent, animationDelay: `${i * 0.18}s` }}
          />
        ))}
      </span>
      <span className="font-mono text-[11px] uppercase tracking-wider">
        {name} is forming a view
      </span>
    </div>
  );
}

"use client";

import { AGENT_ORDER, profileFor } from "@/lib/agents";
import type { AgentId, Side, Stance } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";
import { AgentCard } from "./AgentCard";

export function AgentRoster() {
  const agents = useSessionStore((s) => s.agents);
  const thinking = useSessionStore((s) => s.thinking);
  const votes = useSessionStore((s) => s.votes);
  const messages = useSessionStore((s) => s.messages);

  const voteByAgent = new Map<AgentId, Side>(votes.map((v) => [v.agentId, v.side]));
  const spokeSet = new Set(messages.map((m) => m.agentId));
  // Latest stance + confidence for each agent, from their most recent statement.
  const latest = new Map<AgentId, { stance: Stance; confidence: number }>();
  for (const m of messages) latest.set(m.agentId, { stance: m.stance, confidence: m.confidence });

  // Fall back to static profiles until the first session event arrives.
  const list = agents.length
    ? agents
    : AGENT_ORDER.map((id) => ({ ...profileFor(id), id, personality: "", castsVote: id !== "execution" }));

  return (
    <aside className="flex flex-col gap-2">
      <div className="flex items-center justify-between px-1">
        <span className="eyebrow">The Committee</span>
        <span className="eyebrow">{list.length}</span>
      </div>
      {list.map((p) => (
        <AgentCard
          key={p.id}
          profile={p}
          thinking={thinking === p.id}
          spoke={spokeSet.has(p.id)}
          vote={voteByAgent.get(p.id) ?? null}
          stance={latest.get(p.id)?.stance ?? null}
          confidence={latest.get(p.id)?.confidence ?? null}
        />
      ))}
    </aside>
  );
}

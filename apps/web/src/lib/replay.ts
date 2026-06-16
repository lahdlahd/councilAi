import { AGENT_ORDER, profileFor } from "./agents";
import type { AgentProfile, JournalEntry, WsEvent } from "./types";

// One step in a replay: an event to apply, and how long to wait after it (ms, at 1x).
export interface ReplayStep {
  event: WsEvent;
  delayAfter: number;
}

const TOKEN_MS = 45; // matches the live cadence feel
const THINK_MS = 600;
const MSG_GAP_MS = 350;
const VOTE_MS = 250;
const BEAT_MS = 350;

const words = (text: string): string[] => text.match(/\S+\s*/g) ?? [text];

function profiles(): AgentProfile[] {
  return AGENT_ORDER.map((id) => ({
    ...profileFor(id),
    id,
    personality: "",
    castsVote: id !== "execution",
  }));
}

// Expand a recorded decision into the same event sequence the live session emitted,
// so replay drives the identical chamber rendering — just on a local clock.
export function buildTimeline(entry: JournalEntry): ReplayStep[] {
  const steps: ReplayStep[] = [];
  const voteByAgent = new Map(entry.votes.map((v) => [v.agentId, v]));

  // Seed/clear via a synthetic snapshot.
  steps.push({
    event: {
      type: "session.snapshot",
      sessionId: entry.sessionId,
      symbol: entry.symbol,
      snapshot: entry.snapshot,
      startedAt: entry.startedAt,
      phase: "debating",
      agents: profiles(),
      messages: [],
      votes: [],
      veto: null,
      confidence: null,
      confidenceBreakdown: null,
      recommendation: null,
    },
    delayAfter: BEAT_MS,
  });

  for (const m of entry.messages) {
    steps.push({ event: { type: "agent.thinking", agentId: m.agentId }, delayAfter: THINK_MS });
    for (const w of words(m.text)) {
      steps.push({
        event: { type: "agent.token", agentId: m.agentId, messageId: m.messageId, delta: w },
        delayAfter: TOKEN_MS,
      });
    }
    steps.push({ event: { type: "agent.message", message: m }, delayAfter: MSG_GAP_MS });
    if (m.references.length) {
      steps.push({
        event: {
          type: "debate.reference",
          fromAgent: m.agentId,
          toAgents: m.references,
          stance: m.stance,
        },
        delayAfter: 0,
      });
    }
    const vote = voteByAgent.get(m.agentId);
    if (vote) steps.push({ event: { type: "vote.cast", vote }, delayAfter: VOTE_MS });
  }

  steps.push({ event: { type: "council.phase", phase: "voting" }, delayAfter: BEAT_MS });
  if (entry.confidence !== null && entry.confidenceBreakdown) {
    steps.push({
      event: { type: "council.confidence", score: entry.confidence, breakdown: entry.confidenceBreakdown },
      delayAfter: BEAT_MS,
    });
  }
  if (entry.veto) {
    steps.push({ event: { type: "council.veto", veto: entry.veto }, delayAfter: 200 });
  }
  if (entry.recommendation) {
    steps.push({ event: { type: "council.recommendation", recommendation: entry.recommendation }, delayAfter: 0 });
  }
  steps.push({ event: { type: "council.phase", phase: entry.phase }, delayAfter: 0 });

  return steps;
}

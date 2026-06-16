import { create } from "zustand";
import type {
  AgentId,
  AgentMessage,
  AgentProfile,
  ConfidenceBreakdown,
  MarketSnapshot,
  Phase,
  Recommendation,
  VetoInfo,
  Vote,
  WsEvent,
} from "../lib/types";

// A message as rendered in the chamber: the wire message plus a streaming flag
// while its tokens are still arriving.
export interface ChamberMessage extends AgentMessage {
  streaming: boolean;
}

interface SessionState {
  connected: boolean;
  sessionId: string | null;
  symbol: string | null;
  snapshot: MarketSnapshot | null;
  phase: Phase;
  agents: AgentProfile[];
  messages: ChamberMessage[];
  votes: Vote[];
  veto: VetoInfo | null;
  confidence: number | null;
  breakdown: ConfidenceBreakdown | null;
  recommendation: Recommendation | null;
  thinking: AgentId | null;

  setConnected: (c: boolean) => void;
  reset: () => void;
  apply: (e: WsEvent) => void;
}

const FRESH = {
  messages: [] as ChamberMessage[],
  votes: [] as Vote[],
  veto: null as VetoInfo | null,
  confidence: null as number | null,
  breakdown: null as ConfidenceBreakdown | null,
  recommendation: null as Recommendation | null,
  thinking: null as AgentId | null,
};

export const useSessionStore = create<SessionState>((set) => ({
  connected: false,
  sessionId: null,
  symbol: null,
  snapshot: null,
  phase: "idle",
  agents: [],
  ...FRESH,

  setConnected: (c) => set({ connected: c }),

  reset: () =>
    set({
      sessionId: null,
      symbol: null,
      snapshot: null,
      phase: "idle",
      agents: [],
      ...FRESH,
    }),

  apply: (e) =>
    set((s) => {
      switch (e.type) {
        case "session.snapshot":
          return {
            sessionId: e.sessionId,
            symbol: e.symbol,
            snapshot: e.snapshot,
            phase: e.phase,
            agents: e.agents,
            messages: e.messages.map((m) => ({ ...m, streaming: false })),
            votes: e.votes,
            veto: e.veto,
            confidence: e.confidence,
            breakdown: e.confidenceBreakdown,
            recommendation: e.recommendation,
            thinking: null,
          };

        case "session.started":
          // A new round begins — clear the prior debate but keep the chrome.
          return {
            sessionId: e.sessionId,
            symbol: e.symbol,
            snapshot: e.snapshot,
            agents: e.agents,
            phase: "debating",
            ...FRESH,
          };

        case "council.phase":
          return { phase: e.phase };

        case "agent.thinking":
          return { thinking: e.agentId };

        case "agent.token": {
          const existing = s.messages.find((m) => m.messageId === e.messageId);
          if (existing) {
            return {
              messages: s.messages.map((m) =>
                m.messageId === e.messageId ? { ...m, text: m.text + e.delta } : m
              ),
            };
          }
          // First token for this message — create a streaming placeholder.
          const placeholder: ChamberMessage = {
            messageId: e.messageId,
            agentId: e.agentId,
            text: e.delta,
            stance: "neutral",
            references: [],
            confidence: 50,
            ts: Date.now(),
            streaming: true,
          };
          return { messages: [...s.messages, placeholder], thinking: null };
        }

        case "agent.message": {
          const m = e.message;
          const final: ChamberMessage = { ...m, streaming: false };
          const found = s.messages.some((x) => x.messageId === m.messageId);
          return {
            thinking: null,
            messages: found
              ? s.messages.map((x) => (x.messageId === m.messageId ? final : x))
              : [...s.messages, final],
          };
        }

        case "vote.cast":
          return { votes: [...s.votes.filter((v) => v.agentId !== e.vote.agentId), e.vote] };

        case "council.confidence":
          return { confidence: e.score, breakdown: e.breakdown };

        case "council.veto":
          return { veto: e.veto };

        case "council.recommendation":
          return { recommendation: e.recommendation };

        default:
          return {};
      }
    }),
}));

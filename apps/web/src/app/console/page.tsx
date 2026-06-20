"use client";

import { AgentRoster } from "@/components/agents/AgentRoster";
import { DebateTimeline } from "@/components/chamber/DebateTimeline";
import { ExplainableConfidence } from "@/components/confidence/ExplainableConfidence";
import { ConveneControls } from "@/components/convene/ConveneControls";
import { DecisionSummaryCard } from "@/components/decision/DecisionSummaryCard";
import { PaperTradeCard } from "@/components/decision/PaperTradeCard";
import { RiskReviewCard } from "@/components/risk/RiskReviewCard";
import { SessionCompletionOverlay } from "@/components/session/SessionCompletionOverlay";
import { SessionTimeline } from "@/components/session/SessionTimeline";
import { TradeLedger } from "@/components/ledger/TradeLedger";
import { TopBar } from "@/components/TopBar";
import { VetoOverlay } from "@/components/veto/VetoOverlay";
import { CouncilVotingPanel } from "@/components/voting/CouncilVotingPanel";
import { useCouncilStream } from "@/hooks/useStreams";
import { useSessionStore } from "@/stores/sessionStore";

const GOLD = "#C9A227";
const POSITIVE = "#2B8A6E";
const NEGATIVE = "#A54B4B";
const MUTED = "#8C8579";

function sessionNo(id: string | null): string {
  if (!id) return "----";
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return String(1000 + (h % 9000));
}

function StatusPill({ phase }: { phase: string }) {
  const map: Record<string, { label: string; color: string; pulse?: boolean }> = {
    debating: { label: "LIVE", color: POSITIVE, pulse: true },
    voting: { label: "LIVE", color: POSITIVE, pulse: true },
    decided: { label: "DECIDED", color: GOLD },
    blocked: { label: "BLOCKED", color: NEGATIVE },
    idle: { label: "IDLE", color: MUTED },
  };
  const s = map[phase] ?? map.idle;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider"
      style={{ color: s.color, background: `${s.color}1a` }}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.pulse ? "animate-pulse-soft" : ""}`} style={{ background: s.color }} />
      {s.label}
    </span>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <div className="mb-2 eyebrow">{children}</div>;
}

export default function Console() {
  useCouncilStream();
  const sessionId = useSessionStore((s) => s.sessionId);
  const symbol = useSessionStore((s) => s.symbol);
  const phase = useSessionStore((s) => s.phase);

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar />

      {/* Session Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline px-5 py-3">
        <div className="flex items-baseline gap-4">
          <span className="font-mono text-lg font-semibold text-text">
            Session <span style={{ color: GOLD }}>#{sessionNo(sessionId)}</span>
          </span>
          <span className="font-mono text-sm text-text">{symbol ?? "—"}</span>
        </div>
        <StatusPill phase={phase} />
      </div>

      <main className="mx-auto w-full max-w-7xl space-y-4 p-4 pb-16">
        {/* Progress stepper */}
        <SessionTimeline />

        {/* Band: Committee Status · Decision Summary · Metrics */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div>
            <Label>Committee Status</Label>
            <AgentRoster />
          </div>
          <div>
            <Label>Decision Summary</Label>
            <DecisionSummaryCard />
          </div>
          <div>
            <Label>Decision Metrics</Label>
            <div className="space-y-4">
              <ExplainableConfidence />
              <ConveneControls />
            </div>
          </div>
        </div>

        {/* Full-width stacked sections */}
        <div>
          <Label>Council Vote</Label>
          <CouncilVotingPanel />
        </div>

        <div>
          <Label>Risk Review</Label>
          <RiskReviewCard />
        </div>

        <div>
          <Label>Paper Trade</Label>
          <PaperTradeCard />
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="eyebrow">Debate Timeline</span>
            <span className="font-mono text-[10px] text-muted">· supporting detail</span>
          </div>
          <div className="h-96">
            <DebateTimeline />
          </div>
        </div>
      </main>

      <VetoOverlay />
      <SessionCompletionOverlay />
      <TradeLedger />
    </div>
  );
}

"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { useSessionStore } from "@/stores/sessionStore";

// A stable, human-friendly session number derived from the session id.
function sessionNumber(id: string | null): string {
  if (!id) return "—";
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return String(1000 + (h % 9000));
}

interface Step {
  label: string;
  done: boolean;
  danger?: boolean;
}

export function SessionTimeline() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const snapshot = useSessionStore((s) => s.snapshot);
  const phase = useSessionStore((s) => s.phase);
  const votes = useSessionStore((s) => s.votes);
  const agents = useSessionStore((s) => s.agents);
  const confidence = useSessionStore((s) => s.confidence);
  const recommendation = useSessionStore((s) => s.recommendation);

  const hasSession = phase !== "idle" && (!!sessionId || !!snapshot);
  const expectedVotes = agents.filter((a) => a.castsVote).length || 4;
  const vetoed = recommendation?.vetoed ?? false;

  // Each stage maps to a concrete signal from the live event stream.
  const scanDone = !!snapshot;
  const decisionDone = recommendation !== null && (phase === "decided" || phase === "blocked");
  const reviewDone = confidence !== null || decisionDone;
  const votingDone = votes.length >= expectedVotes || reviewDone;
  const debateDone = votes.length > 0 || votingDone;

  const steps: Step[] = [
    { label: "Market Scan", done: scanDone },
    { label: "Debate", done: debateDone },
    { label: "Voting", done: votingDone },
    { label: vetoed ? "Risk Veto" : "Risk Review", done: reviewDone, danger: vetoed },
    { label: vetoed ? "Blocked" : "Decision", done: decisionDone, danger: vetoed },
  ];
  // The current step is the first not-yet-done one (only while a session runs).
  const activeIdx = hasSession ? steps.findIndex((s) => !s.done) : -1;

  return (
    <div className="flex items-center gap-4 border border-hairline bg-surface px-4 py-2.5">
      <div className="shrink-0">
        <div className="eyebrow">Session</div>
        <div className="font-mono text-sm font-semibold text-text">
          #{sessionNumber(sessionId)}
        </div>
      </div>

      <div className="flex flex-1 items-center">
        {steps.map((step, i) => {
          const isActive = i === activeIdx;
          const color = step.danger ? "#A54B4B" : "#C9A227";
          return (
            <div key={step.label} className="flex flex-1 items-center">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={clsx(
                    "flex h-6 w-6 items-center justify-center rounded-full border transition-colors",
                    step.done ? "border-transparent" : "border-hairline"
                  )}
                  style={step.done ? { background: color, color: "#0F1113" } : undefined}
                >
                  {step.done ? (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 400, damping: 16 }}
                    >
                      <Check size={14} strokeWidth={3} />
                    </motion.span>
                  ) : isActive ? (
                    <span
                      className="h-2 w-2 rounded-full animate-pulse-soft"
                      style={{ background: color }}
                    />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-muted/40" />
                  )}
                </div>
                <span
                  className={clsx(
                    "whitespace-nowrap font-mono text-[10px] uppercase tracking-wide",
                    step.done ? "text-text/80" : isActive ? "text-text" : "text-muted/60"
                  )}
                  style={step.danger && step.done ? { color: "#A54B4B" } : undefined}
                >
                  {step.label}
                </span>
              </div>

              {i < steps.length - 1 && (
                <div className="mx-1 mb-4 h-px flex-1 bg-hairline">
                  <div
                    className="h-full transition-all duration-500"
                    style={{ width: step.done ? "100%" : "0%", background: color }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

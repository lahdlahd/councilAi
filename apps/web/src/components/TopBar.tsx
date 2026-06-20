"use client";

import clsx from "clsx";
import Link from "next/link";
import { useSessionStore } from "@/stores/sessionStore";

const PHASE_LABEL: Record<string, string> = {
  idle: "Standby",
  debating: "In session",
  voting: "Voting",
  decided: "Decision reached",
  blocked: "Decision blocked",
};

export function TopBar({ showJournalLink = true }: { showJournalLink?: boolean }) {
  const connected = useSessionStore((s) => s.connected);
  const symbol = useSessionStore((s) => s.symbol);
  const phase = useSessionStore((s) => s.phase);

  return (
    <header className="flex items-center justify-between border-b border-hairline px-6 py-3">
      <div className="flex items-baseline gap-3">
        <Link href="/" className="font-serif text-2xl font-semibold tracking-tight text-text">
          Council
        </Link>
        <span className="hidden text-[11px] text-muted sm:inline">
          Autonomous AI Investment Committee
        </span>
      </div>

      <div className="flex items-center gap-6">
        <Link href="/room" className="eyebrow transition-colors hover:text-gold" style={{ color: "#C9A227" }}>
          Performance Room ▸
        </Link>
        <Link href="/dashboard" className="eyebrow transition-colors hover:text-gold">
          Portfolio →
        </Link>
        <Link href="/compliance" className="eyebrow transition-colors hover:text-gold">
          Submission →
        </Link>
        <Link
          href={showJournalLink ? "/journal" : "/"}
          className="eyebrow transition-colors hover:text-gold"
        >
          {showJournalLink ? "Trade Journal →" : "← Live Session"}
        </Link>
        <div className="hidden items-center gap-2 md:flex">
          <span className="eyebrow">Subject</span>
          <span className="font-mono text-sm text-gold">{symbol ?? "—"}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="eyebrow">{PHASE_LABEL[phase] ?? phase}</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "h-2 w-2 rounded-full",
              connected ? "bg-positive animate-pulse-soft" : "bg-negative"
            )}
          />
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">
            {connected ? "Live" : "Offline"}
          </span>
        </div>
      </div>
    </header>
  );
}

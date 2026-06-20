"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";
import { AgentRoster } from "@/components/agents/AgentRoster";
import { CouncilChamber } from "@/components/chamber/CouncilChamber";
import { ConfidenceDial } from "@/components/confidence/ConfidenceDial";
import { RecommendationCard } from "@/components/recommendation/RecommendationCard";
import { ReplayBar } from "@/components/replay/ReplayBar";
import { TradeOutcomePanel } from "@/components/replay/TradeOutcomePanel";
import { SessionTimeline } from "@/components/session/SessionTimeline";
import { TopBar } from "@/components/TopBar";
import { VetoOverlay } from "@/components/veto/VetoOverlay";
import { VotePanel } from "@/components/voting/VotePanel";
import { useReplay } from "@/hooks/useReplay";
import { fetchTradeDetail } from "@/lib/api";
import { buildTimeline } from "@/lib/replay";
import type { TradeDetail } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

export default function TradeReplayPage({ params }: { params: Promise<{ tradeId: string }> }) {
  const { tradeId } = use(params);
  const [detail, setDetail] = useState<TradeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTradeDetail(tradeId)
      .then(setDetail)
      .catch((e) => setError(String(e)));
  }, [tradeId]);

  const steps = useMemo(() => (detail?.session ? buildTimeline(detail.session) : []), [detail]);
  const replay = useReplay(steps);

  // The trade outcome is revealed once the decision (recommendation) is reached.
  const recommendation = useSessionStore((s) => s.recommendation);
  const outcomeRevealed = recommendation !== null || replay.finished;

  return (
    <div className="flex h-screen flex-col">
      <TopBar showJournalLink={false} />

      <div className="flex items-center justify-between gap-4 px-4 pt-4">
        <Link href={`/trade/${tradeId}`} className="eyebrow transition-colors hover:text-gold">
          ← Trade details
        </Link>
        <span className="eyebrow">
          Decision Replay{detail?.trade ? ` · ${detail.trade.symbol}` : ""}
          {detail?.trade ? ` · ${detail.trade.direction.toUpperCase()}` : ""}
        </span>
      </div>

      <div className="px-4 pt-3">
        <ReplayBar
          playing={replay.playing}
          finished={replay.finished}
          progress={replay.progress}
          speed={replay.speed}
          total={replay.total}
          index={replay.index}
          onToggle={replay.toggle}
          onRestart={replay.restart}
          onSeek={replay.seek}
          onSpeed={replay.setSpeed}
        />
      </div>

      {error && <p className="px-6 pt-4 font-mono text-xs text-negative">Could not load ({error}).</p>}
      {detail && !detail.session && (
        <p className="px-6 pt-4 font-mono text-xs text-muted">
          The full council record for this trade isn&apos;t available to replay — showing the outcome only.
        </p>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[260px_minmax(0,1fr)_320px]">
        <div className="hidden min-h-0 overflow-y-auto lg:block">
          <AgentRoster />
        </div>

        <div className="flex min-h-0 flex-col gap-4">
          <SessionTimeline />
          <div className="min-h-0 flex-1">
            <CouncilChamber />
          </div>
        </div>

        <div className="hidden min-h-0 flex-col gap-4 overflow-y-auto lg:flex">
          <ConfidenceDial />
          <VotePanel />
          <RecommendationCard />
          {detail?.trade && <TradeOutcomePanel trade={detail.trade} revealed={outcomeRevealed} />}
        </div>
      </main>

      <VetoOverlay />
    </div>
  );
}

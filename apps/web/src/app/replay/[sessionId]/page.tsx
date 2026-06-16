"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";
import { AgentRoster } from "@/components/agents/AgentRoster";
import { CouncilChamber } from "@/components/chamber/CouncilChamber";
import { ConfidenceDial } from "@/components/confidence/ConfidenceDial";
import { RecommendationCard } from "@/components/recommendation/RecommendationCard";
import { ReplayBar } from "@/components/replay/ReplayBar";
import { TopBar } from "@/components/TopBar";
import { VetoOverlay } from "@/components/veto/VetoOverlay";
import { VotePanel } from "@/components/voting/VotePanel";
import { useReplay } from "@/hooks/useReplay";
import { fetchJournalEntry } from "@/lib/api";
import { buildTimeline } from "@/lib/replay";
import type { JournalEntry } from "@/lib/types";

export default function ReplayPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const [entry, setEntry] = useState<JournalEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJournalEntry(sessionId)
      .then(setEntry)
      .catch((e) => setError(String(e)));
  }, [sessionId]);

  const steps = useMemo(() => (entry ? buildTimeline(entry) : []), [entry]);
  const replay = useReplay(steps);

  return (
    <div className="flex h-screen flex-col">
      <TopBar showJournalLink={false} />

      <div className="flex items-center justify-between gap-4 px-4 pt-4">
        <Link href={`/journal/${sessionId}`} className="eyebrow transition-colors hover:text-gold">
          ← Decision detail
        </Link>
        <span className="eyebrow">
          Replay{entry ? ` · ${entry.symbol}` : ""} · {new Date(entry?.startedAt ?? Date.now()).toLocaleString()}
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

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[260px_minmax(0,1fr)_320px]">
        <div className="hidden min-h-0 overflow-y-auto lg:block">
          <AgentRoster />
        </div>
        <div className="min-h-0">
          <CouncilChamber />
        </div>
        <div className="hidden min-h-0 flex-col gap-4 overflow-y-auto lg:flex">
          <ConfidenceDial />
          <VotePanel />
          <RecommendationCard />
        </div>
      </main>

      <VetoOverlay />
    </div>
  );
}

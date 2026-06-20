"use client";

import { AgentRoster } from "@/components/agents/AgentRoster";
import { CouncilChamber } from "@/components/chamber/CouncilChamber";
import { ConfidenceDial } from "@/components/confidence/ConfidenceDial";
import { ConveneControls } from "@/components/convene/ConveneControls";
import { TradeLedger } from "@/components/ledger/TradeLedger";
import { MarketPanel } from "@/components/market/MarketPanel";
import { PriceChart } from "@/components/market/PriceChart";
import { RecommendationCard } from "@/components/recommendation/RecommendationCard";
import { SessionTimeline } from "@/components/session/SessionTimeline";
import { TopBar } from "@/components/TopBar";
import { VetoOverlay } from "@/components/veto/VetoOverlay";
import { VotePanel } from "@/components/voting/VotePanel";
import { useCouncilStream } from "@/hooks/useStreams";

export default function Home() {
  useCouncilStream();

  return (
    <div className="flex h-screen flex-col">
      <TopBar />

      {/* Control-room grid: roster · chamber · instruments. */}
      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-4 pb-12 lg:grid-cols-[260px_minmax(0,1fr)_320px]">
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
          <ConveneControls />
          <MarketPanel />
          <PriceChart />
          <ConfidenceDial />
          <VotePanel />
          <RecommendationCard />
        </div>
      </main>

      <VetoOverlay />
      <TradeLedger />
    </div>
  );
}

import { create } from "zustand";
import type { PaperTrade } from "../lib/types";

// A lightweight real-time feed of executed paper trades, fed by the
// "paper.trade" WebSocket event. `tick` bumps on every new trade so consumers
// (the Trade Ledger) can react instantly without polling.
interface TradeFeedState {
  lastTrade: PaperTrade | null;
  tick: number;
  push: (trade: PaperTrade) => void;
}

export const useTradeFeed = create<TradeFeedState>((set) => ({
  lastTrade: null,
  tick: 0,
  push: (trade) => set((s) => ({ lastTrade: trade, tick: s.tick + 1 })),
}));

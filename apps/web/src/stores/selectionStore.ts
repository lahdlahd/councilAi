import { create } from "zustand";
import type { MarketType } from "@/lib/types";

// The instrument the user is currently looking at / about to convene the council on.
// Shared by the market panel, the chart, and (later) the convene controls.
interface SelectionState {
  symbol: string;
  market: MarketType;
  setSymbol: (s: string) => void;
  setMarket: (m: MarketType) => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  symbol: "BTCUSDT",
  market: "spot",
  setSymbol: (symbol) => set({ symbol }),
  setMarket: (market) => set({ market }),
}));

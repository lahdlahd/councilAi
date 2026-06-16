import { create } from "zustand";
import type { MarketSnapshot, WsEvent } from "../lib/types";

interface MarketState {
  bySymbol: Record<string, MarketSnapshot>;
  degraded: boolean;
  apply: (e: WsEvent) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  bySymbol: {},
  degraded: false,
  apply: (e) =>
    set((s) => {
      if (e.type === "market.tick") {
        return { bySymbol: { ...s.bySymbol, [e.snapshot.symbol]: e.snapshot } };
      }
      if (e.type === "connection.status") {
        return { degraded: e.state === "degraded" };
      }
      return {};
    }),
}));

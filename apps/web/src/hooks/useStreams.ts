"use client";

import { useCallback, useEffect } from "react";
import { openCouncilSocket } from "../lib/ws/client";
import type { WsEvent } from "../lib/types";
import { useMarketStore } from "../stores/marketStore";
import { useSessionStore } from "../stores/sessionStore";
import { useTradeFeed } from "../stores/tradeFeedStore";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export function useCouncilStream() {
  const apply = useSessionStore((s) => s.apply);
  const setConnected = useSessionStore((s) => s.setConnected);
  const pushTrade = useTradeFeed((s) => s.push);

  // Drive the session store, and fan out trade-created events to the live feed
  // so the Trade Ledger updates the instant a trade is executed (no refresh).
  const onEvent = useCallback(
    (e: WsEvent) => {
      apply(e);
      if (e.type === "paper.trade") pushTrade(e.trade);
    },
    [apply, pushTrade]
  );

  useEffect(() => {
    return openCouncilSocket({
      url: `${WS_BASE}/ws/council`,
      onEvent,
      onStatus: setConnected,
    });
  }, [onEvent, setConnected]);
}

export function useMarketStream() {
  const apply = useMarketStore((s) => s.apply);
  useEffect(() => {
    return openCouncilSocket({ url: `${WS_BASE}/ws/market`, onEvent: apply });
  }, [apply]);
}

"use client";

import { useEffect } from "react";
import { openCouncilSocket } from "../lib/ws/client";
import { useMarketStore } from "../stores/marketStore";
import { useSessionStore } from "../stores/sessionStore";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export function useCouncilStream() {
  const apply = useSessionStore((s) => s.apply);
  const setConnected = useSessionStore((s) => s.setConnected);

  useEffect(() => {
    return openCouncilSocket({
      url: `${WS_BASE}/ws/council`,
      onEvent: apply,
      onStatus: setConnected,
    });
  }, [apply, setConnected]);
}

export function useMarketStream() {
  const apply = useMarketStore((s) => s.apply);
  useEffect(() => {
    return openCouncilSocket({ url: `${WS_BASE}/ws/market`, onEvent: apply });
  }, [apply]);
}

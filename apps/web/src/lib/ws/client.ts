import type { WsEvent } from "../types";

// A minimal reconnecting WebSocket that decodes the server's JSON envelope and
// hands typed events to a callback. Exponential backoff, clean teardown.
export interface CouncilSocketOptions {
  url: string;
  onEvent: (event: WsEvent) => void;
  onStatus?: (connected: boolean) => void;
}

export function openCouncilSocket(opts: CouncilSocketOptions): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let backoff = 500;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    if (closed) return;
    ws = new WebSocket(opts.url);

    ws.onopen = () => {
      backoff = 500;
      opts.onStatus?.(true);
    };
    ws.onmessage = (ev) => {
      try {
        opts.onEvent(JSON.parse(ev.data) as WsEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      opts.onStatus?.(false);
      if (closed) return;
      reconnectTimer = setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 8000);
    };
    ws.onerror = () => ws?.close();
  };

  connect();

  return () => {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    ws?.close();
  };
}

"use client";

import { useEffect, useRef } from "react";
import { useSessionStore } from "@/stores/sessionStore";
import { AgentMessage } from "./AgentMessage";
import { TypingIndicator } from "./TypingIndicator";

export function CouncilChamber() {
  const messages = useSessionStore((s) => s.messages);
  const thinking = useSessionStore((s) => s.thinking);
  const symbol = useSessionStore((s) => s.symbol);
  const connected = useSessionStore((s) => s.connected);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-follow the debate as tokens stream in.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking]);

  return (
    <section className="flex min-h-0 flex-col border border-hairline bg-surface/60 shadow-panel">
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <div>
          <div className="eyebrow">Council Chamber</div>
          <h1 className="font-serif text-lg text-text">
            Live Council Session{symbol ? ` — ${symbol}` : ""}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-gold animate-pulse-soft" />
          <span className="eyebrow">Streaming</span>
        </div>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5">
        {messages.length === 0 && !thinking && (
          <div className="flex h-full items-center justify-center text-center">
            <p className="max-w-sm font-mono text-xs uppercase tracking-wider text-muted">
              {connected ? "Convening the committee…" : "Connecting to the council floor…"}
            </p>
          </div>
        )}

        {messages.map((m) => (
          <AgentMessage key={m.messageId} message={m} />
        ))}

        {thinking && <TypingIndicator agentId={thinking} />}
      </div>
    </section>
  );
}

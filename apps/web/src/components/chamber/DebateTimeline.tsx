"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AGENT_ACCENT, profileFor } from "@/lib/agents";
import type { AgentId } from "@/lib/types";
import { useSessionStore } from "@/stores/sessionStore";

// The role each agent plays the first time they speak in a round.
const ROLE_VERB: Record<AgentId, string> = {
  technical: "opens",
  news: "responds",
  quant: "challenges",
  risk: "reviews",
  execution: "summarizes",
};

export function DebateTimeline() {
  const messages = useSessionStore((s) => s.messages);
  const thinking = useSessionStore((s) => s.thinking);
  const connected = useSessionStore((s) => s.connected);

  const [open, setOpen] = useState<Record<string, boolean>>({});
  const scrollRef = useRef<HTMLDivElement>(null);

  // Assign each message a verb: role verb on first appearance, else "continues".
  const entries = useMemo(() => {
    const seen = new Set<AgentId>();
    return messages.map((m) => {
      const verb = seen.has(m.agentId) ? "continues" : ROLE_VERB[m.agentId] ?? "notes";
      seen.add(m.agentId);
      return { m, verb };
    });
  }, [messages]);

  const lastId = messages[messages.length - 1]?.messageId;

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking]);

  const isOpen = (id: string, streaming: boolean) =>
    streaming || (open[id] ?? id === lastId);

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto border border-hairline bg-surface/60 px-4 py-3">
      {entries.length === 0 ? (
        <div className="flex h-full items-center justify-center">
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted">
            {connected ? "The committee will convene here…" : "Connecting to the council floor…"}
          </p>
        </div>
      ) : (
        <div className="ml-1 border-l border-hairline">
          {entries.map(({ m, verb }) => {
            const accent = AGENT_ACCENT[m.agentId];
            const p = profileFor(m.agentId);
            const expanded = isOpen(m.messageId, m.streaming);
            return (
              <div key={m.messageId} className="relative pl-5">
                <span
                  className="absolute -left-[5px] top-2 h-2.5 w-2.5 rounded-full border-2"
                  style={{ background: "#181C20", borderColor: accent }}
                />
                <button
                  onClick={() => setOpen((o) => ({ ...o, [m.messageId]: !expanded }))}
                  className="flex w-full items-center gap-2 py-2 text-left"
                >
                  {expanded ? (
                    <ChevronDown size={13} className="shrink-0 text-muted" />
                  ) : (
                    <ChevronRight size={13} className="shrink-0 text-muted" />
                  )}
                  <span aria-hidden>{p.avatar}</span>
                  <span className="font-mono text-xs font-semibold" style={{ color: accent }}>
                    {p.name}
                  </span>
                  <span className="eyebrow">{verb}</span>
                  {!expanded && (
                    <span className="ml-1 truncate font-mono text-[11px] text-muted">— {m.text.slice(0, 64)}…</span>
                  )}
                </button>
                {expanded && (
                  <div className="pb-3 pl-5">
                    {m.references.length > 0 && (
                      <div className="mb-1 font-mono text-[10px] text-muted">
                        ↳ to {m.references.map((r) => profileFor(r).name.split(" ")[0]).join(", ")}
                      </div>
                    )}
                    <p className={`max-w-[60ch] text-[13px] leading-relaxed text-text/85 ${m.streaming ? "caret" : ""}`}>
                      {m.text}
                    </p>
                  </div>
                )}
              </div>
            );
          })}

          {thinking && (
            <div className="relative pl-5">
              <span className="absolute -left-[5px] top-2 h-2.5 w-2.5 animate-pulse-soft rounded-full" style={{ background: AGENT_ACCENT[thinking] }} />
              <div className="flex items-center gap-2 py-2">
                <span aria-hidden>{profileFor(thinking).avatar}</span>
                <span className="font-mono text-xs font-semibold" style={{ color: AGENT_ACCENT[thinking] }}>
                  {profileFor(thinking).name}
                </span>
                <span className="eyebrow animate-pulse-soft">is deliberating…</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

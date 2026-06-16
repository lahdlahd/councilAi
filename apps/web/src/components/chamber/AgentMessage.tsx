"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import { AGENT_ACCENT, profileFor } from "@/lib/agents";
import type { ChamberMessage } from "@/stores/sessionStore";

const STANCE_LABEL: Record<string, string> = {
  opening: "opens",
  agree: "agrees",
  disagree: "disagrees",
  challenge: "challenges",
  neutral: "notes",
};

export function AgentMessage({ message }: { message: ChamberMessage }) {
  const accent = AGENT_ACCENT[message.agentId];
  const profile = profileFor(message.agentId);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="border-l border-hairline pl-4"
      style={{ borderLeftColor: `${accent}40` }}
    >
      <div className="flex items-center gap-2">
        <span aria-hidden style={{ color: accent }}>
          {profile.avatar}
        </span>
        <span className="text-[13px] font-semibold" style={{ color: accent }}>
          {profile.name}
        </span>
        <span className="eyebrow">{STANCE_LABEL[message.stance] ?? message.stance}</span>
        {message.references.length > 0 && (
          <span className="font-mono text-[10px] text-muted">
            ↳ {message.references.map((r) => profileFor(r).name.split(" ")[0]).join(", ")}
          </span>
        )}
      </div>

      <p
        className={clsx(
          "mt-1 max-w-[62ch] text-[15px] leading-relaxed text-text/90",
          message.streaming && "caret"
        )}
      >
        {message.text}
      </p>
    </motion.div>
  );
}

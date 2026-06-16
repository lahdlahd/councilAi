"use client";

import clsx from "clsx";
import { Pause, Play, RotateCcw } from "lucide-react";

interface Props {
  playing: boolean;
  finished: boolean;
  progress: number;
  speed: number;
  total: number;
  index: number;
  onToggle: () => void;
  onRestart: () => void;
  onSeek: (n: number) => void;
  onSpeed: (s: number) => void;
}

const SPEEDS = [1, 2, 4];

export function ReplayBar({
  playing,
  finished,
  progress,
  speed,
  total,
  index,
  onToggle,
  onRestart,
  onSeek,
  onSpeed,
}: Props) {
  return (
    <div className="flex items-center gap-4 border border-hairline bg-surface px-4 py-3">
      <button
        onClick={finished ? onRestart : onToggle}
        className="flex h-9 w-9 items-center justify-center border border-gold/50 text-gold transition-colors hover:bg-gold/10"
        aria-label={finished ? "Replay" : playing ? "Pause" : "Play"}
      >
        {finished ? <RotateCcw size={16} /> : playing ? <Pause size={16} /> : <Play size={16} />}
      </button>

      <button
        onClick={onRestart}
        className="text-muted transition-colors hover:text-text"
        aria-label="Restart"
      >
        <RotateCcw size={15} />
      </button>

      {/* Scrubber */}
      <input
        type="range"
        min={0}
        max={total}
        value={index}
        onChange={(e) => onSeek(Number(e.target.value))}
        className="h-1 flex-1 cursor-pointer appearance-none bg-surface-2 accent-gold"
        style={{
          background: `linear-gradient(to right, #C9A227 ${progress * 100}%, #1F242A ${progress * 100}%)`,
        }}
      />

      <span className="eyebrow tabular-nums">{Math.round(progress * 100)}%</span>

      <div className="flex items-center gap-1">
        {SPEEDS.map((s) => (
          <button
            key={s}
            onClick={() => onSpeed(s)}
            className={clsx(
              "px-2 py-1 font-mono text-[11px] transition-colors",
              speed === s ? "text-gold" : "text-muted hover:text-text"
            )}
          >
            {s}×
          </button>
        ))}
      </div>
    </div>
  );
}

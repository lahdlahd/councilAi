"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReplayStep } from "@/lib/replay";
import { useSessionStore } from "@/stores/sessionStore";

// Drives the (live) session store from a recorded timeline on a local clock.
// Reuses the exact same store + components as the live session — replay is just a
// different event source. Supports play/pause, speed, restart, and scrubbing.
export function useReplay(steps: ReplayStep[]) {
  const apply = useSessionStore((s) => s.apply);
  const reset = useSessionStore((s) => s.reset);

  const [index, setIndex] = useState(0); // next step to apply
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const total = steps.length;

  const clearTimer = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  // Apply steps [0, n) instantly — used for seeking and initial reset.
  const applyUpTo = useCallback(
    (n: number) => {
      reset();
      for (let i = 0; i < n; i++) apply(steps[i].event);
    },
    [apply, reset, steps]
  );

  const seek = useCallback(
    (n: number) => {
      clearTimer();
      const target = Math.max(0, Math.min(total, n));
      applyUpTo(target);
      setIndex(target);
      setPlaying(false);
    },
    [applyUpTo, total]
  );

  const restart = useCallback(() => {
    clearTimer();
    applyUpTo(0);
    setIndex(0);
    setPlaying(true);
  }, [applyUpTo]);

  // Initialize on mount / when the timeline changes: seed and autoplay.
  useEffect(() => {
    applyUpTo(0);
    setIndex(0);
    setPlaying(true);
    return clearTimer;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [steps]);

  // The playback loop.
  useEffect(() => {
    if (!playing) {
      clearTimer();
      return;
    }
    if (index >= total) {
      setPlaying(false);
      return;
    }
    const step = steps[index];
    apply(step.event);
    timer.current = setTimeout(
      () => setIndex((i) => i + 1),
      Math.max(0, step.delayAfter) / speed
    );
    return clearTimer;
  }, [playing, index, total, speed, steps, apply]);

  return {
    index,
    total,
    playing,
    speed,
    progress: total ? index / total : 0,
    finished: index >= total,
    play: () => setPlaying(true),
    pause: () => setPlaying(false),
    toggle: () => setPlaying((p) => !p),
    restart,
    seek,
    setSpeed,
  };
}

import { useEffect, useState } from "react";

/** Whole seconds since `active` last turned true; 0 while inactive. Ticks once a second. */
export function useElapsed(active: boolean): number {
  const [start, setStart] = useState<number | null>(null);
  const [now, setNow] = useState(0);

  useEffect(() => {
    if (!active) {
      setStart(null);
      return;
    }
    const t0 = Date.now();
    setStart(t0);
    setNow(t0);
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);

  return active && start != null ? Math.max(0, Math.floor((now - start) / 1000)) : 0;
}

/** 75 → "1:15"; 3725 → "1:02:05". */
export function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** Elapsed time worth showing: hidden for the first few seconds so quick jobs don't flicker a clock. */
export const SHOW_ELAPSED_AFTER = 3;

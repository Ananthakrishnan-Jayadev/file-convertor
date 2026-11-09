import { useLayoutEffect, useRef, useState } from "react";
import { humanSize } from "./format";

type Props = {
  input: number;
  output: number | null;
  limit: number | null;
  met: boolean | null;
  /** The job this result belongs to. With it, the result bar shrinks into place the first
   *  time the result shows up; without it, the bar simply appears at its size. */
  playKey?: string;
};

// Results that have already played their landing, so a remount or re-render never replays it.
const played = new Set<string>();

// The landing: a short hold on the original length, then one confident ease-out to the result.
const HOLD_MS = 80;
const LAND_MS = 760;
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];
// The summary's settle (styles.css, meter-settle: 560ms delay + 340ms) ends this long after the bar.
const SETTLE_TAIL_MS = 560 + 340 - (HOLD_MS + LAND_MS);

/** One shared scale: the original as a faint bar, the result as a solid bar, the limit as a marker. */
export default function SizeMeter({ input, output, limit, met, playKey }: Props) {
  const max = Math.max(input, output ?? 0, limit ?? 0) * 1.08 || 1;
  const at = (n: number) => Math.max(0.6, (n / max) * 100);
  const pct = (n: number) => `${at(n)}%`;
  const over = limit != null && input > limit && output == null;
  // Keep the limit label inside the card: centred on the marker in the middle,
  // starting at the marker near the left edge, ending at it near the right edge.
  const limitPct = limit != null ? at(limit) : 0;
  const labelSide = limitPct < 30 ? "at-start" : limitPct > 70 ? "at-end" : "at-centre";
  const labelStyle = labelSide === "at-end" ? { right: `${100 - limitPct}%` } : { left: `${limitPct}%` };

  // Decided during render, so the summary that follows the meter can settle in step with it
  // from its very first frame. The set is only written in the effect, which keeps this pure.
  const landing = useRef<string | null>(null);
  if (output != null && playKey != null && !played.has(playKey) && landing.current !== playKey) {
    landing.current = playKey;
  }
  const isLanding = output != null && playKey != null && landing.current === playKey;
  // Set once the landing is over (or skipped). The class then comes off, so showing a hidden
  // panel again, which restarts CSS animations, cannot replay the summary's fade.
  const [landed, setLanded] = useState(false);

  // The result bar is laid out as long as the longer of original and result, and clipped
  // back to the result. Shrinking it is then a clip-path change: no width, no layout.
  const startPct = at(input);
  const endPct = output != null ? at(output) : 0;
  const boxPct = Math.max(startPct, endPct);
  const clipAt = (x: number) => `inset(0 ${(1 - x / boxPct) * 100}% 0 0 round 7px)`;

  const barRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const bar = barRef.current;
    if (!isLanding || !bar || playKey == null) return;
    played.add(playKey);
    if (typeof bar.animate !== "function" || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setLanded(true);
      return;
    }

    const timing = { duration: LAND_MS, delay: HOLD_MS, fill: "backwards" as const };
    const shrink = bar.animate([{ clipPath: clipAt(startPct) }, { clipPath: clipAt(endPct) }], {
      ...timing,
      easing: `cubic-bezier(${EASE.join(", ")})`,
    });
    let tail: number | undefined;
    shrink.onfinish = () => {
      tail = window.setTimeout(() => setLanded(true), Math.max(0, SETTLE_TAIL_MS));
    };

    // The colour turns at the moment the bar passes the limit line, not before or after.
    const css = getComputedStyle(bar);
    const ok = css.getPropertyValue("--ok").trim();
    const bad = css.getPropertyValue("--bad").trim();
    const from = limit != null && startPct > limitPct ? bad : ok;
    const to = met === false ? bad : ok;
    let turn: Animation | null = null;
    if (from && to && from !== to) {
      const travelled = startPct === endPct ? 1 : (startPct - limitPct) / (startPct - endPct);
      const t = timeAtProgress(Math.min(1, Math.max(0, travelled)));
      turn = bar.animate(
        [
          { backgroundColor: from, offset: 0 },
          { backgroundColor: from, offset: Math.max(0, t - 0.04) },
          { backgroundColor: to, offset: Math.min(1, t + 0.04) },
          { backgroundColor: to, offset: 1 },
        ],
        { ...timing, easing: "linear" },
      );
    }

    return () => {
      shrink.onfinish = null;
      shrink.cancel();
      turn?.cancel();
      window.clearTimeout(tail);
    };
    // Runs once per landing; the sizes for a finished job don't change.
  }, [isLanding, playKey]);

  const description = [
    `Original ${humanSize(input)}`,
    output != null && `result ${humanSize(output)}`,
    limit != null && `limit ${humanSize(limit)}`,
    limit != null && output != null && met === true && "under the limit",
    limit != null && output != null && met === false && "over the limit",
    over && "the original is over the limit",
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div className={`meter${isLanding && !landed ? " is-landing" : ""}`} role="img" aria-label={description}>
      <div className="meter-track">
        <div className={`meter-bar meter-input${over ? " is-over" : ""}`} style={{ width: pct(input) }} />
        {output != null && (
          <div
            ref={barRef}
            className={`meter-bar meter-output${met === false ? " is-missed" : ""}`}
            style={{ width: `${boxPct}%`, clipPath: clipAt(endPct) }}
          />
        )}
        {limit != null && <div className="meter-limit" style={{ left: pct(limit) }} />}
      </div>
      {limit != null && (
        <div className={`meter-limit-label ${labelSide}`} style={labelStyle}>
          {humanSize(limit)} limit
        </div>
      )}
    </div>
  );
}

/** For the landing's easing curve, the share of the duration at which the bar has covered
 *  `progress` of its distance. Lets the colour turn exactly as the bar crosses the limit. */
function timeAtProgress(progress: number): number {
  const [x1, y1, x2, y2] = EASE;
  const coord = (s: number, a: number, b: number) => 3 * a * s * (1 - s) ** 2 + 3 * b * s * s * (1 - s) + s ** 3;
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 24; i++) {
    const mid = (lo + hi) / 2;
    if (coord(mid, y1, y2) < progress) lo = mid;
    else hi = mid;
  }
  return coord((lo + hi) / 2, x1, x2);
}

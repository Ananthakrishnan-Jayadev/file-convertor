import { type KeyboardEvent, useRef } from "react";

export type SegOption<K extends string | number> = { key: K; label: string };

type Props<K extends string | number> = {
  /** Id of the visible label (the fieldset's legend) that names the group. */
  labelledBy: string;
  options: readonly SegOption<K>[];
  /** The chosen option, or null when none is. */
  value: K | null;
  onChange: (key: K) => void;
};

/**
 * A single choice shown as a row of buttons. Behaves like a radio group: one Tab stop,
 * and the arrow keys, Home and End move the choice along it.
 */
export default function Segmented<K extends string | number>({ labelledBy, options, value, onChange }: Props<K>) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const chosen = options.findIndex((o) => o.key === value);
  const tabStop = chosen === -1 ? 0 : chosen;

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, i: number) {
    const last = options.length - 1;
    let next: number;
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        next = i === last ? 0 : i + 1;
        break;
      case "ArrowLeft":
      case "ArrowUp":
        next = i === 0 ? last : i - 1;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = last;
        break;
      default:
        return;
    }
    e.preventDefault();
    buttons.current[next]?.focus();
    onChange(options[next].key);
  }

  return (
    <div className="segmented" role="radiogroup" aria-labelledby={labelledBy}>
      {options.map((o, i) => (
        <button
          key={o.key}
          ref={(el) => {
            buttons.current[i] = el;
          }}
          type="button"
          role="radio"
          aria-checked={o.key === value}
          tabIndex={i === tabStop ? 0 : -1}
          className={o.key === value ? "seg is-on" : "seg"}
          onClick={() => onChange(o.key)}
          onKeyDown={(e) => onKeyDown(e, i)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

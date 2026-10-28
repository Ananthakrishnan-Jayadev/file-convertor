import { useState } from "react";

const PRESETS: { label: string; kb: number | null }[] = [
  { label: "No limit", kb: null },
  { label: "Under 5 MB", kb: 5 * 1024 },
  { label: "Under 1 MB", kb: 1024 },
  { label: "Under 500 KB", kb: 500 },
];
const MIN_KB = 10;

type Props = { value: number | null; onChange: (kb: number | null) => void };

export default function SizeLimitPicker({ value, onChange }: Props) {
  const isPreset = PRESETS.some((p) => p.kb === value);
  const [custom, setCustom] = useState(!isPreset);
  const [amount, setAmount] = useState("200");
  const [unit, setUnit] = useState<"KB" | "MB">("KB");

  function applyCustom(nextAmount: string, nextUnit: "KB" | "MB") {
    setAmount(nextAmount);
    setUnit(nextUnit);
    const n = Number(nextAmount);
    const kb = Math.round(nextUnit === "MB" ? n * 1024 : n);
    if (Number.isFinite(n) && kb >= MIN_KB) onChange(kb);
  }

  const customKb = Math.round(unit === "MB" ? Number(amount) * 1024 : Number(amount));
  const customInvalid = custom && !(customKb >= MIN_KB);

  return (
    <fieldset className="field size-limit">
      <legend className="field-label">Size limit</legend>
      <div className="segmented" role="radiogroup">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            role="radio"
            aria-checked={!custom && value === p.kb}
            className={!custom && value === p.kb ? "seg is-on" : "seg"}
            onClick={() => {
              setCustom(false);
              onChange(p.kb);
            }}
          >
            {p.label}
          </button>
        ))}
        <button
          role="radio"
          aria-checked={custom}
          className={custom ? "seg is-on" : "seg"}
          onClick={() => {
            setCustom(true);
            applyCustom(amount, unit);
          }}
        >
          Custom
        </button>
      </div>
      {custom && (
        <div className="custom-limit">
          <label>
            <span className="visually-hidden">Custom size limit</span>
            <input
              type="number"
              min={unit === "MB" ? 0.01 : MIN_KB}
              step="any"
              value={amount}
              aria-invalid={customInvalid}
              onChange={(e) => applyCustom(e.target.value, unit)}
            />
          </label>
          <select value={unit} onChange={(e) => applyCustom(amount, e.target.value as "KB" | "MB")} aria-label="Unit">
            <option>KB</option>
            <option>MB</option>
          </select>
          {customInvalid && <span className="status-error">Use at least {MIN_KB} KB.</span>}
        </div>
      )}
    </fieldset>
  );
}

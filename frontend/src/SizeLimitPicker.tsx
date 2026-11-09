import { useEffect, useId, useState } from "react";
import Segmented from "./Segmented";

const PRESETS: { key: string; label: string; kb: number | null }[] = [
  { key: "none", label: "No limit", kb: null },
  { key: "5mb", label: "Under 5 MB", kb: 5 * 1024 },
  { key: "1mb", label: "Under 1 MB", kb: 1024 },
  { key: "500kb", label: "Under 500 KB", kb: 500 },
];
const CUSTOM = "custom";
const OPTIONS = [...PRESETS.map(({ key, label }) => ({ key, label })), { key: CUSTOM, label: "Custom" }];
const MIN_KB = 10;

type Props = {
  value: number | null;
  onChange: (kb: number | null) => void;
  /** Told whether the limit as typed can be used, so the tool can hold its button until it can. */
  onValidChange?: (valid: boolean) => void;
  hint?: string;
};

export default function SizeLimitPicker({ value, onChange, onValidChange, hint }: Props) {
  const isPreset = PRESETS.some((p) => p.kb === value);
  const [custom, setCustom] = useState(!isPreset);
  const [amount, setAmount] = useState("200");
  const [unit, setUnit] = useState<"KB" | "MB">("KB");
  const ids = useId();
  const labelId = `${ids}-label`;
  const errorId = `${ids}-error`;

  function applyCustom(nextAmount: string, nextUnit: "KB" | "MB") {
    setAmount(nextAmount);
    setUnit(nextUnit);
    const n = Number(nextAmount);
    const kb = Math.round(nextUnit === "MB" ? n * 1024 : n);
    if (Number.isFinite(n) && kb >= MIN_KB) onChange(kb);
  }

  function choose(key: string) {
    if (key === CUSTOM) {
      setCustom(true);
      applyCustom(amount, unit);
      return;
    }
    setCustom(false);
    onChange(PRESETS.find((p) => p.key === key)?.kb ?? null);
  }

  const customKb = Math.round(unit === "MB" ? Number(amount) * 1024 : Number(amount));
  const customInvalid = custom && !(customKb >= MIN_KB);

  useEffect(() => {
    onValidChange?.(!customInvalid);
  }, [customInvalid, onValidChange]);

  const chosen = custom ? CUSTOM : (PRESETS.find((p) => p.kb === value)?.key ?? null);

  return (
    <fieldset className="field size-limit">
      <legend id={labelId} className="field-label">
        Size limit
      </legend>
      <Segmented labelledBy={labelId} options={OPTIONS} value={chosen} onChange={choose} />
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
              aria-describedby={customInvalid ? errorId : undefined}
              onChange={(e) => applyCustom(e.target.value, unit)}
            />
          </label>
          <select value={unit} onChange={(e) => applyCustom(amount, e.target.value as "KB" | "MB")} aria-label="Unit">
            <option>KB</option>
            <option>MB</option>
          </select>
          {customInvalid && (
            <span id={errorId} className="status-error">
              Use at least {MIN_KB} KB.
            </span>
          )}
        </div>
      )}
      {hint && <p className="hint">{hint}</p>}
    </fieldset>
  );
}

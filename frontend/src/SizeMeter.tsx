import { humanSize } from "./format";

type Props = {
  input: number;
  output: number | null;
  limit: number | null;
  met: boolean | null;
};

/** One shared scale: the original as a faint bar, the result as a solid bar, the limit as a marker. */
export default function SizeMeter({ input, output, limit, met }: Props) {
  const max = Math.max(input, output ?? 0, limit ?? 0) * 1.08 || 1;
  const pct = (n: number) => `${Math.max(0.6, (n / max) * 100)}%`;
  const over = limit != null && input > limit && output == null;

  const description = [
    `Original ${humanSize(input)}`,
    output != null && `result ${humanSize(output)}`,
    limit != null && `limit ${humanSize(limit)}`,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div className="meter" role="img" aria-label={description}>
      <div className="meter-track">
        <div className={`meter-bar meter-input${over ? " is-over" : ""}`} style={{ width: pct(input) }} />
        {output != null && (
          <div className={`meter-bar meter-output${met === false ? " is-missed" : ""}`} style={{ width: pct(output) }} />
        )}
        {limit != null && <div className="meter-limit" style={{ left: pct(limit) }} />}
      </div>
      {limit != null && (
        <div className="meter-limit-label" style={{ left: pct(limit) }}>
          {humanSize(limit)} limit
        </div>
      )}
    </div>
  );
}

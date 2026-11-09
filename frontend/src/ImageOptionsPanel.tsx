import { useId } from "react";
import { DEFAULT_IMAGE_OPTIONS, ImageOptions } from "./api";
import Segmented, { type SegOption } from "./Segmented";

type Props = { value: ImageOptions; onChange: (next: ImageOptions) => void; imageCount: number };

type ResizeMode = "none" | "scale" | "fit";

const ROTATIONS: { label: string; deg: ImageOptions["rotate"] }[] = [
  { label: "None", deg: 0 },
  { label: "90° right", deg: 90 },
  { label: "180°", deg: 180 },
  { label: "90° left", deg: 270 },
];

const RESIZE_MODES: SegOption<ResizeMode>[] = [
  { key: "none", label: "Original size" },
  { key: "scale", label: "Percentage" },
  { key: "fit", label: "Fit inside a box" },
];

const ROTATE_OPTIONS: SegOption<ImageOptions["rotate"]>[] = ROTATIONS.map((r) => ({ key: r.deg, label: r.label }));

function resizeMode(o: ImageOptions): ResizeMode {
  if (o.scale) return "scale";
  if (o.width || o.height) return "fit";
  return "none";
}

/** Plain-language list of what's changed, shown on the collapsed panel. */
function summary(o: ImageOptions): string {
  const parts: string[] = [];
  if (o.scale) parts.push(`${o.scale}% size`);
  else if (o.width || o.height) parts.push(`fit in ${o.width ?? "any"} × ${o.height ?? "any"} px`);
  if (o.rotate) parts.push(`rotate ${ROTATIONS.find((r) => r.deg === o.rotate)!.label}`);
  if (o.quality) parts.push(`quality ${o.quality}`);
  if (o.keepMetadata) parts.push("keep photo details");
  return parts.length ? parts.join(", ") : "No changes";
}

const toNumber = (text: string) => (text.trim() === "" ? null : Math.max(1, Math.round(Number(text))) || null);

export default function ImageOptionsPanel({ value, onChange, imageCount }: Props) {
  const mode = resizeMode(value);
  const ids = useId();
  const set = (patch: Partial<ImageOptions>) => onChange({ ...value, ...patch });

  function setMode(next: ResizeMode) {
    if (next === "none") set({ scale: null, width: null, height: null });
    if (next === "scale") set({ scale: value.scale ?? 50, width: null, height: null });
    if (next === "fit") set({ scale: null, width: value.width ?? 1920, height: value.height ?? 1080 });
  }

  return (
    <details className="options">
      <summary>
        <span className="field-label">
          Image options for {imageCount} {imageCount === 1 ? "image" : "images"}
        </span>
        <span className="hint">{summary(value)}</span>
      </summary>

      <div className="options-body">
        <fieldset className="field">
          <legend id={`${ids}-resize`} className="field-label">
            Resize
          </legend>
          <Segmented labelledBy={`${ids}-resize`} options={RESIZE_MODES} value={mode} onChange={setMode} />
          {mode === "scale" && (
            <label className="inline-input">
              <input
                type="number"
                min={1}
                max={100}
                value={value.scale ?? ""}
                onChange={(e) => set({ scale: Math.min(100, toNumber(e.target.value) ?? 1) })}
                aria-label="Percent of original size"
              />
              % of the original width and height
            </label>
          )}
          {mode === "fit" && (
            <div className="inline-input">
              <input
                type="number"
                min={1}
                value={value.width ?? ""}
                placeholder="any"
                onChange={(e) => set({ width: toNumber(e.target.value) })}
                aria-label="Maximum width in pixels"
              />
              ×
              <input
                type="number"
                min={1}
                value={value.height ?? ""}
                placeholder="any"
                onChange={(e) => set({ height: toNumber(e.target.value) })}
                aria-label="Maximum height in pixels"
              />
              px, keeping the shape. Smaller images aren't enlarged.
            </div>
          )}
        </fieldset>

        <fieldset className="field">
          <legend id={`${ids}-rotate`} className="field-label">
            Rotate
          </legend>
          <Segmented
            labelledBy={`${ids}-rotate`}
            options={ROTATE_OPTIONS}
            value={value.rotate}
            onChange={(deg) => set({ rotate: deg })}
          />
        </fieldset>

        <fieldset className="field">
          <legend className="field-label">Quality</legend>
          <label className="radio">
            <input type="radio" name={`${ids}-quality`} checked={value.quality == null} onChange={() => set({ quality: null })} />
            Automatic
          </label>
          <label className="radio">
            <input
              type="radio"
              name={`${ids}-quality`}
              checked={value.quality != null}
              onChange={() => set({ quality: value.quality ?? 80 })}
            />
            Set it myself
          </label>
          {value.quality != null && (
            <label className="inline-input">
              <input
                type="range"
                min={10}
                max={100}
                value={value.quality}
                onChange={(e) => set({ quality: Number(e.target.value) })}
                aria-label="Quality"
              />
              <span className="quality-value">{value.quality}</span>
            </label>
          )}
          <p className="hint">
            Applies to JPG, WEBP, AVIF and HEIC. With a size limit, quality can go lower than this but never higher.
          </p>
        </fieldset>

        <label className="radio">
          <input
            type="checkbox"
            checked={value.keepMetadata}
            onChange={(e) => set({ keepMetadata: e.target.checked })}
          />
          Keep photo details (date, camera and location)
        </label>
        <p className="hint">Off by default, so a phone photo doesn't reveal where it was taken.</p>

        {summary(value) !== "No changes" && (
          <button className="btn btn-quiet btn-small reset-options" onClick={() => onChange(DEFAULT_IMAGE_OPTIONS)}>
            Reset image options
          </button>
        )}
      </div>
    </details>
  );
}

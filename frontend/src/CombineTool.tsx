import { useEffect, useState } from "react";
import { combinePdf, FormatMap } from "./api";
import DropZone from "./DropZone";
import { extensionOf, groupFormats, humanSize } from "./format";
import Icon from "./Icon";
import JobResult from "./JobResult";
import SizeLimitPicker from "./SizeLimitPicker";
import Thumb from "./Thumb";
import { useJob } from "./useJob";

type Entry = { key: string; file: File };
let nextKey = 0;

type Props = {
  formats: FormatMap | null;
  maxUpload: number;
  /** Tells the page whether this tool has files, so the masthead can step back. */
  onHasFiles: (has: boolean) => void;
};

export default function CombineTool({ formats, maxUpload, onHasFiles }: Props) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [name, setName] = useState("combined");
  const [limitKb, setLimitKb] = useState<number | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [dropAt, setDropAt] = useState<number | null>(null);
  const [limitOk, setLimitOk] = useState(true);
  const task = useJob();

  const accepted = formats
    ? [...Object.keys(formats).filter((ext) => formats[ext].category === "image"), "pdf"]
    : [];
  const total = entries.reduce((sum, e) => sum + e.file.size, 0);
  const tooBig = maxUpload > 0 && total > maxUpload;

  const hasEntries = entries.length > 0;
  useEffect(() => {
    onHasFiles(hasEntries);
  }, [hasEntries, onHasFiles]);

  function change(next: Entry[]) {
    setEntries(next);
    task.reset(); // the previous result no longer matches the list
  }

  function add(files: File[]) {
    const ok = files.filter((f) => accepted.includes(extensionOf(f.name)));
    setRejected(files.filter((f) => !ok.includes(f)).map((f) => f.name));
    change([...entries, ...ok.map((file) => ({ key: String(nextKey++), file }))]);
  }

  function moveTo(from: number, to: number) {
    if (from === to) return;
    const next = [...entries];
    const [entry] = next.splice(from, 1);
    next.splice(to, 0, entry);
    change(next);
  }

  function endDrag() {
    setDragging(null);
    setDropAt(null);
  }

  return (
    <>
      <DropZone
        title="Drop images or PDFs here, or choose them"
        disabled={!formats}
        accept={accepted}
        groups={formats ? groupFormats(formats, accepted) : undefined}
        compact={hasEntries}
        extra={
          <button className="btn btn-quiet" onClick={() => change([])} disabled={task.busy}>
            Clear list
          </button>
        }
        onFiles={add}
      />
      {rejected.length > 0 && (
        <p className="banner banner-error">
          Only images and PDFs can be combined, so these were left out: {rejected.join(", ")}
        </p>
      )}

      {hasEntries && (
        <section className="workbench has-side side-after" aria-label="Files to combine">
          <div className="work-side">
            <div className="controls">
              <label className="field">
                <span className="field-label">File name</span>
                <span className="name-input">
                  <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
                  <span className="name-suffix">.pdf</span>
                </span>
              </label>
              <SizeLimitPicker value={limitKb} onChange={setLimitKb} onValidChange={setLimitOk} />
            </div>

            {tooBig && (
              <p className="banner banner-error">
                These files add up to {humanSize(total)}. The most you can upload at once is {humanSize(maxUpload)}.
              </p>
            )}
          </div>

          <div className="work-main">
            <p className="hint">
              Pages follow this order.{" "}
              <span className="fine-only">Drag files or use the arrows to reorder them.</span>
              <span className="coarse-only">Use the arrows to reorder them.</span> Each image becomes one page.
            </p>
            <ol className="order-list">
              {entries.map((entry, i) => (
                <li
                  key={entry.key}
                  className={[
                    "order-row",
                    dragging === i && "is-dragging",
                    dropAt === i && dragging !== null && dragging !== i && "is-drop-target",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  draggable={!task.busy}
                  onDragStart={(e) => {
                    setDragging(i);
                    e.dataTransfer.effectAllowed = "move";
                    e.dataTransfer.setData("text/plain", String(i)); // Firefox won't start a drag without data
                  }}
                  onDragOver={(e) => {
                    if (dragging === null) return; // a file dragged in from outside, not a row
                    e.preventDefault();
                    setDropAt(i);
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (dragging !== null) moveTo(dragging, i);
                    endDrag();
                  }}
                  onDragEnd={endDrag}
                >
                  <span className="order-num">{i + 1}</span>
                  <Thumb file={entry.file} size={40} />
                  <span className="file-name" title={entry.file.name}>
                    {entry.file.name}
                  </span>
                  <span className="order-size">{humanSize(entry.file.size)}</span>
                  <span className="order-buttons">
                    <button
                      className="icon-btn"
                      onClick={() => moveTo(i, i - 1)}
                      disabled={i === 0 || task.busy}
                      aria-label={`Move ${entry.file.name} up`}
                    >
                      <Icon name="up" />
                    </button>
                    <button
                      className="icon-btn"
                      onClick={() => moveTo(i, i + 1)}
                      disabled={i === entries.length - 1 || task.busy}
                      aria-label={`Move ${entry.file.name} down`}
                    >
                      <Icon name="down" />
                    </button>
                  </span>
                  {/* Kept apart from the arrows so a thumb aiming to reorder can't remove a file. */}
                  <button
                    className="icon-btn order-remove"
                    onClick={() => change(entries.filter((x) => x.key !== entry.key))}
                    disabled={task.busy}
                    aria-label={`Remove ${entry.file.name}`}
                  >
                    <Icon name="close" />
                  </button>
                </li>
              ))}
            </ol>

            <div className="actions">
              <button
                className="btn btn-primary"
                disabled={task.busy || tooBig || !limitOk}
                aria-describedby={!task.busy && !tooBig && !limitOk ? "combine-blocked" : undefined}
                onClick={() =>
                  task.start((signal) =>
                    combinePdf(
                      entries.map((e) => e.file),
                      name.trim() || "combined",
                      limitKb,
                      signal,
                    ),
                  )
                }
              >
                {task.busy
                  ? "Combining…"
                  : entries.length === 1
                    ? "Make a PDF"
                    : `Combine ${entries.length} files into one PDF`}
              </button>
              {/* Too big is already explained in its own banner with the settings. */}
              {!task.busy && !tooBig && !limitOk && (
                <p id="combine-blocked" className="hint action-hint">
                  Fix the size limit first.
                </p>
              )}
            </div>

            <JobResult task={task} verb="Combining" />
          </div>
        </section>
      )}
    </>
  );
}

import { useState } from "react";
import { combinePdf, FormatMap } from "./api";
import DropZone from "./DropZone";
import { extensionOf, humanSize } from "./format";
import JobResult from "./JobResult";
import SizeLimitPicker from "./SizeLimitPicker";
import { useJob } from "./useJob";

type Entry = { key: string; file: File };
let nextKey = 0;

export default function CombineTool({ formats, maxUpload }: { formats: FormatMap | null; maxUpload: number }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [name, setName] = useState("combined");
  const [limitKb, setLimitKb] = useState<number | null>(null);
  const task = useJob();

  const accepted = formats
    ? [...Object.keys(formats).filter((ext) => formats[ext].category === "image"), "pdf"]
    : [];
  const total = entries.reduce((sum, e) => sum + e.file.size, 0);
  const tooBig = maxUpload > 0 && total > maxUpload;

  function change(next: Entry[]) {
    setEntries(next);
    task.reset(); // the previous result no longer matches the list
  }

  function add(files: File[]) {
    const ok = files.filter((f) => accepted.includes(extensionOf(f.name)));
    setRejected(files.filter((f) => !ok.includes(f)).map((f) => f.name));
    change([...entries, ...ok.map((file) => ({ key: String(nextKey++), file }))]);
  }

  function move(index: number, by: number) {
    const next = [...entries];
    const [entry] = next.splice(index, 1);
    next.splice(index + by, 0, entry);
    change(next);
  }

  return (
    <>
      <DropZone title="Drop images or PDFs here" disabled={!formats} accept={accepted} onFiles={add} />
      {rejected.length > 0 && (
        <p className="banner banner-error">
          Only images and PDFs can be combined, so these were left out: {rejected.join(", ")}
        </p>
      )}

      {entries.length > 0 && (
        <section className="workbench" aria-label="Files to combine">
          <p className="hint">Pages follow this order. Each image becomes one page.</p>
          <ol className="order-list">
            {entries.map((entry, i) => (
              <li key={entry.key} className="order-row">
                <span className="order-num">{i + 1}</span>
                <span className="file-name" title={entry.file.name}>
                  {entry.file.name}
                </span>
                <span className="order-size">{humanSize(entry.file.size)}</span>
                <span className="order-buttons">
                  <button
                    className="icon-btn"
                    onClick={() => move(i, -1)}
                    disabled={i === 0 || task.busy}
                    aria-label={`Move ${entry.file.name} up`}
                  >
                    ↑
                  </button>
                  <button
                    className="icon-btn"
                    onClick={() => move(i, 1)}
                    disabled={i === entries.length - 1 || task.busy}
                    aria-label={`Move ${entry.file.name} down`}
                  >
                    ↓
                  </button>
                  <button
                    className="icon-btn"
                    onClick={() => change(entries.filter((x) => x.key !== entry.key))}
                    disabled={task.busy}
                    aria-label={`Remove ${entry.file.name}`}
                  >
                    ×
                  </button>
                </span>
              </li>
            ))}
          </ol>

          <div className="controls">
            <label className="field">
              <span className="field-label">File name</span>
              <span className="name-input">
                <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
                <span className="name-suffix">.pdf</span>
              </span>
            </label>
            <SizeLimitPicker value={limitKb} onChange={setLimitKb} />
          </div>

          {tooBig && (
            <p className="banner banner-error">
              These files add up to {humanSize(total)}. The most you can upload at once is {humanSize(maxUpload)}.
            </p>
          )}

          <div className="actions">
            <button
              className="btn btn-primary"
              disabled={task.busy || tooBig}
              onClick={() => task.start(() => combinePdf(entries.map((e) => e.file), name.trim() || "combined", limitKb))}
            >
              {task.busy
                ? "Combining…"
                : entries.length === 1
                  ? "Make a PDF"
                  : `Combine ${entries.length} files into one PDF`}
            </button>
            <button className="btn btn-quiet" onClick={() => change([])} disabled={task.busy}>
              Clear list
            </button>
          </div>

          <JobResult task={task} verb="Combining" />
        </section>
      )}
    </>
  );
}

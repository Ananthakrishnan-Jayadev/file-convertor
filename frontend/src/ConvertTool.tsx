import { useCallback, useEffect, useRef, useState } from "react";
import { createJob, downloadArchive, FormatMap, getJob, Job } from "./api";
import DropZone from "./DropZone";
import FileRow, { Item } from "./FileRow";
import { defaultTarget, extensionOf, humanSize } from "./format";
import SizeLimitPicker from "./SizeLimitPicker";

const PARALLEL_UPLOADS = 3;
const POLL_MS = 1000;

let nextKey = 0;

export default function ConvertTool({ formats, maxUpload }: { formats: FormatMap | null; maxUpload: number }) {
  const [items, setItems] = useState<Item[]>([]);
  const [limitKb, setLimitKb] = useState<number | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const update = useCallback((key: string, patch: Partial<Item>) => {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));
  }, []);

  const addFiles = useCallback(
    (files: File[]) => {
      if (!formats) return;
      const added = Array.from(files).map((file): Item => {
        const ext = extensionOf(file.name);
        const entry = formats[ext];
        const base = { key: String(nextKey++), file, ext };
        if (!entry) return { ...base, target: ext, phase: "unsupported" };
        if (maxUpload && file.size > maxUpload)
          return { ...base, target: ext, phase: "unsupported", message: `Files can be at most ${humanSize(maxUpload)}.` };
        return { ...base, target: defaultTarget(ext, entry.category, entry.outputs), phase: "ready" };
      });
      setItems((prev) => [...prev, ...added]);
    },
    [formats, maxUpload],
  );

  // Poll every job that's still converting.
  const pending = items.filter((it) => it.phase === "working" && it.job).map((it) => it.job!.id);
  const pendingKey = pending.join(",");
  useEffect(() => {
    if (!pendingKey) return;
    const timer = setInterval(async () => {
      const results = await Promise.allSettled(pendingKey.split(",").map(getJob));
      setItems((prev) =>
        prev.map((it) => {
          const r = results.find((x) => x.status === "fulfilled" && x.value.id === it.job?.id) as
            | PromiseFulfilledResult<Job>
            | undefined;
          if (!r) return it;
          const job = r.value;
          if (job.status === "done") return { ...it, job, phase: "done" };
          if (job.status === "error") return { ...it, job, phase: "error", message: job.error ?? "Conversion failed." };
          return { ...it, job };
        }),
      );
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [pendingKey]);

  const queue = items.filter((it) => it.phase === "ready" || it.phase === "error");
  const running = useRef(false);

  async function convertAll() {
    if (running.current) return;
    running.current = true;
    const todo = [...queue];
    const worker = async () => {
      for (let it = todo.shift(); it; it = todo.shift()) {
        update(it.key, { phase: "uploading", message: undefined, job: undefined });
        try {
          const job = await createJob(it.file, it.target, limitKb);
          update(it.key, { phase: "working", job });
        } catch (e) {
          update(it.key, { phase: "error", message: (e as Error).message });
        }
      }
    };
    await Promise.all(Array.from({ length: PARALLEL_UPLOADS }, worker));
    running.current = false;
  }

  function setTarget(key: string, target: string) {
    // Changing the format of a finished file means it needs converting again.
    update(key, { target, phase: "ready", job: undefined, message: undefined });
  }

  const supported = items.filter((it) => it.phase !== "unsupported" && formats?.[it.ext]);
  const commonTargets =
    formats && supported.length > 1
      ? supported.map((it) => formats[it.ext].outputs).reduce((acc, outs) => acc.filter((f) => outs.includes(f)))
      : [];

  const doneIds = items.filter((it) => it.phase === "done" && it.job).map((it) => it.job!.id);
  const busy = items.some((it) => it.phase === "uploading" || it.phase === "working");

  return (
    <>
      <DropZone
        title="Drop files here"
        disabled={!formats}
        accept={formats ? Object.keys(formats) : []}
        onFiles={addFiles}
      />

      {items.length > 0 && (
        <section className="workbench" aria-label="Files to convert">
          <div className="controls">
            <SizeLimitPicker value={limitKb} onChange={setLimitKb} />
            {commonTargets.length > 0 && (
              <label className="field">
                <span className="field-label">Convert all to</span>
                <select
                  value=""
                  onChange={(e) => {
                    const t = e.target.value;
                    supported.forEach((it) => setTarget(it.key, t));
                  }}
                >
                  <option value="" disabled>
                    Choose a format
                  </option>
                  {commonTargets.map((f) => (
                    <option key={f} value={f}>
                      {f.toUpperCase()}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <ul className="file-list">
            {items.map((it) => (
              <FileRow
                key={it.key}
                item={it}
                outputs={formats?.[it.ext]?.outputs ?? []}
                limitKb={limitKb}
                onTarget={(t) => setTarget(it.key, t)}
                onRemove={() => setItems((prev) => prev.filter((x) => x.key !== it.key))}
              />
            ))}
          </ul>

          <div className="actions">
            <button className="btn btn-primary" onClick={convertAll} disabled={queue.length === 0 || busy}>
              {busy ? "Converting…" : queue.length === 1 ? "Convert 1 file" : `Convert ${queue.length} files`}
            </button>
            {doneIds.length > 1 && (
              <button
                className="btn"
                onClick={() => {
                  setArchiveError(null);
                  downloadArchive(doneIds).catch((e) => setArchiveError((e as Error).message));
                }}
              >
                Download all as .zip
              </button>
            )}
            <button className="btn btn-quiet" onClick={() => setItems([])} disabled={busy}>
              Clear list
            </button>
          </div>
          {archiveError && <p className="banner banner-error">{archiveError}</p>}
        </section>
      )}
    </>
  );
}

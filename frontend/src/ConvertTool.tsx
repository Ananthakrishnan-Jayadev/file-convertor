import { useCallback, useEffect, useRef, useState } from "react";
import {
  createJob,
  DEFAULT_IMAGE_OPTIONS,
  deleteJob,
  downloadArchive,
  FormatMap,
  getJob,
  ImageOptions,
  isGone,
  Job,
} from "./api";
import DropZone from "./DropZone";
import FileRow, { Item } from "./FileRow";
import { defaultTarget, extensionOf, groupFormats, humanSize } from "./format";
import ImageOptionsPanel from "./ImageOptionsPanel";
import { Elapsed } from "./JobResult";
import SizeLimitPicker from "./SizeLimitPicker";
import { useElapsed } from "./useElapsed";

const PARALLEL_UPLOADS = 3;
const POLL_MS = 1000;

let nextKey = 0;

type Props = {
  formats: FormatMap | null;
  maxUpload: number;
  /** Tells the page whether this tool has files, so the masthead can step back. */
  onHasFiles: (has: boolean) => void;
};

export default function ConvertTool({ formats, maxUpload, onHasFiles }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [limitKb, setLimitKb] = useState<number | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [imageOpts, setImageOpts] = useState<ImageOptions>(DEFAULT_IMAGE_OPTIONS);
  const [limitOk, setLimitOk] = useState(true);
  const uploads = useRef(new Map<string, AbortController>());

  const hasItems = items.length > 0;
  useEffect(() => {
    onHasFiles(hasItems);
  }, [hasItems, onHasFiles]);

  const isImage = (it: Item) => formats?.[it.ext]?.category === "image";

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
      const ids = pendingKey.split(",");
      const results = await Promise.allSettled(ids.map(getJob));
      setItems((prev) =>
        prev.map((it) => {
          const i = it.job ? ids.indexOf(it.job.id) : -1;
          if (i === -1) return it;
          const r: PromiseSettledResult<Job> = results[i];
          if (r.status === "rejected") {
            // Gone means the server expired or deleted it; any other failure may pass, so keep polling.
            return isGone(r.reason) ? { ...it, job: undefined, phase: "error", message: (r.reason as Error).message } : it;
          }
          const job = r.value;
          if (job.status === "done") return { ...it, job, phase: "done" };
          if (job.status === "error") return { ...it, job, phase: "error", message: job.error ?? "Conversion failed." };
          if (job.status === "cancelled") return { ...it, job: undefined, phase: "ready", message: "Cancelled." };
          return { ...it, job };
        }),
      );
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [pendingKey]);

  const queue = items.filter((it) => it.phase === "ready" || it.phase === "error");
  const running = useRef(false);

  async function convert(list: Item[]) {
    if (running.current || list.length === 0) return;
    running.current = true;
    const todo = [...list];
    const worker = async () => {
      for (let it = todo.shift(); it; it = todo.shift()) {
        update(it.key, { phase: "uploading", message: undefined, job: undefined });
        const controller = new AbortController();
        uploads.current.set(it.key, controller);
        try {
          const options = isImage(it) ? imageOpts : undefined;
          const job = await createJob(it.file, it.target, limitKb, options, controller.signal);
          update(it.key, { phase: "working", job });
        } catch (e) {
          if (!controller.signal.aborted) update(it.key, { phase: "error", message: (e as Error).message });
        } finally {
          uploads.current.delete(it.key);
        }
      }
    };
    await Promise.all(Array.from({ length: PARALLEL_UPLOADS }, worker));
    running.current = false;
  }

  function cancel(it: Item) {
    uploads.current.get(it.key)?.abort();
    if (it.job && it.phase === "working") deleteJob(it.job.id);
    update(it.key, { phase: "ready", job: undefined, message: "Cancelled." });
  }

  function remove(it: Item) {
    if (it.phase === "uploading" || it.phase === "working") cancel(it);
    else if (it.job) deleteJob(it.job.id); // free the server copy straight away
    setItems((prev) => prev.filter((x) => x.key !== it.key));
  }

  function clearAll() {
    items.forEach((it) => it.job && deleteJob(it.job.id));
    setItems([]);
  }

  /** New settings make finished results stale, so those files need converting again. */
  function markStale(affects: (it: Item) => boolean) {
    setItems((prev) =>
      prev.map((it) => {
        if (it.phase !== "done" || !affects(it)) return it;
        if (it.job) deleteJob(it.job.id);
        return { ...it, phase: "ready", job: undefined, message: "Settings changed. Convert again to apply them." };
      }),
    );
  }

  function changeLimit(kb: number | null) {
    setLimitKb(kb);
    markStale(() => true);
  }

  function changeImageOpts(next: ImageOptions) {
    setImageOpts(next);
    markStale(isImage);
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
  const imageCount = items.filter((it) => it.phase !== "unsupported" && isImage(it)).length;
  const batchElapsed = useElapsed(busy);

  // One line for the whole batch, so progress and outcomes don't have to be read off every row.
  const active = items.filter((it) => it.phase !== "unsupported");
  const doneCount = active.filter((it) => it.phase === "done").length;
  const overCount = active.filter((it) => it.phase === "done" && it.job?.target_met === false).length;
  const failedCount = active.filter((it) => it.phase === "error").length;
  const batchSummary =
    busy || doneCount > 0 || failedCount > 0
      ? [
          `${doneCount} of ${active.length} done`,
          overCount > 0 && `${overCount} over the limit`,
          failedCount > 0 && `${failedCount} failed`,
        ]
          .filter(Boolean)
          .join(" · ")
      : "";
  const onlyRetries = queue.length > 0 && queue.every((it) => it.phase === "error");
  const convertLabel = busy
    ? "Converting…"
    : queue.length === 0
      ? "Convert files"
      : onlyRetries
        ? queue.length === 1
          ? "Try again"
          : `Try ${queue.length} files again`
        : queue.length === 1
          ? "Convert 1 file"
          : `Convert ${queue.length} files`;
  // Why the button can't be used, when the screen doesn't already say so.
  const blockedReason = busy
    ? null
    : !limitOk
      ? "Fix the size limit first."
      : queue.length === 0 && doneCount === 0
        ? "None of these files can be converted."
        : null;

  return (
    <>
      <DropZone
        title="Drop files here or choose them"
        disabled={!formats}
        accept={formats ? Object.keys(formats) : []}
        groups={formats ? groupFormats(formats) : undefined}
        compact={hasItems}
        extra={
          <button className="btn btn-quiet" onClick={clearAll} disabled={busy}>
            Clear list
          </button>
        }
        onFiles={addFiles}
      />

      {hasItems && (
        <section className="workbench has-side" aria-label="Files to convert">
          <div className="work-side">
            <div className="controls">
              <SizeLimitPicker value={limitKb} onChange={changeLimit} onValidChange={setLimitOk} />
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

            {imageCount > 0 && <ImageOptionsPanel value={imageOpts} onChange={changeImageOpts} imageCount={imageCount} />}
          </div>

          <div className="work-main">
            <ul className="file-list">
              {items.map((it) => (
                <FileRow
                  key={it.key}
                  item={it}
                  outputs={formats?.[it.ext]?.outputs ?? []}
                  limitKb={limitKb}
                  isImage={isImage(it)}
                  onTarget={(t) => setTarget(it.key, t)}
                  onRemove={() => remove(it)}
                  onCancel={() => cancel(it)}
                  onRetry={busy || !limitOk ? undefined : () => convert([it])}
                />
              ))}
            </ul>

            <div className="actions">
              <button
                className="btn btn-primary"
                onClick={() => convert(queue)}
                disabled={queue.length === 0 || busy || !limitOk}
                aria-describedby={blockedReason ? "convert-blocked" : undefined}
              >
                {convertLabel}
              </button>
              {blockedReason && (
                <p id="convert-blocked" className="hint action-hint">
                  {blockedReason}
                </p>
              )}
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
              <p className="batch-status">
                <span role="status">{batchSummary}</span>
                {busy && (
                  // Visual only: the live summary above shouldn't be re-read every second.
                  <span aria-hidden="true">
                    {" "}
                    <Elapsed seconds={batchElapsed} />
                  </span>
                )}
              </p>
            </div>
            {doneCount > 0 && (
              <p className="hint expiry-hint">Download within an hour. After that, results are deleted from the server.</p>
            )}
            {archiveError && <p className="banner banner-error">{archiveError}</p>}
          </div>
        </section>
      )}
    </>
  );
}

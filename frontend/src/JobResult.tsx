import { useState } from "react";
import { downloadUrl, getJob, isGone, Job } from "./api";
import { humanSize } from "./format";
import SizeMeter from "./SizeMeter";
import { formatElapsed, SHOW_ELAPSED_AFTER, useElapsed } from "./useElapsed";
import { JobState } from "./useJob";

/** Progress, then the size meter and download link, for a single combine/split job. */
export default function JobResult({ task, verb }: { task: JobState; verb: string }) {
  const { job, error, uploading, busy } = task;
  const elapsed = useElapsed(busy);
  if (!job && !error && !uploading) return null;

  // The clock is visual only: this region is live, and a ticking clock would be read out every second.
  const clock = (
    <span aria-hidden="true">
      <Elapsed seconds={elapsed} />
    </span>
  );

  return (
    <div className="result" aria-live="polite">
      {uploading && <p className="status status-busy">Uploading… {clock}</p>}
      {error && <p className="status status-error">{error}</p>}
      {job && (job.status === "queued" || job.status === "running") && (
        <p className="status status-busy">
          {job.status === "running" ? `${verb}…` : "Waiting in line…"} {clock}
        </p>
      )}
      {busy && (
        <button className="btn btn-quiet btn-small cancel-btn" onClick={task.cancel}>
          Cancel
        </button>
      )}
      {job?.status === "error" && <p className="status status-error">{job.error ?? `${verb} failed.`}</p>}
      {job?.status === "done" && (
        <>
          <SizeMeter
            input={job.input_size}
            output={job.output_size}
            limit={job.max_bytes}
            met={job.target_met}
            playKey={job.id}
          />
          <DoneSummary job={job} tip={limitTip(job)} />
          <p className="hint">Download it within an hour. After that, it's deleted from the server.</p>
        </>
      )}
    </div>
  );
}

/** Running time, shown once a job has taken long enough for the wait to matter. */
export function Elapsed({ seconds }: { seconds: number }) {
  if (seconds < SHOW_ELAPSED_AFTER) return null;
  return <span className="elapsed">{formatElapsed(seconds)}</span>;
}

/** One concrete next step when a size limit was missed. */
export function limitTip(job: Job, opts: { isImage?: boolean; outputs?: string[] } = {}): string {
  if (job.operation === "combine") return "To get under it, choose a larger limit or combine fewer files.";
  if (job.operation === "split") return "To get under it, choose a larger limit or put fewer pages in each PDF.";
  if (opts.isImage) {
    const compact = ["webp", "avif"].filter((f) => f !== job.target_format && opts.outputs?.includes(f));
    return compact.length > 0
      ? `To get under it, make the image smaller in Image options, or convert to ${compact
          .map((f) => f.toUpperCase())
          .join(" or ")}, which ${compact.length === 1 ? "is" : "are"} usually smaller.`
      : "To get under it, make the image smaller in Image options, or choose a larger limit.";
  }
  return "To get under it, try a more compact format or choose a larger limit.";
}

export function DoneSummary({ job, tip }: { job: Job; tip?: string }) {
  const [gone, setGone] = useState<string | null>(null);
  if (job.output_size == null) return null;
  const saved = job.input_size > 0 ? Math.round((1 - job.output_size / job.input_size) * 100) : 0;
  const limit = job.max_bytes != null && job.target_met != null ? humanSize(job.max_bytes) : null;

  // The link downloads natively; alongside it, check the result still exists so an expired one is explained.
  function checkStillThere() {
    getJob(job.id)
      .then(() => setGone(null))
      .catch((e) => {
        if (isGone(e)) setGone((e as Error).message);
      });
  }

  return (
    <div className="done">
      <p className="status">
        {limit && (
          <span className={job.target_met ? "outcome outcome-met" : "outcome outcome-missed"}>
            {job.target_met ? `Under the ${limit} limit` : `Over the ${limit} limit`}
          </span>
        )}
        {humanSize(job.input_size)} to {humanSize(job.output_size)}
        {saved > 0 && ` (${saved}% smaller)`}
        {job.note && <span className={job.target_met === false ? "note note-warn" : "note"}>{job.note}</span>}
        {job.target_met === false && tip && <span className="note">{tip}</span>}
      </p>
      <a
        className="btn btn-download"
        href={downloadUrl(job.id)}
        download={job.output_name ?? undefined}
        onClick={checkStillThere}
      >
        Download {job.output_name}
      </a>
      {gone && (
        <p className="status status-error done-gone" role="alert">
          {gone}
        </p>
      )}
    </div>
  );
}

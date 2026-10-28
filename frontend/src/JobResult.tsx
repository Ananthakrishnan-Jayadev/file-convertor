import { downloadUrl, Job } from "./api";
import { humanSize } from "./format";
import SizeMeter from "./SizeMeter";
import { JobState } from "./useJob";

/** Progress, then the size meter and download link, for a single combine/split job. */
export default function JobResult({ task, verb }: { task: JobState; verb: string }) {
  const { job, error, uploading } = task;
  if (!job && !error && !uploading) return null;

  return (
    <div className="result" aria-live="polite">
      {uploading && <p className="status status-busy">Uploading…</p>}
      {error && <p className="status status-error">{error}</p>}
      {job && job.status !== "done" && job.status !== "error" && (
        <p className="status status-busy">{job.status === "running" ? `${verb}…` : "Waiting in line…"}</p>
      )}
      {job?.status === "error" && <p className="status status-error">{job.error ?? `${verb} failed.`}</p>}
      {job?.status === "done" && (
        <>
          <SizeMeter input={job.input_size} output={job.output_size} limit={job.max_bytes} met={job.target_met} />
          <DoneSummary job={job} />
        </>
      )}
    </div>
  );
}

export function DoneSummary({ job }: { job: Job }) {
  if (job.output_size == null) return null;
  const saved = job.input_size > 0 ? Math.round((1 - job.output_size / job.input_size) * 100) : 0;
  return (
    <div className="done">
      <p className="status">
        {humanSize(job.input_size)} to {humanSize(job.output_size)}
        {saved > 0 && ` (${saved}% smaller)`}
        {job.note && <span className={job.target_met === false ? "note note-warn" : "note"}>{job.note}</span>}
      </p>
      <a className="btn btn-download" href={downloadUrl(job.id)} download={job.output_name ?? undefined}>
        Download {job.output_name}
      </a>
    </div>
  );
}

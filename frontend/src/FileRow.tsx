import { Job } from "./api";
import { DoneSummary } from "./JobResult";
import SizeMeter from "./SizeMeter";

export type Item = {
  key: string;
  file: File;
  ext: string;
  target: string;
  phase: "ready" | "uploading" | "working" | "done" | "error" | "unsupported";
  job?: Job;
  message?: string;
};

type Props = {
  item: Item;
  outputs: string[];
  limitKb: number | null;
  onTarget: (target: string) => void;
  onRemove: () => void;
};

export default function FileRow({ item, outputs, limitKb, onTarget, onRemove }: Props) {
  const { file, ext, target, phase, job } = item;
  const locked = phase === "uploading" || phase === "working";
  // Before conversion, show the limit the user has picked; afterwards, the one actually used.
  const limitBytes = job ? job.max_bytes : limitKb ? limitKb * 1024 : null;

  return (
    <li className={`file-row phase-${phase}`}>
      <div className="file-head">
        <span className="file-name" title={file.name}>
          {file.name}
        </span>
        <button className="icon-btn" onClick={onRemove} disabled={locked} aria-label={`Remove ${file.name}`}>
          ×
        </button>
      </div>

      {phase === "unsupported" ? (
        <p className="status status-error">
          {item.message ??
            (ext ? `.${ext} files can't be converted yet.` : "This file has no extension, so its type is unknown.")}
        </p>
      ) : (
        <>
          <div className="file-convert">
            <span className="fmt-chip">{ext.toUpperCase()}</span>
            <span className="to">to</span>
            <select
              value={target}
              disabled={locked}
              onChange={(e) => onTarget(e.target.value)}
              aria-label={`Output format for ${file.name}`}
            >
              {outputs.map((f) => (
                <option key={f} value={f}>
                  {f === ext ? `${f.toUpperCase()} (same format, only shrink)` : f.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          <SizeMeter
            input={file.size}
            output={phase === "done" ? job?.output_size ?? null : null}
            limit={limitBytes}
            met={job?.target_met ?? null}
          />

          <Status item={item} />
        </>
      )}
    </li>
  );
}

function Status({ item }: { item: Item }) {
  const { phase, job, message } = item;
  switch (phase) {
    case "ready":
      return <p className="status">Ready to convert</p>;
    case "uploading":
      return <p className="status status-busy">Uploading…</p>;
    case "working":
      return <p className="status status-busy">{job?.status === "running" ? "Converting…" : "Waiting in line…"}</p>;
    case "error":
      return <p className="status status-error">{message ?? "Conversion failed."}</p>;
    case "done":
      return job ? <DoneSummary job={job} /> : null;
    default:
      return null;
  }
}

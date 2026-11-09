import { useState } from "react";
import { Job } from "./api";
import Compare, { canCompare } from "./Compare";
import Icon from "./Icon";
import { DoneSummary, Elapsed, limitTip } from "./JobResult";
import SizeMeter from "./SizeMeter";
import Thumb from "./Thumb";
import { useElapsed } from "./useElapsed";

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
  isImage: boolean;
  onTarget: (target: string) => void;
  onRemove: () => void;
  onCancel: () => void;
  /** Convert just this file again after a failure; absent while a batch is running. */
  onRetry?: () => void;
};

export default function FileRow({ item, outputs, limitKb, isImage, onTarget, onRemove, onCancel, onRetry }: Props) {
  const { file, ext, target, phase, job } = item;
  const locked = phase === "uploading" || phase === "working";
  // Before conversion, show the limit the user has picked; afterwards, the one actually used.
  const limitBytes = job ? job.max_bytes : limitKb ? limitKb * 1024 : null;
  const [comparing, setComparing] = useState(false);
  const comparable = phase === "done" && canCompare(file, job);
  const elapsed = useElapsed(locked);
  const tip = job && phase === "done" ? limitTip(job, { isImage, outputs }) : undefined;

  return (
    <li className={`file-row phase-${phase}`}>
      <div className="file-head">
        <span className="file-title">
          <Thumb file={file} />
          <span className="file-name" title={file.name}>
            {file.name}
          </span>
        </span>
        <button className="icon-btn" onClick={onRemove} aria-label={`Remove ${file.name}`}>
          <Icon name="close" />
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
            playKey={job?.id}
          />

          <div className="status-line">
            <Status item={item} elapsed={elapsed} tip={tip} />
            {locked && (
              <button className="btn btn-quiet btn-small" onClick={onCancel}>
                Cancel
              </button>
            )}
            {phase === "error" && onRetry && (
              <button className="btn btn-small" onClick={onRetry} aria-label={`Try again: ${file.name}`}>
                Try again
              </button>
            )}
          </div>

          {comparable && (
            <button className="btn btn-quiet btn-small compare-toggle" onClick={() => setComparing((c) => !c)}>
              {comparing ? "Hide comparison" : "Compare with original"}
            </button>
          )}
          {comparable && comparing && job && <Compare file={file} job={job} />}
        </>
      )}
    </li>
  );
}

function Status({ item, elapsed, tip }: { item: Item; elapsed: number; tip?: string }) {
  const { phase, job, message } = item;
  switch (phase) {
    case "ready":
      return <p className="status">{message ?? "Ready to convert"}</p>;
    case "uploading":
      return (
        <p className="status status-busy">
          Uploading… <Elapsed seconds={elapsed} />
        </p>
      );
    case "working":
      return (
        <p className="status status-busy">
          {job?.status === "running" ? "Converting…" : "Waiting in line…"} <Elapsed seconds={elapsed} />
        </p>
      );
    case "error":
      return <p className="status status-error">{message ?? "Conversion failed."}</p>;
    case "done":
      return job ? <DoneSummary job={job} tip={tip} /> : null;
    default:
      return null;
  }
}

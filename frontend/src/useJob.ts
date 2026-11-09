import { useEffect, useRef, useState } from "react";
import { deleteJob, getJob, isGone, Job } from "./api";

const POLL_MS = 1000;

/** Start one server job and follow it until it's done, fails, or is cancelled. */
export function useJob() {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const upload = useRef<AbortController | null>(null);

  const working = job != null && (job.status === "queued" || job.status === "running");
  const jobId = job?.id;

  useEffect(() => {
    if (!working || !jobId) return;
    const timer = setInterval(() => {
      getJob(jobId)
        .then((next) => {
          setJob(next);
          setError(null);
        })
        .catch((e) => {
          // Gone means it expired or was deleted, so stop following it; anything else may pass, so keep polling.
          if (isGone(e)) setJob(null);
          setError((e as Error).message);
        });
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [working, jobId]);

  async function start(request: (signal: AbortSignal) => Promise<Job>) {
    setJob(null);
    setError(null);
    setUploading(true);
    const controller = new AbortController();
    upload.current = controller;
    try {
      setJob(await request(controller.signal));
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message);
    } finally {
      upload.current = null;
      setUploading(false);
    }
  }

  function cancel() {
    upload.current?.abort();
    if (job && working) deleteJob(job.id);
    setJob(null);
    setError("Cancelled.");
  }

  function reset() {
    setJob(null);
    setError(null);
  }

  return { job, error, uploading, busy: uploading || working, start, cancel, reset };
}

export type JobState = ReturnType<typeof useJob>;

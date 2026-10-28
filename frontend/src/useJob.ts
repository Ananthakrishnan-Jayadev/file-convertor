import { useEffect, useState } from "react";
import { getJob, Job } from "./api";

const POLL_MS = 1000;

/** Start one server job and follow it until it's done or fails. */
export function useJob() {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const working = job != null && (job.status === "queued" || job.status === "running");
  const jobId = job?.id;

  useEffect(() => {
    if (!working || !jobId) return;
    const timer = setInterval(() => {
      getJob(jobId)
        .then(setJob)
        .catch((e) => setError((e as Error).message));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [working, jobId]);

  async function start(request: () => Promise<Job>) {
    setJob(null);
    setError(null);
    setUploading(true);
    try {
      setJob(await request());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  function reset() {
    setJob(null);
    setError(null);
  }

  return { job, error, uploading, busy: uploading || working, start, reset };
}

export type JobState = ReturnType<typeof useJob>;

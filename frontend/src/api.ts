export type FormatMap = Record<string, { category: string; outputs: string[] }>;

export type Job = {
  id: string;
  operation: "convert" | "combine" | "split";
  filename: string;
  target_format: string;
  max_bytes: number | null;
  status: "queued" | "running" | "done" | "error" | "cancelled";
  error: string | null;
  input_size: number;
  output_name: string | null;
  output_size: number | null;
  target_met: boolean | null;
  note: string;
};

/** A failed request. `status` 404 on a job means it has expired (the server keeps files for an hour). */
export class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** True when the server no longer has this job: it expired or was deleted. */
export const isGone = (e: unknown) => e instanceof HttpError && e.status === 404;

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  return `The server answered ${res.status} ${res.statusText}.`;
}

export async function getFormats(): Promise<{ formats: FormatMap; max_upload_bytes: number }> {
  const res = await fetch("/api/formats");
  if (!res.ok) throw new HttpError(res.status, await errorMessage(res));
  return res.json();
}

export type ImageOptions = {
  /** Fit within this box, keeping the shape. Never enlarges. */
  width: number | null;
  height: number | null;
  /** Percent of the original size, 1-100. Used instead of width/height when set. */
  scale: number | null;
  /** Degrees clockwise. */
  rotate: 0 | 90 | 180 | 270;
  /** 1-100 for JPG, WEBP, AVIF and HEIC. null means automatic. */
  quality: number | null;
  /** Keep date, camera and location details. */
  keepMetadata: boolean;
};

export const DEFAULT_IMAGE_OPTIONS: ImageOptions = {
  width: null,
  height: null,
  scale: null,
  rotate: 0,
  quality: null,
  keepMetadata: false,
};

/** Upload a form that starts a job. `signal` cancels the upload. */
async function startJob(url: string, body: FormData, signal?: AbortSignal): Promise<Job> {
  const res = await fetch(url, { method: "POST", body, signal });
  if (!res.ok) throw new HttpError(res.status, await errorMessage(res));
  return res.json();
}

export function createJob(
  file: File,
  target: string,
  maxSizeKb: number | null,
  image?: ImageOptions,
  signal?: AbortSignal,
): Promise<Job> {
  const body = new FormData();
  body.append("file", file);
  body.append("target_format", target);
  if (maxSizeKb) body.append("max_size_kb", String(maxSizeKb));
  if (image) {
    if (image.scale) body.append("scale", String(image.scale));
    else {
      if (image.width) body.append("width", String(image.width));
      if (image.height) body.append("height", String(image.height));
    }
    if (image.rotate) body.append("rotate", String(image.rotate));
    if (image.quality) body.append("quality", String(image.quality));
    if (image.keepMetadata) body.append("keep_metadata", "true");
  }
  return startJob("/api/jobs", body, signal);
}

export function combinePdf(
  files: File[],
  outputName: string,
  maxSizeKb: number | null,
  signal?: AbortSignal,
): Promise<Job> {
  const body = new FormData();
  files.forEach((f) => body.append("files", f));
  body.append("output_name", outputName);
  if (maxSizeKb) body.append("max_size_kb", String(maxSizeKb));
  return startJob("/api/pdf/combine", body, signal);
}

/** `ranges` like "1-3, 5, 8-"; empty means one PDF per page. `together` puts all ranges in one PDF. */
export function splitPdf(
  file: File,
  ranges: string,
  together: boolean,
  maxSizeKb: number | null,
  signal?: AbortSignal,
): Promise<Job> {
  const body = new FormData();
  body.append("file", file);
  body.append("ranges", ranges);
  body.append("together", String(together));
  if (maxSizeKb) body.append("max_size_kb", String(maxSizeKb));
  return startJob("/api/pdf/split", body, signal);
}

/** Cancel a running job, or delete a finished one and its files from the server. */
export async function deleteJob(id: string): Promise<void> {
  await fetch(`/api/jobs/${id}`, { method: "DELETE" });
}

export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`/api/jobs/${id}`);
  if (!res.ok) throw new HttpError(res.status, await errorMessage(res));
  return res.json();
}

export const downloadUrl = (id: string) => `/api/jobs/${id}/download`;

export async function downloadArchive(ids: string[]): Promise<void> {
  const res = await fetch("/api/archive", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  if (!res.ok) throw new HttpError(res.status, await errorMessage(res));
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "converted-files.zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

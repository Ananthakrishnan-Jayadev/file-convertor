export type FormatMap = Record<string, { category: string; outputs: string[] }>;

export type Job = {
  id: string;
  operation: "convert" | "combine" | "split";
  filename: string;
  target_format: string;
  max_bytes: number | null;
  status: "queued" | "running" | "done" | "error";
  error: string | null;
  input_size: number;
  output_name: string | null;
  output_size: number | null;
  target_met: boolean | null;
  note: string;
};

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
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function createJob(file: File, target: string, maxSizeKb: number | null): Promise<Job> {
  const body = new FormData();
  body.append("file", file);
  body.append("target_format", target);
  if (maxSizeKb) body.append("max_size_kb", String(maxSizeKb));
  const res = await fetch("/api/jobs", { method: "POST", body });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function combinePdf(files: File[], outputName: string, maxSizeKb: number | null): Promise<Job> {
  const body = new FormData();
  files.forEach((f) => body.append("files", f));
  body.append("output_name", outputName);
  if (maxSizeKb) body.append("max_size_kb", String(maxSizeKb));
  const res = await fetch("/api/pdf/combine", { method: "POST", body });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

/** `ranges` like "1-3, 5, 8-"; empty means one PDF per page. */
export async function splitPdf(file: File, ranges: string, maxSizeKb: number | null): Promise<Job> {
  const body = new FormData();
  body.append("file", file);
  body.append("ranges", ranges);
  if (maxSizeKb) body.append("max_size_kb", String(maxSizeKb));
  const res = await fetch("/api/pdf/split", { method: "POST", body });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`/api/jobs/${id}`);
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export const downloadUrl = (id: string) => `/api/jobs/${id}/download`;

export async function downloadArchive(ids: string[]): Promise<void> {
  const res = await fetch("/api/archive", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "converted-files.zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

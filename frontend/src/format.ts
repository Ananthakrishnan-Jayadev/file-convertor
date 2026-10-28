const ALIASES: Record<string, string> = {
  jpeg: "jpg", jpe: "jpg", tif: "tiff", heif: "heic", htm: "html", yml: "yaml", markdown: "md",
};

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  const ext = dot === -1 ? "" : name.slice(dot + 1).toLowerCase();
  return ALIASES[ext] ?? ext;
}

export function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// What people usually want from each kind of file; the first one that applies wins.
const PREFERRED: Record<string, string[]> = {
  image: ["jpg", "png"],
  document: ["pdf", "docx"],
  presentation: ["pdf"],
  spreadsheet: ["xlsx", "csv"],
  pdf: ["docx"],
  data: ["csv", "yaml", "json"],
};

export function defaultTarget(ext: string, category: string, outputs: string[]): string {
  const pick = (PREFERRED[category] ?? []).find((f) => f !== ext && outputs.includes(f));
  return pick ?? outputs.find((f) => f !== ext) ?? ext;
}

export const CATEGORY_NAMES: Record<string, string> = {
  image: "Image",
  document: "Document",
  presentation: "Slides",
  spreadsheet: "Spreadsheet",
  pdf: "PDF",
  data: "Data",
};

import type { FormatMap } from "./api";

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
  audio: ["mp3", "m4a"],
  video: ["mp4", "webm"],
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
  audio: "Audio",
  video: "Video",
};

export type FormatGroup = { name: string; exts: string[] };

/** Extensions sorted into their kinds of file, in a fixed order, so the list reads as groups instead of one wall. */
export function groupFormats(formats: FormatMap, only?: string[]): FormatGroup[] {
  const exts = Object.keys(formats).filter((e) => !only || only.includes(e));
  const groups: FormatGroup[] = Object.entries(CATEGORY_NAMES)
    .map(([category, name]) => ({ name, exts: exts.filter((e) => formats[e].category === category).sort() }))
    .filter((g) => g.exts.length > 0);
  // A kind the server knows but this list doesn't name yet still shows up.
  const rest = exts.filter((e) => !(formats[e].category in CATEGORY_NAMES)).sort();
  if (rest.length > 0) groups.push({ name: "Other", exts: rest });
  return groups;
}

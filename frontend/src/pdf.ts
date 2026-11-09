import type { PDFDocumentProxy } from "pdfjs-dist";

// pdf.js is large, so it's only downloaded the first time a PDF needs previewing.
let lib: Promise<typeof import("pdfjs-dist")> | null = null;

function pdfjs() {
  lib ??= Promise.all([import("pdfjs-dist"), import("pdfjs-dist/build/pdf.worker.min.mjs?url")]).then(
    ([mod, worker]) => {
      mod.GlobalWorkerOptions.workerSrc = worker.default;
      return mod;
    },
  );
  return lib;
}

export async function openPdf(file: File): Promise<PDFDocumentProxy> {
  const { getDocument } = await pdfjs();
  return getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
}

/** Render one page (1-based) as a JPEG object URL about `width` CSS pixels wide. Revoke it when done. */
export async function renderPage(doc: PDFDocumentProxy, pageNumber: number, width: number): Promise<string> {
  const page = await doc.getPage(pageNumber);
  const scale = (width / page.getViewport({ scale: 1 }).width) * Math.min(window.devicePixelRatio || 1, 2);
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  await page.render({ canvasContext: canvas.getContext("2d")!, viewport }).promise;
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.82));
  if (!blob) throw new Error("Couldn't draw this page.");
  return URL.createObjectURL(blob);
}

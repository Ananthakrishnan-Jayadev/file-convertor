import { useEffect, useState } from "react";
import { extensionOf } from "./format";
import { openPdf, renderPage } from "./pdf";

// Formats every current browser can show in an <img>. HEIC and TIFF get a format label instead.
export const BROWSER_IMAGES = new Set(["png", "jpg", "webp", "gif", "bmp", "avif", "ico"]);

/** A small preview of a local file: the image itself, a PDF's first page, or its format. */
export default function Thumb({ file, size = 48 }: { file: File; size?: number }) {
  const ext = extensionOf(file.name);
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let made: string | null = null;
    let cancelled = false;
    if (BROWSER_IMAGES.has(ext)) {
      made = URL.createObjectURL(file);
      setUrl(made);
    } else if (ext === "pdf") {
      openPdf(file)
        .then(async (doc) => {
          const page = await renderPage(doc, 1, size * 2);
          doc.destroy();
          if (cancelled) URL.revokeObjectURL(page);
          else setUrl((made = page));
        })
        .catch(() => {}); // damaged PDFs just show the label
    }
    return () => {
      cancelled = true;
      if (made) URL.revokeObjectURL(made);
      setUrl(null);
    };
  }, [file, ext, size]);

  return (
    <span className="thumb" style={{ width: size, height: size }} aria-hidden="true">
      {url ? <img src={url} alt="" /> : <span className="thumb-label">{ext.toUpperCase() || "?"}</span>}
    </span>
  );
}

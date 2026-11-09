import type { PDFDocumentProxy } from "pdfjs-dist";
import { useEffect, useRef, useState } from "react";
import { renderPage } from "./pdf";

const THUMB_WIDTH = 120;

type Props = {
  doc: PDFDocumentProxy;
  selected: Set<number>;
  onChange: (pages: Set<number>) => void;
};

/**
 * Grid of page thumbnails. Click toggles a page; Shift+click selects everything since the last click.
 * On touch there is no Shift, so "Select a range" turns the next two taps into the start and end of a run.
 */
export default function PagePicker({ doc, selected, onChange }: Props) {
  const [thumbs, setThumbs] = useState<Record<number, string>>({});
  const lastClicked = useRef<number | null>(null);
  const [rangeMode, setRangeMode] = useState(false);
  const [anchor, setAnchor] = useState<number | null>(null);
  const count = doc.numPages;

  // Render pages one after another so the first ones appear quickly even in long PDFs.
  useEffect(() => {
    let cancelled = false;
    const made: string[] = [];
    (async () => {
      for (let p = 1; p <= count && !cancelled; p++) {
        try {
          const url = await renderPage(doc, p, THUMB_WIDTH);
          made.push(url);
          if (!cancelled) setThumbs((prev) => ({ ...prev, [p]: url }));
        } catch {
          /* leave the placeholder */
        }
      }
    })();
    return () => {
      cancelled = true;
      made.forEach(URL.revokeObjectURL);
      setThumbs({});
      setRangeMode(false);
      setAnchor(null);
    };
  }, [doc, count]);

  function addRun(from: number, to: number) {
    const next = new Set(selected);
    const [a, b] = [from, to].sort((x, y) => x - y);
    for (let p = a; p <= b; p++) next.add(p);
    onChange(next);
  }

  function click(page: number, shift: boolean) {
    if (rangeMode) {
      if (anchor == null) {
        setAnchor(page);
      } else {
        addRun(anchor, page);
        setAnchor(null);
        setRangeMode(false);
      }
      lastClicked.current = page;
      return;
    }
    const next = new Set(selected);
    if (shift && lastClicked.current != null) {
      const [a, b] = [lastClicked.current, page].sort((x, y) => x - y);
      for (let p = a; p <= b; p++) next.add(p);
    } else if (next.has(page)) {
      next.delete(page);
    } else {
      next.add(page);
    }
    lastClicked.current = page;
    onChange(next);
  }

  function toggleRangeMode() {
    setRangeMode((on) => !on);
    setAnchor(null);
  }

  const all = Array.from({ length: count }, (_, i) => i + 1);
  const rangeHint = !rangeMode
    ? null
    : anchor == null
      ? "Choose the first page of the range."
      : `The range starts at page ${anchor}. Now choose the last page.`;

  return (
    <div className="page-picker">
      <div className="page-picker-bar">
        <span className="hint" aria-live="polite">
          {selected.size} of {count} pages selected.{" "}
          {rangeHint ?? <span className="fine-only">Shift+click selects a run of pages.</span>}
        </span>
        <span className="page-picker-actions">
          <button
            className={rangeMode ? "btn btn-small range-toggle is-on" : "btn btn-quiet btn-small range-toggle"}
            aria-pressed={rangeMode}
            onClick={toggleRangeMode}
          >
            Select a range
          </button>
          <button className="btn btn-quiet btn-small" onClick={() => onChange(new Set(all))}>
            Select all
          </button>
          <button className="btn btn-quiet btn-small" onClick={() => onChange(new Set())} disabled={!selected.size}>
            Clear
          </button>
        </span>
      </div>
      <div className={rangeMode ? "page-grid is-ranging" : "page-grid"}>
        {all.map((p) => (
          <button
            key={p}
            className={["page-tile", selected.has(p) && "is-on", anchor === p && "is-anchor"].filter(Boolean).join(" ")}
            aria-pressed={selected.has(p)}
            aria-label={anchor === p ? `Page ${p}, start of the range` : `Page ${p}`}
            onClick={(e) => click(p, e.shiftKey)}
          >
            <span className="page-img">{thumbs[p] ? <img src={thumbs[p]} alt="" /> : null}</span>
            <span className="page-num">{p}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

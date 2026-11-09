import type { PDFDocumentProxy } from "pdfjs-dist";
import { useEffect, useState } from "react";
import { splitPdf } from "./api";
import DropZone from "./DropZone";
import { extensionOf, humanSize } from "./format";
import Icon from "./Icon";
import JobResult from "./JobResult";
import PagePicker from "./PagePicker";
import { openPdf } from "./pdf";
import { parseRanges, toRanges } from "./ranges";
import SizeLimitPicker from "./SizeLimitPicker";
import Thumb from "./Thumb";
import { useJob } from "./useJob";

type Props = {
  maxUpload: number;
  /** Tells the page whether this tool has a file, so the masthead can step back. */
  onHasFiles: (has: boolean) => void;
};

export default function SplitTool({ maxUpload, onHasFiles }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [mode, setMode] = useState<"pages" | "select">("pages");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [rangesText, setRangesText] = useState("");
  const [together, setTogether] = useState(true);
  const [limitKb, setLimitKb] = useState<number | null>(null);
  const [limitOk, setLimitOk] = useState(true);
  const task = useJob();

  const hasFile = file !== null;
  useEffect(() => {
    onHasFiles(hasFile);
  }, [hasFile, onHasFiles]);

  // Open the PDF in the browser for page previews. If that fails, typed ranges still work.
  useEffect(() => {
    if (!file) return;
    let current: PDFDocumentProxy | null = null;
    let cancelled = false;
    openPdf(file)
      .then((d) => {
        if (cancelled) d.destroy();
        else setDoc((current = d));
      })
      .catch(() => setDoc(null));
    return () => {
      cancelled = true;
      current?.destroy();
      setDoc(null);
    };
  }, [file]);

  function choose([f]: File[]) {
    task.reset();
    if (extensionOf(f.name) !== "pdf") return setFileError(`${f.name} isn't a PDF.`);
    if (maxUpload && f.size > maxUpload) return setFileError(`Files can be at most ${humanSize(maxUpload)}.`);
    setFileError(null);
    setSelected(new Set());
    setRangesText("");
    setFile(f);
  }

  function pick(pages: Set<number>) {
    setSelected(pages);
    setRangesText(toRanges(pages));
    task.reset();
  }

  function type(text: string) {
    setRangesText(text);
    task.reset();
    if (doc) {
      const parsed = parseRanges(text, doc.numPages);
      if ("pages" in parsed) setSelected(parsed.pages);
    }
  }

  // With the page count known, check ranges here; otherwise the server checks them on upload.
  const parsed = doc && rangesText.trim() ? parseRanges(rangesText, doc.numPages) : null;
  const rangeError = parsed && "error" in parsed ? parsed.error : null;
  const selectInvalid = mode === "select" && (!rangesText.trim() || rangeError !== null);
  // Why the button can't be used yet, said beside it since the cause may be scrolled out of view.
  const blockedReason = task.busy
    ? null
    : mode === "select" && !rangesText.trim()
      ? "Choose the pages you want first."
      : selectInvalid
        ? "Check the pages you typed."
        : !limitOk
          ? "Fix the size limit first."
          : null;

  return (
    <>
      {!file && <DropZone title="Drop a PDF here or choose one" accept={["pdf"]} multiple={false} onFiles={choose} />}
      {fileError && <p className="banner banner-error">{fileError}</p>}

      {file && (
        <section className={mode === "select" ? "workbench has-side" : "workbench"} aria-label="PDF to split">
          <div className="work-side">
            <div className="file-row">
              <div className="file-head">
                <span className="file-title">
                  <Thumb file={file} />
                  <span className="file-name" title={file.name}>
                    {file.name}
                  </span>
                </span>
                <button
                  className="icon-btn"
                  onClick={() => {
                    setFile(null);
                    task.reset();
                  }}
                  disabled={task.busy}
                  aria-label={`Remove ${file.name}`}
                >
                  <Icon name="close" />
                </button>
              </div>
              <p className="status">
                {humanSize(file.size)}
                {doc && `, ${doc.numPages} ${doc.numPages === 1 ? "page" : "pages"}`}
              </p>
            </div>

            <fieldset className="field split-mode">
              <legend className="field-label">Split into</legend>
              <label className="radio">
                <input type="radio" name="split-mode" checked={mode === "pages"} onChange={() => setMode("pages")} />
                One PDF per page
              </label>
              <label className="radio">
                <input type="radio" name="split-mode" checked={mode === "select"} onChange={() => setMode("select")} />
                Pages I choose
              </label>
            </fieldset>

            {mode === "select" && (
              <div className="select-pages">
                <label className="ranges">
                  <span className="field-label">Pages</span>
                  <input
                    type="text"
                    value={rangesText}
                    placeholder="1-3, 5, 8-"
                    aria-invalid={rangeError !== null}
                    aria-describedby="ranges-hint"
                    onChange={(e) => type(e.target.value)}
                  />
                  <span id="ranges-hint" className={rangeError ? "hint status-error" : "hint"}>
                    {rangeError ??
                      `Use commas between pages and a dash for a run: 8- means page 8 to the end.${doc ? " Or pick them in the page previews." : ""}`}
                  </span>
                </label>
                <fieldset className="field">
                  <legend className="field-label">Save as</legend>
                  <label className="radio">
                    <input type="radio" name="split-together" checked={together} onChange={() => setTogether(true)} />
                    One PDF with these pages
                  </label>
                  <label className="radio">
                    <input type="radio" name="split-together" checked={!together} onChange={() => setTogether(false)} />
                    A separate PDF for each group (like 1-3 and 5)
                  </label>
                </fieldset>
              </div>
            )}

            <div className="controls">
              <SizeLimitPicker
                value={limitKb}
                onChange={setLimitKb}
                hint="Applies to each PDF you get back."
                onValidChange={setLimitOk}
              />
            </div>
          </div>

          <div className="work-main">
            {mode === "select" && doc && <PagePicker doc={doc} selected={selected} onChange={pick} />}

            <div className="actions">
              <button
                className="btn btn-primary"
                disabled={task.busy || selectInvalid || !limitOk}
                aria-describedby={blockedReason ? "split-blocked" : undefined}
                onClick={() =>
                  task.start((signal) =>
                    mode === "select"
                      ? splitPdf(file, rangesText, together, limitKb, signal)
                      : splitPdf(file, "", false, limitKb, signal),
                  )
                }
              >
                {task.busy ? "Splitting…" : mode === "select" && together ? "Make PDF" : "Split PDF"}
              </button>
              {blockedReason && (
                <p id="split-blocked" className="hint action-hint">
                  {blockedReason}
                </p>
              )}
            </div>

            <JobResult task={task} verb="Splitting" />
          </div>
        </section>
      )}
    </>
  );
}

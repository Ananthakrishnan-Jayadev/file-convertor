import { useState } from "react";
import { splitPdf } from "./api";
import DropZone from "./DropZone";
import { extensionOf, humanSize } from "./format";
import JobResult from "./JobResult";
import SizeLimitPicker from "./SizeLimitPicker";
import { useJob } from "./useJob";

// Rough shape check only; the server checks the numbers against the real page count.
const RANGES = /^\s*(\d*\s*-\s*\d*|\d+)(\s*,\s*(\d*\s*-\s*\d*|\d+))*\s*,?\s*$/;

export default function SplitTool({ maxUpload }: { maxUpload: number }) {
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [mode, setMode] = useState<"pages" | "ranges">("pages");
  const [ranges, setRanges] = useState("");
  const [limitKb, setLimitKb] = useState<number | null>(null);
  const task = useJob();

  function choose([f]: File[]) {
    task.reset();
    if (extensionOf(f.name) !== "pdf") {
      setFileError(`${f.name} isn't a PDF.`);
      return;
    }
    if (maxUpload && f.size > maxUpload) {
      setFileError(`Files can be at most ${humanSize(maxUpload)}.`);
      return;
    }
    setFileError(null);
    setFile(f);
  }

  const rangesInvalid = mode === "ranges" && (!ranges.trim() || !RANGES.test(ranges));

  return (
    <>
      {!file && <DropZone title="Drop a PDF here" accept={["pdf"]} multiple={false} onFiles={choose} />}
      {fileError && <p className="banner banner-error">{fileError}</p>}

      {file && (
        <section className="workbench" aria-label="PDF to split">
          <div className="file-row">
            <div className="file-head">
              <span className="file-name" title={file.name}>
                {file.name}
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
                ×
              </button>
            </div>
            <p className="status">{humanSize(file.size)}</p>
          </div>

          <div className="controls">
            <fieldset className="field">
              <legend className="field-label">Split into</legend>
              <label className="radio">
                <input type="radio" checked={mode === "pages"} onChange={() => setMode("pages")} />
                One PDF per page
              </label>
              <label className="radio">
                <input type="radio" checked={mode === "ranges"} onChange={() => setMode("ranges")} />
                Page ranges I choose
              </label>
              {mode === "ranges" && (
                <label className="ranges">
                  <span className="visually-hidden">Page ranges</span>
                  <input
                    type="text"
                    value={ranges}
                    placeholder="1-3, 5, 8-"
                    aria-invalid={ranges.trim() !== "" && rangesInvalid}
                    aria-describedby="ranges-hint"
                    onChange={(e) => setRanges(e.target.value)}
                  />
                  <span id="ranges-hint" className="hint">
                    Each range becomes its own PDF. Use 8- for page 8 to the end.
                  </span>
                </label>
              )}
            </fieldset>
            <SizeLimitPicker value={limitKb} onChange={setLimitKb} hint="Applies to each PDF you get back." />
          </div>

          <div className="actions">
            <button
              className="btn btn-primary"
              disabled={task.busy || rangesInvalid}
              onClick={() => task.start(() => splitPdf(file, mode === "ranges" ? ranges : "", limitKb))}
            >
              {task.busy ? "Splitting…" : "Split PDF"}
            </button>
          </div>

          <JobResult task={task} verb="Splitting" />
        </section>
      )}
    </>
  );
}

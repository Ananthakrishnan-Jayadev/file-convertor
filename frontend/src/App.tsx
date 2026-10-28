import { useEffect, useState } from "react";
import { FormatMap, getFormats } from "./api";
import CombineTool from "./CombineTool";
import ConvertTool from "./ConvertTool";
import SplitTool from "./SplitTool";

const TOOLS = [
  { id: "convert", label: "Convert files" },
  { id: "combine", label: "Combine into PDF" },
  { id: "split", label: "Split PDF" },
] as const;
type ToolId = (typeof TOOLS)[number]["id"];

export default function App() {
  const [formats, setFormats] = useState<FormatMap | null>(null);
  const [maxUpload, setMaxUpload] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tool, setTool] = useState<ToolId>("convert");

  useEffect(() => {
    getFormats()
      .then((r) => {
        setFormats(r.formats);
        setMaxUpload(r.max_upload_bytes);
      })
      .catch(() => setLoadError("Can't reach the conversion server. Check that the server is running (fileconvert serve)."));
  }, []);

  return (
    <main className="page">
      <header className="masthead">
        <h1>Convert files and shrink them to size</h1>
        <p className="lede">
          Images, documents, slides, spreadsheets, PDFs and data files. Convert them, combine images and PDFs into
          one PDF, or split a PDF apart, with an optional size limit. Files are deleted from the server after an hour.
        </p>
      </header>

      {loadError && <p className="banner banner-error">{loadError}</p>}

      <div className="tabs" role="tablist" aria-label="Tools">
        {TOOLS.map((t) => (
          <button
            key={t.id}
            id={`tab-${t.id}`}
            role="tab"
            aria-selected={tool === t.id}
            aria-controls={`panel-${t.id}`}
            className={tool === t.id ? "tab is-on" : "tab"}
            onClick={() => setTool(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* All tools stay mounted so switching tabs keeps each one's files and results. */}
      <div id="panel-convert" role="tabpanel" aria-labelledby="tab-convert" hidden={tool !== "convert"}>
        <ConvertTool formats={formats} maxUpload={maxUpload} />
      </div>
      <div id="panel-combine" role="tabpanel" aria-labelledby="tab-combine" hidden={tool !== "combine"}>
        <CombineTool formats={formats} maxUpload={maxUpload} />
      </div>
      <div id="panel-split" role="tabpanel" aria-labelledby="tab-split" hidden={tool !== "split"}>
        <SplitTool maxUpload={maxUpload} />
      </div>
    </main>
  );
}

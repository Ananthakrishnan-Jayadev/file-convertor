import { type KeyboardEvent, useEffect, useRef, useState } from "react";
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
type Theme = "light" | "dark";

// Browser chrome colours that match each theme's paper (see styles.css).
const THEME_COLOR: Record<Theme, string> = { light: "#f8f3e9", dark: "#1e1814" };

function applyTheme(theme: Theme) {
  if (theme === "dark") document.documentElement.dataset.theme = "dark";
  else delete document.documentElement.dataset.theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[theme]);
  try {
    localStorage.setItem("theme", theme);
  } catch {
    /* private browsing: the choice just isn't remembered */
  }
}

export default function App() {
  const [formats, setFormats] = useState<FormatMap | null>(null);
  const [maxUpload, setMaxUpload] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tool, setTool] = useState<ToolId>("convert");
  // Once any tool holds files, the masthead steps back so the work sits higher on the screen.
  const [convertHas, setConvertHas] = useState(false);
  const [combineHas, setCombineHas] = useState(false);
  const [splitHas, setSplitHas] = useState(false);
  const working = convertHas || combineHas || splitHas;
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  // index.html has already applied a remembered choice before React started.
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }

  // One Tab stop for the row; arrows, Home and End move between tools and open them.
  function onTabKey(e: KeyboardEvent<HTMLButtonElement>, i: number) {
    const last = TOOLS.length - 1;
    const next =
      e.key === "ArrowRight" ? (i === last ? 0 : i + 1)
      : e.key === "ArrowLeft" ? (i === 0 ? last : i - 1)
      : e.key === "Home" ? 0
      : e.key === "End" ? last
      : null;
    if (next === null) return;
    e.preventDefault();
    setTool(TOOLS[next].id);
    tabRefs.current[next]?.focus();
  }

  useEffect(() => {
    getFormats()
      .then((r) => {
        setFormats(r.formats);
        setMaxUpload(r.max_upload_bytes);
      })
      .catch(() => setLoadError("Can't reach the conversion server. Check that the server is running (fileconvert serve)."));
  }, []);

  return (
    <main className={working ? "page is-working" : "page"}>
      <header className="masthead">
        <div className="masthead-text">
          <h1>Convert files and shrink them to size</h1>
          {!working && (
            <p className="lede">
              Images, documents, slides, spreadsheets, PDFs, data, audio and video. Convert them, combine images and
              PDFs into one PDF, or split a PDF apart, with an optional size limit. Files are deleted from the server
              after an hour.
            </p>
          )}
        </div>
        <button className="btn btn-quiet btn-small theme-switch" aria-pressed={theme === "dark"} onClick={toggleTheme}>
          Dark mode
        </button>
      </header>

      {loadError && <p className="banner banner-error">{loadError}</p>}

      <div className="tabs" role="tablist" aria-label="Tools">
        {TOOLS.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => {
              tabRefs.current[i] = el;
            }}
            type="button"
            id={`tab-${t.id}`}
            role="tab"
            aria-selected={tool === t.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={tool === t.id ? 0 : -1}
            className={tool === t.id ? "tab is-on" : "tab"}
            onClick={() => setTool(t.id)}
            onKeyDown={(e) => onTabKey(e, i)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* All tools stay mounted so switching tabs keeps each one's files and results. */}
      <div id="panel-convert" role="tabpanel" aria-labelledby="tab-convert" hidden={tool !== "convert"}>
        <ConvertTool formats={formats} maxUpload={maxUpload} onHasFiles={setConvertHas} />
      </div>
      <div id="panel-combine" role="tabpanel" aria-labelledby="tab-combine" hidden={tool !== "combine"}>
        <CombineTool formats={formats} maxUpload={maxUpload} onHasFiles={setCombineHas} />
      </div>
      <div id="panel-split" role="tabpanel" aria-labelledby="tab-split" hidden={tool !== "split"}>
        <SplitTool maxUpload={maxUpload} onHasFiles={setSplitHas} />
      </div>
    </main>
  );
}

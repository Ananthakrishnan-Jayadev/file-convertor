# File Converter

A self-hosted web app that converts files between formats and can shrink the result to fit
under a size limit: under 5 MB, under 1 MB, under 500 KB, or any custom size.

Drop in images, documents, slides, spreadsheets, PDFs or data files, choose an output format
for each one, optionally pick a size limit, and download the results one by one or as a single
zip. It can also combine images and PDFs into one PDF, and split a PDF into pages or ranges.
Everything runs on your own machine, and uploaded files are deleted after an hour.

## Features

- **Many formats in one place:** images, Office and OpenDocument files, PDFs, spreadsheets,
  JSON/YAML/XML (see the table below).
- **Size limit:** each file is shrunk with the method that loses the least quality for its type.
  If the limit can't be reached, the app keeps the smallest version it managed and tells you
  how big it is.
- **Batch conversion:** convert many files at once, set a format per file or for all of them,
  and download everything as one zip.
- **Shrink only:** keep a file's format and just make it smaller.
- **Combine into one PDF:** mix images and PDFs, put them in the order you want, and get one
  PDF. Each image becomes a page the same shape as the image.
- **Split a PDF:** one PDF per page, or your own ranges such as `1-3, 5, 8-`, where each range
  becomes its own PDF. The size limit applies to each PDF you get back.
- **One command to run:** `fileconvert serve` builds the UI and serves the UI and API on port 8000.

## Supported conversions

| From | To |
|---|---|
| **Images**: PNG, JPG, WEBP, AVIF, HEIC, GIF, BMP, TIFF, ICO | Any of those, or PDF |
| **Documents**: DOCX, DOC, ODT, RTF, TXT, HTML, Markdown | DOCX, DOC, ODT, RTF, TXT, HTML, Markdown, PDF |
| **Slides**: PPTX, PPT, ODP | PPTX, PPT, ODP, PDF |
| **Spreadsheets**: CSV, TSV, XLSX, XLS, ODS | CSV, TSV, XLSX, ODS, JSON, HTML, PDF |
| **PDF** | DOCX, TXT, PNG / JPG / WEBP (one image per page) |
| **Data**: JSON, YAML, XML | JSON, YAML, XML; JSON also to CSV, TSV, XLSX, ODS, HTML |

A few conversions produce several files. Those come back as one zip:
- a PDF with several pages converted to images gives one image per page;
- a workbook with several sheets converted to CSV, TSV or HTML gives one file per sheet.

### PDF tools

| Tool | Input | Output |
|---|---|---|
| **Combine into PDF** | Any mix of images (PNG, JPG, WEBP, AVIF, HEIC, GIF, BMP, TIFF, ICO) and PDFs, in your order | One PDF |
| **Split PDF** | One PDF, plus "every page" or ranges like `1-3, 5, 8-` | One PDF per page or range; several parts come back as a zip |

Ranges: `5` is one page, `2-4` is pages 2 to 4, `8-` runs to the last page, `-3` is pages 1 to 3.

## How the size limit works

| Result type | What the app does |
|---|---|
| JPG, WEBP, AVIF, HEIC | Finds the highest quality (92 down to 30) that fits, then scales the image down if quality alone isn't enough |
| PNG, GIF, TIFF, BMP | Optimises the file, reduces it to a 256-colour palette, then scales it down |
| PDF | Re-renders the PDF with Ghostscript, lowering image resolution step by step from 220 to 50 dpi |
| DOCX, PPTX, XLSX, ODT, ODP, ODS, EPUB | Recompresses the pictures inside the file, leaving text and layout untouched |
| CSV, TXT, JSON and other text files | These can't shrink without losing data, so they're packed into a zip |
| Zip of several results (PDF pages, split parts, sheets) | The limit applies to each file inside, using the method for that file's type |

## Getting started

Works on **Linux, macOS and Windows**.

### Requirements

- Python 3.11 or newer
- Node.js 18 or newer, with npm
- LibreOffice, for documents, slides and spreadsheet-to-PDF
- Ghostscript, for PDF compression

| Platform | Install LibreOffice and Ghostscript |
|---|---|
| Ubuntu / Debian | `sudo apt install libreoffice ghostscript` |
| macOS (Homebrew) | `brew install --cask libreoffice` and `brew install ghostscript` |
| Windows (PowerShell) | `winget install TheDocumentFoundation.LibreOffice` and `winget install ArtifexSoftware.GhostScript` |

The app finds both programs on its own, either on `PATH` or in their default install folders
(`C:\Program Files\LibreOffice`, `C:\Program Files\gs`, `/Applications/LibreOffice.app`).
If you installed them somewhere else, set `SOFFICE_BIN` and `GS_BIN`.
The app still starts without them; only the conversions that need them fail.

### Install and run on Linux / macOS

```bash
git clone <this-repo> file_conversion
cd file_conversion

python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[test]"   # also creates the `fileconvert` command
(cd frontend && npm install)

backend/.venv/bin/fileconvert serve
```

### Install and run on Windows (PowerShell)

```powershell
git clone <this-repo> file_conversion
cd file_conversion

py -m venv backend\.venv
backend\.venv\Scripts\pip install -e "backend[test]"
cd frontend; npm install; cd ..

backend\.venv\Scripts\fileconvert serve
```

Then open **http://localhost:8000**.

- `--port 9000` uses a different port.
- `--host 0.0.0.0` lets other devices on your network, such as your phone, reach the app.

Backend code changes reload automatically. After changing the UI, stop the server with Ctrl+C and
run the command again so the UI is rebuilt.

### Run with Docker

The image includes LibreOffice and Ghostscript, so nothing else needs installing:

```bash
docker compose up --build      # http://localhost:8000
```

## Tests

```bash
cd backend
.venv/bin/pytest                    # full suite   (Windows: .venv\Scripts\pytest)
.venv/bin/pytest -m "not slow"      # skip the LibreOffice and PDF-to-DOCX tests
```

Tests that need LibreOffice or Ghostscript are skipped automatically when those aren't installed.

## How it works

```
Browser (React)                     FastAPI                               Worker threads
───────────────                     ───────                               ──────────────
POST /api/jobs  (file, format,  ──▶ checks the type, saves the upload ──▶ convert ─▶ shrink to limit
                 size limit)        returns a job id
POST /api/pdf/combine | split   ──▶ same, for the PDF tools           ──▶ combine / split ─▶ shrink
GET  /api/jobs/{id}  (every 1s) ──▶ queued / running / done / error
GET  /api/jobs/{id}/download    ──▶ the converted file
```

- **Registry** (`registry.py`): every converter declares which input and output formats it
  handles. The UI's format menus come from the same list, so the backend and UI never disagree.
- **Converters** (`converters/`): images use Pillow and pillow-heif; documents and slides use
  headless LibreOffice; spreadsheets use pandas; PDFs use PyMuPDF and pdf2docx; data formats use
  PyYAML and xmltodict.
- **PDF tools** (`pdftools.py`): combining and splitting with PyMuPDF. Page ranges are checked
  when you upload, so a typo is reported straight away.
- **Size controller** (`compress.py`): the strategies in the table above.
- **Jobs** (`jobs.py`): conversions run on a thread pool, and finished files are deleted after
  `FC_JOB_TTL` seconds.

### API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/formats` | Every supported input format and what it can become |
| `POST` | `/api/jobs` | Start a conversion. Form fields: `file`, `target_format`, optional `max_size_kb` |
| `POST` | `/api/pdf/combine` | Combine images and PDFs. Form fields: `files` (repeat, in page order), optional `output_name`, `max_size_kb` |
| `POST` | `/api/pdf/split` | Split a PDF. Form fields: `file`, optional `ranges` (empty means every page), `max_size_kb` |
| `GET` | `/api/jobs/{id}` | Job status, sizes, and a note when the size limit wasn't met |
| `GET` | `/api/jobs/{id}/download` | Download the result |
| `POST` | `/api/archive` | `{"ids": [...]}` returns the finished files as one zip |

Interactive API docs are at http://localhost:8000/docs while the server is running.

## Project layout

```
backend/
  app/
    main.py          API endpoints; also serves the built UI
    cli.py           the `fileconvert serve` command
    tools.py         finds LibreOffice and Ghostscript on Linux, macOS and Windows
    jobs.py          job queue, temporary storage, cleanup
    registry.py      which converter handles which conversion
    compress.py      the size controller
    pdftools.py      combine images/PDFs into one PDF, split a PDF
    converters/      images, pdf, sheets, documents (LibreOffice), data
  tests/             pytest suite
  pyproject.toml     dependencies and the `fileconvert` command
frontend/
  src/               React UI: Convert, Combine into PDF and Split PDF tools, size limit picker, size meter
Dockerfile           single image: builds the UI, installs LibreOffice and Ghostscript
docker-compose.yml
```

## Configuration

Set these as environment variables before running `fileconvert serve` or in `docker-compose.yml`.

| Variable | Default | Meaning |
|---|---|---|
| `FC_MAX_UPLOAD_MB` | `200` | Largest file that can be uploaded |
| `FC_JOB_TTL` | `3600` | Seconds before uploaded and converted files are deleted |
| `FC_WORKERS` | half the CPU cores | How many conversions run at the same time |
| `FC_DATA_DIR` | system temp folder | Where uploads and results are stored |
| `SOFFICE_BIN`, `GS_BIN` | found automatically | Custom paths to LibreOffice and Ghostscript |

## Known limitations

- **PDF to DOCX** is close but not perfect for complex layouts such as multiple columns,
  floating images or forms.
- **LibreOffice output** can differ slightly from Microsoft Office in fonts and spacing.
- **Animated GIFs** keep only their first frame.
- **CSV to Excel** guesses column types, so codes with leading zeros, like `00123`, become numbers.
- **Job status is kept in memory**: restarting the server forgets jobs that are running or finished.
- **File types are recognised by extension**: a misnamed file fails during conversion and
  shows an error.

## Roadmap

- Audio and video with FFmpeg, including exact target sizes for video
- OCR for scanned PDFs (OCRmyPDF) and ebook formats (Calibre)
- Celery or RQ with Redis instead of the in-process queue, for running several servers
- Checking file contents, not just extensions, before converting

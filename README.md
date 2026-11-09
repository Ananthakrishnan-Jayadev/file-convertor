# File Converter

A self-hosted web app that converts files between formats and can shrink the result to fit
under a size limit: under 5 MB, under 1 MB, under 500 KB, or any custom size.

Drop in images, documents, slides, spreadsheets, PDFs, data, audio or video files, choose an output format
for each one, optionally pick a size limit, and download the results one by one or as a single
zip. It can also combine images and PDFs into one PDF, and split a PDF into pages or ranges.
Everything runs on your own machine, and uploaded files are deleted after an hour.

## Features

- **Many formats in one place:** images, Office and OpenDocument files, PDFs, spreadsheets,
  JSON/YAML/XML, audio and video (see the table below).
- **Size limit:** each file is shrunk with the method that loses the least quality for its type.
  If the limit can't be reached, the app keeps the smallest version it managed and tells you
  how big it is.
- **Batch conversion:** convert many files at once, set a format per file or for all of them,
  and download everything as one zip.
- **Shrink only:** keep a file's format and just make it smaller.
- **Image options:** resize (percentage, or fit inside a box), rotate, set the quality yourself,
  and choose whether to keep photo details. Date, camera and GPS location are removed unless you
  ask to keep them. Colour profiles are always kept, so colours don't shift.
- **Previews:** thumbnails for images and PDFs, and a side-by-side comparison of the original and
  the result, to judge how much quality shrinking cost.
- **Combine into one PDF:** mix images and PDFs, drag them into the order you want, and get one
  PDF. Each image becomes a page the same shape as the image.
- **Split a PDF:** one PDF per page, or pick pages by clicking their thumbnails (or typing ranges
  such as `1-3, 5, 8-`) and get them as one PDF or one PDF per group. The size limit applies to
  each PDF you get back.
- **Cancel anytime:** stop an upload or a conversion that's taking too long.
- **Safe with your files:** contents are checked against the extension, conversions survive a
  server restart (or fail with a clear message), and everything is deleted after an hour.
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
| **Audio**: MP3, WAV, AAC, M4A, OGG, FLAC, OPUS | Any of those |
| **Video**: MP4, MOV, WEBM, MKV, AVI | Any of those, an animated GIF, or the sound track as any audio format |

A few conversions produce several files. Those come back as one zip:
- a PDF with several pages converted to images gives one image per page;
- a workbook with several sheets converted to CSV, TSV or HTML gives one file per sheet.

### PDF tools

| Tool | Input | Output |
|---|---|---|
| **Combine into PDF** | Any mix of images (PNG, JPG, WEBP, AVIF, HEIC, GIF, BMP, TIFF, ICO) and PDFs, in your order | One PDF |
| **Split PDF** | One PDF, plus "every page" or the pages you pick | One PDF per page, one PDF of the picked pages, or one PDF per group of pages; several PDFs come back as a zip |

Ranges: `5` is one page, `2-4` is pages 2 to 4, `8-` runs to the last page, `-3` is pages 1 to 3.

## How the size limit works

| Result type | What the app does |
|---|---|
| JPG, WEBP, AVIF, HEIC | Finds the highest quality (92 down to 30) that fits, then scales the image down if quality alone isn't enough |
| PNG, GIF, TIFF, BMP | Optimises the file, reduces it to a 256-colour palette, then scales it down |
| Animated GIF | Scales every frame down and, when far over the limit, drops frames, so it stays animated |
| PDF | Re-renders the PDF with Ghostscript, lowering image resolution step by step from 220 to 50 dpi |
| DOCX, PPTX, XLSX, ODT, ODP, ODS | Recompresses the pictures inside the file, leaving text and layout untouched |
| Video | Works out the bitrate that fits from the video's length, encodes in two passes to hit it, and lowers the resolution when the bitrate gets low |
| MP3, AAC, M4A, OGG, OPUS | Re-encodes at the bitrate that fits, switching to mono for very small limits |
| WAV, FLAC | These are uncompressed, so the app suggests converting to MP3 or OPUS instead |
| CSV, TXT, JSON and other text files | These can't shrink without losing data, so they're packed into a zip |
| Zip of several results (PDF pages, split parts, sheets) | The limit applies to each file inside, using the method for that file's type |

## Getting started

Works on **Linux, macOS and Windows**.

### Requirements

- Python 3.11 or newer
- Node.js 18 or newer, with npm
- LibreOffice, for documents, slides and spreadsheet-to-PDF
- Ghostscript, for PDF compression
- FFmpeg, for audio and video

| Platform | Install LibreOffice, Ghostscript and FFmpeg |
|---|---|
| Ubuntu / Debian | `sudo apt install libreoffice ghostscript ffmpeg` |
| macOS (Homebrew) | `brew install --cask libreoffice` and `brew install ghostscript ffmpeg` |
| Windows (PowerShell) | `winget install TheDocumentFoundation.LibreOffice`, `winget install ArtifexSoftware.GhostScript` and `winget install Gyan.FFmpeg` |

The app finds these programs on its own, either on `PATH` or in their default install folders
(`C:\Program Files\LibreOffice`, `C:\Program Files\gs`, `C:\ffmpeg`, `/Applications/LibreOffice.app`,
Homebrew's folders). If you installed them somewhere else, set `SOFFICE_BIN`, `GS_BIN` and
`FFMPEG_BIN`. The app still starts without them; only the conversions that need them fail.

### Install and run on Linux / macOS

```bash
git clone https://github.com/Ananthakrishnan-Jayadev/file-convertor.git
cd file-convertor

python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[test]"   # also creates the `fileconvert` command
(cd frontend && npm install)

backend/.venv/bin/fileconvert serve
```

### Install and run on Windows (PowerShell)

```powershell
git clone https://github.com/Ananthakrishnan-Jayadev/file-convertor.git
cd file-convertor

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

### Using the app

The page has three tabs:

1. **Convert files**: drop one or more files. Each gets its own "to" menu, filled in with a
   sensible default; "Convert all to" changes them together. Pick a size limit if you need one,
   open **Image options** to resize, rotate or set quality, press **Convert**, then download each
   file or **Download all as .zip**. For images, **Compare with original** shows both side by side.
2. **Combine into PDF**: drop images and PDFs, drag them into order (or use the arrows), name the
   file, and press **Combine**.
3. **Split PDF**: drop one PDF and choose **One PDF per page**, or **Pages I choose** and click
   page thumbnails (Shift+click selects a run). Then choose one PDF or one per group.

Under each result, a bar compares the original size, the new size and the size limit. If the limit
couldn't be reached, the result says how close it got. Changing the size limit or image options
after converting marks those files to be converted again.

### Run with Docker

The image includes LibreOffice, Ghostscript and FFmpeg, so nothing else needs installing:

```bash
docker compose up --build      # http://localhost:8000
```

## Tests

```bash
cd backend
.venv/bin/pytest                    # full suite   (Windows: .venv\Scripts\pytest)
.venv/bin/pytest -m "not slow"      # skip the LibreOffice, PDF-to-DOCX and audio/video tests
```

Tests that need LibreOffice, Ghostscript or FFmpeg are skipped automatically when those aren't
installed. The audio and video tests create their own sample files with FFmpeg.

## How it works

```
Browser (React)                     FastAPI                               Worker threads
───────────────                     ───────                               ──────────────
POST /api/jobs  (file, format,  ──▶ checks extension and contents,  ──▶ convert ─▶ shrink to limit
                 size limit)        saves the upload, returns a job id
POST /api/pdf/combine | split   ──▶ same, for the PDF tools           ──▶ combine / split ─▶ shrink
GET  /api/jobs/{id}  (every 1s) ──▶ queued / running / done / error / cancelled
GET  /api/jobs/{id}/download    ──▶ the converted file
DELETE /api/jobs/{id}           ──▶ cancel, or delete the files now
```

- **Registry** (`registry.py`): every converter declares which input and output formats it
  handles. The UI's format menus come from the same list, so the backend and UI never disagree.
- **Converters** (`converters/`): images use Pillow and pillow-heif; documents and slides use
  headless LibreOffice; spreadsheets use pandas; PDFs use PyMuPDF and pdf2docx; data formats use
  PyYAML and xmltodict; audio and video use FFmpeg.
- **Content check** (`sniff.py`): reads the first bytes of each upload and rejects files whose
  contents clearly contradict the extension, such as a JPEG named `.pdf`.
- **PDF tools** (`pdftools.py`): combining and splitting with PyMuPDF. Page ranges are checked
  when you upload, so a typo is reported straight away.
- **Size controller** (`compress.py`): the strategies in the table above.
- **Jobs** (`jobs.py`): conversions run on a thread pool. Job records are saved in SQLite inside
  `FC_DATA_DIR`, so finished jobs survive a restart; jobs that were still running are marked as
  failed with a message asking to try again. Cancelling kills any LibreOffice, Ghostscript or
  FFmpeg process the job started. Finished files are deleted after `FC_JOB_TTL` seconds.
- **Previews** (frontend): image thumbnails come straight from the files in the browser; PDF
  pages are drawn in the browser with pdf.js, so nothing is uploaded just to preview it.

### API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/formats` | Every supported input format and what it can become |
| `POST` | `/api/jobs` | Start a conversion. Form fields: `file`, `target_format`, optional `max_size_kb`; for images also `width`, `height`, `scale` (1-100), `rotate` (0/90/180/270), `quality` (1-100), `keep_metadata` |
| `POST` | `/api/pdf/combine` | Combine images and PDFs. Form fields: `files` (repeat, in page order), optional `output_name`, `max_size_kb` |
| `POST` | `/api/pdf/split` | Split a PDF. Form fields: `file`, optional `ranges` (empty means every page), `together` (one PDF of all ranges), `max_size_kb` |
| `GET` | `/api/jobs/{id}` | Job status, sizes, and a note when the size limit wasn't met |
| `GET` | `/api/jobs/{id}/download` | Download the result |
| `DELETE` | `/api/jobs/{id}` | Cancel a job that's waiting or running, or delete a finished job's files |
| `POST` | `/api/archive` | `{"ids": [...]}` returns the finished files as one zip |

Interactive API docs are at http://localhost:8000/docs while the server is running.

## Project layout

```
backend/
  app/
    main.py          API endpoints; also serves the built UI
    cli.py           the `fileconvert serve` command
    tools.py         finds LibreOffice, Ghostscript and FFmpeg; runs them so jobs can be cancelled
    jobs.py          job queue, SQLite job records, cancelling, cleanup
    sniff.py         checks that a file's contents match its extension
    registry.py      which converter handles which conversion
    compress.py      the size controller
    pdftools.py      combine images/PDFs into one PDF, split a PDF
    converters/      images, pdf, sheets, documents (LibreOffice), data, media (FFmpeg)
  tests/             pytest suite
  pyproject.toml     dependencies and the `fileconvert` command
frontend/
  src/               React UI: Convert, Combine into PDF and Split PDF tools, image options,
                     thumbnails and page picker (pdf.js), size limit picker, size meter
Dockerfile           single image: builds the UI, installs LibreOffice, Ghostscript and FFmpeg
docker-compose.yml
```

## Configuration

Set these as environment variables before running `fileconvert serve` or in `docker-compose.yml`.

| Variable | Default | Meaning |
|---|---|---|
| `FC_MAX_UPLOAD_MB` | `200` | Largest upload per request; for Combine, the total of all files. Raise it for long videos |
| `FC_JOB_TTL` | `3600` | Seconds before uploaded and converted files are deleted |
| `FC_WORKERS` | half the CPU cores | How many conversions run at the same time |
| `FC_DATA_DIR` | system temp folder | Where uploads, results and the job database are stored |
| `SOFFICE_BIN`, `GS_BIN`, `FFMPEG_BIN`, `FFPROBE_BIN` | found automatically | Custom paths to LibreOffice, Ghostscript and FFmpeg |

## Known limitations

- **PDF to DOCX** is close but not perfect for complex layouts such as multiple columns,
  floating images or forms.
- **LibreOffice output** can differ slightly from Microsoft Office in fonts and spacing.
- **Animated GIFs** keep only their first frame when converted to another image format.
  Shrinking a GIF to a size limit keeps it animated.
- **Video to GIF** uses the first 30 seconds at 12 frames per second and at most 640 pixels wide,
  since GIFs grow very large.
- **Running jobs can't resume after a restart**: they're marked as failed and need starting again.
- **Very large PDFs** show page thumbnails gradually, starting from the first page.

## Roadmap

- OCR for scanned PDFs (OCRmyPDF) and ebook formats (Calibre)
- Upload progress bars for large files
- Celery or RQ with Redis instead of the in-process queue, for running several servers

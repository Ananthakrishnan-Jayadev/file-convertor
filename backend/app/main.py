import os
import re
import uuid
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

from . import converters, pdftools  # noqa: F401  (importing converters registers them)
from .jobs import DATA_DIR, Job, JobStore
from .registry import format_map, normalize

MAX_UPLOAD = int(os.environ.get("FC_MAX_UPLOAD_MB", 200)) * 1024 * 1024
MIN_TARGET_KB = 10
CHUNK = 1024 * 1024
FRONTEND_DIST = Path(os.environ.get("FC_FRONTEND_DIST") or Path(__file__).resolve().parents[2] / "frontend" / "dist")

FORMATS = format_map()

app = FastAPI(title="File Converter")
store = JobStore()


def safe_stem(filename: str) -> str:
    stem = re.sub(r"[^\w.\- ]+", "_", Path(filename).stem).strip(" .")
    return stem[:100] or "file"


@app.get("/api/formats")
def get_formats() -> dict:
    return {"formats": FORMATS, "max_upload_bytes": MAX_UPLOAD}


def check_limit(max_size_kb: int | None) -> int | None:
    if max_size_kb is not None and max_size_kb < MIN_TARGET_KB:
        raise HTTPException(400, f"The size limit must be at least {MIN_TARGET_KB} KB.")
    return max_size_kb * 1024 if max_size_kb else None


async def save_upload(job: Job, file: UploadFile, dest: Path, budget: int) -> int:
    """Stream an upload to `dest`; `budget` is how many bytes this request may still use.
    On failure the job is discarded and an HTTP error raised."""
    size = 0
    with dest.open("wb") as fh:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > budget:
                break
            fh.write(chunk)
    if size > budget:
        store.discard(job)
        raise HTTPException(413, f"Uploads can be at most {MAX_UPLOAD // 1024 // 1024} MB in total.")
    if size == 0:
        store.discard(job)
        raise HTTPException(400, f"{file.filename or 'The file'} is empty.")
    return size


@app.post("/api/jobs", status_code=201)
async def create_job(
    file: UploadFile = File(...),
    target_format: str = Form(...),
    max_size_kb: int | None = Form(None),
) -> dict:
    filename = file.filename or ""
    src_ext = normalize(Path(filename).suffix)
    if src_ext not in FORMATS:
        raise HTTPException(415, f"Files of type .{src_ext or '?'} can't be converted yet.")
    target = normalize(target_format)
    if target not in FORMATS[src_ext]["outputs"]:
        raise HTTPException(400, f"A .{src_ext} file can't be converted to .{target}.")

    job = store.create(filename, target, check_limit(max_size_kb))
    src = job.dir / "in" / f"{safe_stem(filename)}.{src_ext}"
    await save_upload(job, file, src, MAX_UPLOAD)
    store.submit(job, src)
    return job.public()


@app.post("/api/pdf/combine", status_code=201)
async def combine_pdf(
    files: list[UploadFile] = File(...),
    output_name: str = Form("combined"),
    max_size_kb: int | None = Form(None),
) -> dict:
    """Images and PDFs, in the order sent, become one PDF."""
    exts = [normalize(Path(f.filename or "").suffix) for f in files]
    if bad := sorted({e or "?" for e in exts if e not in pdftools.COMBINE_INPUTS}):
        raise HTTPException(415, f"Only images and PDFs can be combined, not .{', .'.join(bad)}.")

    name = f"{safe_stem(output_name)}.pdf"
    job = store.create(name, "pdf", check_limit(max_size_kb), operation="combine")
    sources, used = [], 0
    for i, (file, ext) in enumerate(zip(files, exts)):
        # Number the files so their order survives and same-named uploads don't collide.
        src = job.dir / "in" / f"{i:03d}-{safe_stem(file.filename or 'file')}.{ext}"
        used += await save_upload(job, file, src, MAX_UPLOAD - used)
        sources.append(src)

    store.submit_work(job, lambda out_dir: pdftools.combine(sources, out_dir / name), sources)
    return job.public()


@app.post("/api/pdf/split", status_code=201)
async def split_pdf(
    file: UploadFile = File(...),
    ranges: str = Form("", description="e.g. '1-3, 5, 8-'; leave empty for one PDF per page"),
    max_size_kb: int | None = Form(None),
) -> dict:
    """One PDF per page, or one PDF per range. The size limit applies to each part."""
    filename = file.filename or ""
    if normalize(Path(filename).suffix) != "pdf":
        raise HTTPException(415, "Only PDF files can be split.")

    job = store.create(filename, "pdf", check_limit(max_size_kb), operation="split")
    src = job.dir / "in" / f"{safe_stem(filename)}.pdf"
    await save_upload(job, file, src, MAX_UPLOAD)
    # Check the ranges now, so a typo is reported straight away instead of as a failed job.
    try:
        pages = pdftools.page_count(src)
        if pages == 0:
            raise ValueError("This PDF has no pages.")
        parsed = pdftools.parse_ranges(ranges, pages) if ranges.strip() else None
    except ValueError as exc:
        store.discard(job)
        raise HTTPException(400, str(exc)) from None
    except Exception:
        store.discard(job)
        raise HTTPException(400, "This file couldn't be opened as a PDF.") from None

    store.submit_work(job, lambda out_dir: pdftools.split(src, out_dir, parsed), [src])
    return job.public()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    return _job_or_404(job_id).public()


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str) -> FileResponse:
    job = _job_or_404(job_id)
    if job.status != "done" or job.output_path is None:
        raise HTTPException(409, "This file isn't ready yet.")
    return FileResponse(job.output_path, filename=job.output_path.name)


class ArchiveRequest(BaseModel):
    ids: list[str]


@app.post("/api/archive")
def archive(req: ArchiveRequest) -> FileResponse:
    jobs = [store.get(i) for i in req.ids]
    ready = [j for j in jobs if j and j.status == "done" and j.output_path]
    if not ready:
        raise HTTPException(404, "None of these files are ready to download.")

    (DATA_DIR / "archives").mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "archives" / f"{uuid.uuid4().hex}.zip"
    used: set[str] = set()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for job in ready:
            name, n = job.output_path.name, 1
            while name in used:  # two inputs can produce the same output name
                n += 1
                name = f"{job.output_path.stem} ({n}){job.output_path.suffix}"
            used.add(name)
            zf.write(job.output_path, name)
    return FileResponse(path, filename="converted-files.zip",
                        background=BackgroundTask(path.unlink, missing_ok=True))


def _job_or_404(job_id: str):
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "This file has expired or doesn't exist. Upload it again.")
    return job


# Serve the built frontend from the same server in production (after `npm run build`).
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

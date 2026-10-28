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

from . import converters  # noqa: F401  (registers all converters)
from .jobs import DATA_DIR, JobStore
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
    if max_size_kb is not None and max_size_kb < MIN_TARGET_KB:
        raise HTTPException(400, f"The size limit must be at least {MIN_TARGET_KB} KB.")

    job = store.create(filename, target, max_size_kb * 1024 if max_size_kb else None)
    src = job.dir / "in" / f"{safe_stem(filename)}.{src_ext}"
    size = 0
    with src.open("wb") as fh:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > MAX_UPLOAD:
                fh.close()
                store.discard(job)
                raise HTTPException(413, f"Files can be at most {MAX_UPLOAD // 1024 // 1024} MB.")
            fh.write(chunk)
    if size == 0:
        store.discard(job)
        raise HTTPException(400, "The file is empty.")

    store.submit(job, src)
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

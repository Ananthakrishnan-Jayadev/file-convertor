import io
import time
import zipfile

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def wait_for(job_id: str, timeout: float = 60) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.2)
    pytest.fail(f"job {job_id} did not finish in {timeout}s")


def upload(path, target, max_size_kb=None):
    data = {"target_format": target}
    if max_size_kb is not None:
        data["max_size_kb"] = str(max_size_kb)
    with path.open("rb") as fh:
        return client.post("/api/jobs", files={"file": (path.name, fh)}, data=data)


def test_formats_endpoint():
    body = client.get("/api/formats").json()
    assert "jpg" in body["formats"]["png"]["outputs"]
    assert body["max_upload_bytes"] > 0


def test_convert_and_download(png_alpha):
    res = upload(png_alpha, "jpg")
    assert res.status_code == 201
    job = wait_for(res.json()["id"])
    assert job["status"] == "done", job
    assert job["output_name"] == "logo.jpg"

    dl = client.get(f"/api/jobs/{job['id']}/download")
    assert dl.status_code == 200
    assert 'filename="logo.jpg"' in dl.headers["content-disposition"]
    Image.open(io.BytesIO(dl.content)).verify()


def test_convert_with_size_limit(big_jpg):
    job = wait_for(upload(big_jpg, "webp", max_size_kb=100).json()["id"])
    assert job["status"] == "done", job
    assert job["target_met"] is True
    assert job["output_size"] <= 100 * 1024 < job["input_size"]


def test_keep_format_just_shrinks(big_jpg):
    job = wait_for(upload(big_jpg, "jpg", max_size_kb=50).json()["id"])
    assert job["output_name"] == "photo.jpg"
    assert job["output_size"] <= 50 * 1024


def test_unsupported_input_type(tmp_path):
    src = tmp_path / "program.exe"
    src.write_bytes(b"MZ")
    res = upload(src, "pdf")
    assert res.status_code == 415
    assert ".exe" in res.json()["detail"]


def test_unsupported_target(csv_file):
    res = upload(csv_file, "mp3")
    assert res.status_code == 400


def test_size_limit_too_small(csv_file):
    assert upload(csv_file, "xlsx", max_size_kb=1).status_code == 400


def test_empty_file(tmp_path):
    src = tmp_path / "empty.csv"
    src.write_bytes(b"")
    assert upload(src, "xlsx").status_code == 400


def test_bad_file_reports_error(tmp_path):
    src = tmp_path / "broken.png"
    src.write_text("not an image")
    job = wait_for(upload(src, "jpg").json()["id"])
    assert job["status"] == "error" and job["error"]
    assert client.get(f"/api/jobs/{job['id']}/download").status_code == 409


def test_unsafe_filename_is_sanitised(tmp_path, csv_file):
    weird = tmp_path / "a..b;rm -rf$.csv"
    weird.write_bytes(csv_file.read_bytes())
    job = wait_for(upload(weird, "json").json()["id"])
    assert job["status"] == "done"
    assert "/" not in job["output_name"] and ";" not in job["output_name"]


def test_unknown_job_is_404():
    assert client.get("/api/jobs/doesnotexist").status_code == 404


def test_archive_dedupes_names(csv_file, tmp_path):
    other = tmp_path / "copy"
    other.mkdir()
    twin = other / csv_file.name  # same name -> same output name
    twin.write_bytes(csv_file.read_bytes())
    ids = [wait_for(upload(p, "json").json()["id"])["id"] for p in (csv_file, twin)]

    res = client.post("/api/archive", json={"ids": ids + ["missing"]})
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert sorted(zf.namelist()) == ["people (2).json", "people.json"]


def test_archive_with_nothing_ready():
    assert client.post("/api/archive", json={"ids": ["nope"]}).status_code == 404


def make_pdf(path, pages):
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Page {i + 1}")
    doc.save(path)
    doc.close()
    return path


def test_combine_images_and_pdf(tmp_path, png_alpha, big_jpg):
    pdf = make_pdf(tmp_path / "intro.pdf", 2)
    files = [("files", (p.name, p.read_bytes())) for p in (pdf, big_jpg, png_alpha)]
    res = client.post("/api/pdf/combine", files=files, data={"output_name": "My album"})
    assert res.status_code == 201
    job = wait_for(res.json()["id"])
    assert job["status"] == "done", job
    assert job["operation"] == "combine"
    assert job["output_name"] == "My album.pdf"

    dl = client.get(f"/api/jobs/{job['id']}/download")
    with pymupdf.open(stream=dl.content, filetype="pdf") as doc:
        assert doc.page_count == 4


def test_combine_rejects_other_types(tmp_path, png_alpha, csv_file):
    files = [("files", (p.name, p.read_bytes())) for p in (png_alpha, csv_file)]
    res = client.post("/api/pdf/combine", files=files)
    assert res.status_code == 415
    assert ".csv" in res.json()["detail"]


def test_split_by_ranges(tmp_path):
    src = make_pdf(tmp_path / "report.pdf", 5)
    with src.open("rb") as fh:
        res = client.post("/api/pdf/split", files={"file": (src.name, fh)}, data={"ranges": "1-2, 5"})
    assert res.status_code == 201
    job = wait_for(res.json()["id"])
    assert job["status"] == "done", job
    dl = client.get(f"/api/jobs/{job['id']}/download")
    with zipfile.ZipFile(io.BytesIO(dl.content)) as zf:
        assert zf.namelist() == ["report-pages1-2.pdf", "report-page5.pdf"]


def test_split_every_page_by_default(tmp_path):
    src = make_pdf(tmp_path / "report.pdf", 3)
    with src.open("rb") as fh:
        job = wait_for(client.post("/api/pdf/split", files={"file": (src.name, fh)}).json()["id"])
    assert job["output_name"] == "report-split.zip"


def test_split_bad_range_is_rejected_immediately(tmp_path):
    src = make_pdf(tmp_path / "report.pdf", 3)
    with src.open("rb") as fh:
        res = client.post("/api/pdf/split", files={"file": (src.name, fh)}, data={"ranges": "2-9"})
    assert res.status_code == 400
    assert "3 pages" in res.json()["detail"]


def test_split_needs_a_pdf(csv_file):
    with csv_file.open("rb") as fh:
        res = client.post("/api/pdf/split", files={"file": (csv_file.name, fh)})
    assert res.status_code == 415


def test_split_broken_pdf(tmp_path):
    src = tmp_path / "broken.pdf"
    src.write_bytes(b"%PDF-1.4 nonsense")
    with src.open("rb") as fh:
        res = client.post("/api/pdf/split", files={"file": (src.name, fh)}, data={"ranges": "1"})
    assert res.status_code == 400

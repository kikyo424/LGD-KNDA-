"""Small public report API; run one worker so temporary job state stays local."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Lock
import time
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from scripts.update_api import router as update_router

ROOT = Path(__file__).resolve().parents[1]
TTL = 3600
MAX_JOBS = 30
MAX_ACTIVE = 4
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv(
    "REPORT_ALLOWED_ORIGINS", "https://kikyo424.github.io,http://localhost:4321,http://127.0.0.1:4321"
).split(",") if origin.strip()]


class ReportInput(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    date_from: date | None = None
    date_to: date | None = None
    source: Literal["all", "news", "papers"] = "all"

    @model_validator(mode="after")
    def validate_range(self):
        self.keyword = self.keyword.strip()
        if not self.keyword:
            raise ValueError("검색 키워드를 입력해 주세요.")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("시작일이 종료일보다 늦을 수 없습니다.")
        return self


@dataclass
class Job:
    directory: Path
    created: float
    state: str = "queued"
    message: str = "수집 대기 중입니다."
    downloadable: bool = False


jobs: dict[str, Job] = {}
requests_by_ip: dict[str, list[float]] = {}
lock = Lock()
executor = ThreadPoolExecutor(max_workers=2)
app = FastAPI(title="OLED report service", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])
app.include_router(update_router)


def cleanup(now: float) -> None:
    for key, job in list(jobs.items()):
        if now - job.created > TTL and job.state not in ("queued", "running"):
            shutil.rmtree(job.directory, ignore_errors=True)
            del jobs[key]
    for ip, stamps in list(requests_by_ip.items()):
        recent = [stamp for stamp in stamps if now - stamp < 600]
        if recent:
            requests_by_ip[ip] = recent
        else:
            del requests_by_ip[ip]


def collect_report(job: Job, payload: ReportInput) -> None:
    job.state, job.message = "running", "뉴스·논문을 수집하고 있습니다. 잠시 기다려 주세요."
    command = [sys.executable, str(ROOT / "scripts/collect.py"), "--keyword", payload.keyword,
               "--source", payload.source, "--report-output", str(job.directory / "report.html")]
    for flag, value in (("--date-from", payload.date_from), ("--date-to", payload.date_to)):
        if value:
            command.extend([flag, value.isoformat()])
    try:
        result = subprocess.run(command, cwd=ROOT, timeout=480,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        job.downloadable = (job.directory / "report.html").is_file()
        if result.returncode == 0 and job.downloadable:
            job.state, job.message = "completed", "보고서가 완성되었습니다. 일부 경로의 오류가 있으면 보고서에 표시됩니다."
        elif job.downloadable:
            job.state, job.message = "failed", "자료를 수집하지 못했습니다. 오류 내역 보고서를 다운로드해 확인할 수 있습니다."
        else:
            job.state, job.message = "failed", "보고서를 만들지 못했습니다. 잠시 후 다시 시도해 주세요."
    except (subprocess.TimeoutExpired, OSError):
        job.state, job.message = "failed", "수집 시간이 초과되었거나 서비스 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=202)
def create_report(payload: ReportInput, request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        raise HTTPException(403, "허용되지 않은 사이트입니다.")
    now = time.monotonic()
    ip = request.client.host if request.client else "unknown"
    with lock:
        cleanup(now)
        recent = requests_by_ip.get(ip, [])
        if len(recent) >= 3:
            raise HTTPException(429, "10분 동안 최대 3번 수집할 수 있습니다. 잠시 후 다시 시도해 주세요.")
        active = sum(job.state in ("queued", "running") for job in jobs.values())
        if active >= MAX_ACTIVE or len(jobs) >= MAX_JOBS:
            raise HTTPException(503, "현재 수집 요청이 많습니다. 잠시 후 다시 시도해 주세요.")
        key = str(uuid4())
        job = Job(Path(tempfile.mkdtemp(prefix="oled-report-")), now)
        jobs[key] = job
        requests_by_ip[ip] = [*recent, now]
        executor.submit(collect_report, job, payload)
    return {"id": key, "expires_in": TTL}


def get_job(key: UUID) -> Job:
    with lock:
        cleanup(time.monotonic())
        job = jobs.get(str(key))
    if not job:
        raise HTTPException(404, "보고서가 만료되었거나 서버가 재시작되었습니다. 다시 수집해 주세요.")
    return job


@app.get("/reports/{key}")
def report_status(key: UUID):
    job = get_job(key)
    return {"state": job.state, "message": job.message, "downloadable": job.downloadable}


@app.get("/reports/{key}/download")
def download_report(key: UUID):
    job = get_job(key)
    path = job.directory / "report.html"
    if not job.downloadable or not path.is_file():
        raise HTTPException(409, "아직 다운로드할 보고서가 없습니다.")
    return FileResponse(path, filename="oled-custom-report.html", media_type="text/html",
                        headers={"Cache-Control": "no-store"})

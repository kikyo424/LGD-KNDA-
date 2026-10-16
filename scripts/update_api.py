"""Authenticated GitHub dispatch bridge; secrets never leave the Render service."""
import hmac
import os
from threading import Lock
import time
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
dispatch_lock = Lock()
last_dispatch = float("-inf")
failed_auth: dict[str, list[float]] = {}
REPOSITORY = "kikyo424/LGD-KNDA-"
WORKFLOW = "pages.yml"
TITLE_PREFIX = "Navigator MAP update "


def authorize(request: Request) -> None:
    allowed = os.getenv("REPORT_ALLOWED_ORIGINS", "https://kikyo424.github.io,http://localhost:4321,http://127.0.0.1:4321").split(",")
    origin = request.headers.get("origin")
    if origin and origin not in [value.strip() for value in allowed]:
        raise HTTPException(403, "허용되지 않은 사이트입니다.")
    secret = os.getenv("UPDATE_ADMIN_KEY", "")
    if not secret or not os.getenv("UPDATE_GITHUB_TOKEN"):
        raise HTTPException(503, "업데이트 서버의 관리자 인증 설정이 필요합니다.")
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with dispatch_lock:
        for address, stamps in list(failed_auth.items()):
            recent = [stamp for stamp in stamps if now - stamp < 600]
            if recent:
                failed_auth[address] = recent
            else:
                del failed_auth[address]
        if len(failed_auth.get(ip, [])) >= 5:
            raise HTTPException(429, "인증 시도가 많습니다. 10분 후 다시 시도해 주세요.")
        if not hmac.compare_digest(request.headers.get("authorization", "").encode(), f"Bearer {secret}".encode()):
            failed_auth.setdefault(ip, []).append(now)
            raise HTTPException(401, "관리자 키를 확인해 주세요.")


def github(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        response = httpx.request(method, f"https://api.github.com/repos/{REPOSITORY}/{path}",
            headers={"Authorization": f"Bearer {os.environ['UPDATE_GITHUB_TOKEN']}",
                     "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            timeout=25, **kwargs)
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, "GitHub 요청이 거부됐습니다. 서버의 토큰 권한·만료와 워크플로 설정을 확인해 주세요.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(504, "GitHub 응답을 확인하지 못했습니다. Actions에서 실행 여부를 확인한 뒤 다시 시도해 주세요.") from exc


def recent_runs() -> list[dict]:
    return github("GET", f"actions/workflows/{WORKFLOW}/runs", params={"branch": "main", "per_page": 100}).json()["workflow_runs"]


@router.post("/updates", status_code=202)
def request_update(request: Request):
    global last_dispatch
    authorize(request)
    with dispatch_lock:
        if time.monotonic() - last_dispatch < 120:
            raise HTTPException(409, "업데이트 요청이 이미 접수됐습니다. 잠시 후 실행 기록을 확인해 주세요.")
        if any(run["status"] != "completed" for run in recent_runs()):
            raise HTTPException(409, "이미 수집·배포가 진행 중입니다. 완료 후 다시 시도해 주세요.")
        key = str(uuid4())
        last_dispatch = time.monotonic()
        github("POST", f"actions/workflows/{WORKFLOW}/dispatches",
               json={"ref": "main", "inputs": {"update_request": key}})
    return {"id": key, "state": "requested", "message": "업데이트 실행을 요청했습니다. 시작을 기다리고 있습니다."}


@router.get("/updates/{key}")
def update_status(key: UUID, request: Request):
    authorize(request)
    run = next((run for run in recent_runs() if run.get("display_title") == TITLE_PREFIX + str(key)), None)
    if not run:
        return {"state": "requested", "message": "실행 기록을 기다리고 있습니다."}
    if run["status"] != "completed":
        return {"state": "running", "message": "수집·배포 대기 또는 진행 중입니다.", "url": run["html_url"]}
    success = run.get("conclusion") == "success"
    return {"state": "completed" if success else "failed", "url": run["html_url"],
            "message": "사이트 업데이트가 완료되었습니다. 새로고침해 신규 자료를 확인하세요." if success else "업데이트가 완료되지 않았습니다. 실행 기록을 확인해 주세요."}

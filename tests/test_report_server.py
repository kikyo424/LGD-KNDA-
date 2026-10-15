import subprocess
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from scripts import collect, report_server as server


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "jobs", {})
    monkeypatch.setattr(server, "requests_by_ip", {})
    def directory(prefix):
        path = tmp_path / str(uuid4())
        path.mkdir()
        return str(path)
    monkeypatch.setattr(server.tempfile, "mkdtemp", directory)
    monkeypatch.setattr(server, "executor", SimpleNamespace(submit=lambda fn, *args: fn(*args)))
    with TestClient(server.app) as client:
        yield client


def test_public_report_api_collects_and_downloads_html_without_dashboard_changes(client, monkeypatch):
    monkeypatch.setattr(collect, "fetch_domestic_news", lambda *args: [])
    monkeypatch.setattr(collect, "fetch_international_news", lambda *args: [{
        "id": "sample", "title": "Smartwatch OLED LTPO", "published_at": "2026-01-01",
        "source_type": "news", "region": "international", "source": "Test publisher",
        "url": "https://example.com/news",
    }])
    monkeypatch.setattr(collect, "load_existing", lambda: pytest.fail("Dashboard data must not be read"))
    def run(command, **kwargs):
        assert "--report-output" in command
        return subprocess.CompletedProcess(command, collect.main(command[2:]))
    monkeypatch.setattr(server.subprocess, "run", run)
    response = client.post("/reports", json={"keyword": "OLED", "source": "news"},
                           headers={"Origin": server.ALLOWED_ORIGINS[0]})
    assert response.status_code == 202
    assert response.headers["access-control-allow-origin"] == server.ALLOWED_ORIGINS[0]
    key = response.json()["id"]
    status = client.get(f"/reports/{key}").json()
    assert status["state"] == "completed"
    download = client.get(f"/reports/{key}/download")
    assert download.status_code == 200
    assert "Test publisher" in download.text
    assert "attachment" in download.headers["content-disposition"]
    assert download.headers["cache-control"] == "no-store"


def test_api_rejects_invalid_inputs_and_unknown_origins(client):
    for payload in [{"keyword": " "}, {"keyword": "OLED", "source": "bad"},
                    {"keyword": "OLED", "date_from": "2026-02-01", "date_to": "2026-01-01"}]:
        assert client.post("/reports", json=payload).status_code == 422
    assert client.post("/reports", json={"keyword": "OLED"}, headers={"Origin": "https://unknown.example"}).status_code == 403
    assert client.get(f"/reports/{uuid4()}").status_code == 404


def test_api_limits_busy_queue_and_request_frequency(client, monkeypatch):
    monkeypatch.setattr(server, "MAX_ACTIVE", 0)
    assert client.post("/reports", json={"keyword": "OLED"}).status_code == 503
    monkeypatch.setattr(server, "MAX_ACTIVE", 4)
    monkeypatch.setattr(server, "collect_report", lambda job, payload: setattr(job, "state", "completed"))
    for _ in range(3):
        assert client.post("/reports", json={"keyword": "OLED"}).status_code == 202
    assert client.post("/reports", json={"keyword": "OLED"}).status_code == 429


def test_expired_jobs_are_removed_and_pending_download_is_blocked(client, monkeypatch):
    monkeypatch.setattr(server, "executor", SimpleNamespace(submit=lambda *args: None))
    key = client.post("/reports", json={"keyword": "OLED"}).json()["id"]
    assert client.get(f"/reports/{key}/download").status_code == 409
    job = server.jobs[key]
    directory = job.directory
    job.state = "completed"
    job.created -= server.TTL + 1
    assert client.get(f"/reports/{key}").status_code == 404
    assert not directory.exists()

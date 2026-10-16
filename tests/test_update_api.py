import json
import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from scripts import update_api as updates
from scripts.report_server import app

BASE = "https://api.github.com/repos/kikyo424/LGD-KNDA-/actions/workflows/pages.yml"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("UPDATE_ADMIN_KEY", "test-admin-key")
    monkeypatch.setenv("UPDATE_GITHUB_TOKEN", "test-github-token")
    monkeypatch.setattr(updates, "last_dispatch", float("-inf"))
    monkeypatch.setattr(updates, "failed_auth", {})
    return TestClient(app, headers={"Authorization": "Bearer test-admin-key"})


def test_update_requires_configuration_auth_and_allowed_origin(client, monkeypatch):
    assert client.post("/updates", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/updates", headers={"Origin": "https://unknown.example"}).status_code == 403
    preflight = client.options("/updates", headers={"Origin": "https://kikyo424.github.io", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization"})
    assert preflight.status_code == 200
    monkeypatch.delenv("UPDATE_GITHUB_TOKEN")
    assert client.post("/updates").status_code == 503


@respx.mock
def test_dispatch_tracks_only_matching_run_through_deployment(client):
    listing = respx.get(BASE + "/runs").mock(return_value=httpx.Response(200, json={"workflow_runs": []}))
    dispatch = respx.post(BASE + "/dispatches").mock(return_value=httpx.Response(204))
    response = client.post("/updates")
    assert response.status_code == 202
    key = response.json()["id"]
    assert json.loads(dispatch.calls[0].request.content) == {"ref": "main", "inputs": {"update_request": key}}
    assert client.get(f"/updates/{key}").json()["state"] == "requested"
    listing.mock(return_value=httpx.Response(200, json={"workflow_runs": [{"display_title": "Unrelated successful deployment", "status": "completed", "conclusion": "success"}]}))
    assert client.get(f"/updates/{key}").json()["state"] == "requested"
    assert client.post("/updates").status_code == 409
    run = {"display_title": updates.TITLE_PREFIX + key, "status": "in_progress", "html_url": "https://github.com/kikyo424/LGD-KNDA-/actions/runs/1"}
    listing.mock(return_value=httpx.Response(200, json={"workflow_runs": [run]}))
    assert client.get(f"/updates/{key}").json()["state"] == "running"
    for conclusion, state in [("failure", "failed"), ("cancelled", "failed"), ("success", "completed")]:
        listing.mock(return_value=httpx.Response(200, json={"workflow_runs": [{**run, "status": "completed", "conclusion": conclusion}]}))
        assert client.get(f"/updates/{key}").json()["state"] == state


@respx.mock
def test_active_run_blocks_dispatch_and_upstream_errors_hide_secrets(client):
    listing = respx.get(BASE + "/runs").mock(return_value=httpx.Response(200, json={"workflow_runs": [{"status": "queued"}]}))
    dispatch = respx.post(BASE + "/dispatches")
    assert client.post("/updates").status_code == 409
    assert not dispatch.called
    listing.mock(return_value=httpx.Response(403, text="test-github-token"))
    response = client.post("/updates")
    assert response.status_code == 502
    assert "test-github-token" not in response.text


def test_bad_admin_key_attempts_are_limited(client):
    for _ in range(5):
        assert client.post("/updates", headers={"Authorization": "Bearer bad"}).status_code == 401
    assert client.post("/updates").status_code == 429


@respx.mock
def test_dispatch_timeout_does_not_claim_success_or_repeat_request(client):
    respx.get(BASE + "/runs").mock(return_value=httpx.Response(200, json={"workflow_runs": []}))
    dispatch = respx.post(BASE + "/dispatches").mock(side_effect=httpx.ReadTimeout("timeout"))
    assert client.post("/updates").status_code == 504
    assert client.post("/updates").status_code == 409
    assert dispatch.call_count == 1

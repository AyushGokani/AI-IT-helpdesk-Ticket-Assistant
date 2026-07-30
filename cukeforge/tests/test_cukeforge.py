from pathlib import Path

import pytest

from app import create_app
from app.ai import generate_feature, generate_steps, heuristic_feature, heuristic_steps
from app.cucumber import prepare_workspace, run_behave, write_feature, write_steps
from app.jira_client import load_demo_tickets
from app.pipeline import execute_pipeline

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "samples" / "demo_tickets.json"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("JIRA_EMAIL", "")
    monkeypatch.setenv("JIRA_API_TOKEN", "")
    monkeypatch.setenv("CUKE_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["service"] == "cukeforge"
    assert data["jira_mode"] == "demo"
    assert data["ai_mode"] == "heuristic"


def test_list_demo_tickets(client):
    res = client.get("/api/tickets")
    assert res.status_code == 200
    data = res.get_json()
    assert data["mode"] == "demo"
    assert len(data["tickets"]) >= 3
    assert {t["key"] for t in data["tickets"]} >= {"DEMO-101", "DEMO-102", "DEMO-103"}


def test_ticket_detail(client):
    res = client.get("/api/tickets/DEMO-102")
    assert res.status_code == 200
    assert res.get_json()["summary"]


def test_ticket_missing(client):
    assert client.get("/api/tickets/NOPE-999").status_code == 404


def test_heuristic_feature_contains_tag():
    feature = heuristic_feature(load_demo_tickets(DEMO)[0])
    assert "@jira-DEMO-101" in feature
    assert "Scenario:" in feature
    assert "Given" in feature


@pytest.mark.parametrize("key", ["DEMO-101", "DEMO-102", "DEMO-103"])
def test_behave_passes_for_demo_tickets(tmp_path, key):
    ticket = next(t for t in load_demo_tickets(DEMO) if t["key"] == key)
    feature, _ = generate_feature(ticket, use_ai=False)
    steps, _ = generate_steps(feature, ticket, use_ai=False)
    ws = prepare_workspace(tmp_path, key.lower())
    write_feature(ws, feature)
    write_steps(ws, steps)
    result = run_behave(ws)
    assert result.passed, result.stdout + "\n" + result.stderr


def test_pipeline_demo101_passes(app, tmp_path):
    run = execute_pipeline(
        "DEMO-101",
        demo_path=app.config["DEMO_TICKETS_PATH"],
        workspace_root=tmp_path / "ws",
        use_ai=False,
        max_iterations=2,
    )
    assert run.status == "passed"
    assert run.result and run.result["passed"] is True


def test_create_run_api(client):
    res = client.post(
        "/api/runs",
        json={"ticket_key": "DEMO-103", "use_ai": False, "max_iterations": 2},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "passed"
    assert data["feature"]
    assert data["steps"]
    assert data["iterations"]


def test_create_run_requires_key(client):
    assert client.post("/api/runs", json={}).status_code == 400


def test_index_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"CukeForge" in res.data


def test_heuristic_steps_is_valid_python():
    feature = heuristic_feature(load_demo_tickets(DEMO)[1])
    steps = heuristic_steps(feature)
    compile(steps, "<steps>", "exec")

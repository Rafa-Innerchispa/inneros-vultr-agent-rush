"""Smoke checks for the judge route being wired into the same real backend."""

from fastapi.testclient import TestClient
from inneros_agent_rush.main import create_app
from inneros_agent_rush.core import Ledger, WorkflowEngine
from inneros_agent_rush.runner import SandboxUnavailable


class UnavailableRunner:
    def ready(self):
        return False

    def run(self, code, tests):
        raise SandboxUnavailable("No Docker on the QA runner")


class RulesOnly:
    label = "deterministic_rules"
    enabled = False


def new_engine(tmp_path):
    return WorkflowEngine(Ledger(tmp_path / "judge.sqlite"), runner=UnavailableRunner(), model=RulesOnly())


def test_judge_is_a_bookmarkable_route_and_has_real_controls(tmp_path):
    with TestClient(create_app(new_engine(tmp_path), public_demo=True)) as client:
        page = client.get("/judge")
        assert page.status_code == 200
        html = page.text
        assert 'id="judge-workthrough"' in html
        assert 'id="judge-start"' in html
        assert 'id="judge-verify"' in html
        assert 'id="judge-complete"' in html
        assert 'id="containment"' in html
        assert 'id="containment-btn"' in html
        assert "BUILD 0.6.0" in html
        assert client.get("/healthz").json()["status"] == "ok"
        assert client.get("/api/runs").json() == []
        assert client.get("/api/tickets").json() == []


def test_judge_does_not_override_private_mode(tmp_path):
    with TestClient(create_app(new_engine(tmp_path), auth_token="secret", public_demo=False)) as client:
        assert client.get("/judge").status_code == 200
        assert client.get("/api/tickets").status_code == 401
        assert client.post("/api/triage", json={
            "title": "An invented outage", "description": "A hypothetical network fiber outage"
        }).status_code == 401

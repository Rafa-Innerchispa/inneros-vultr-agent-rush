"""Single-origin API for a real, auditable enterprise workflow demo."""
from __future__ import annotations

import hmac
import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from .core import CASES, Ledger, WorkflowEngine, event_chain_valid, verify_run_integrity
from .containment import SCENARIOS, describe_scenarios
from .remote_runner import RemoteRunner


ROOT = Path(__file__).parent


class TriageRequest(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=8, max_length=5000)
    customer: str = Field(default="Demo customer", min_length=1, max_length=100)


class ContainmentRequest(BaseModel):
    scenario_id: str = Field(min_length=2, max_length=40)


class TicketAction(BaseModel):
    action: str = Field(pattern="^(acknowledge|resolve|reopen)$")
    note: str = Field(min_length=12, max_length=1000)


class RepairRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=50)
    title: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    code: str | None = Field(default=None, max_length=16000)
    tests: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def require_custom_fields(self):
        if self.case_id not in CASES and not all([self.title, self.description, self.code, self.tests]):
            raise ValueError("Custom repairs require title, description, code and tests")
        if self.case_id in CASES and any(x is not None for x in (self.title, self.description, self.code, self.tests)):
            raise ValueError("Built-in cases do not accept overrides")
        return self


def create_app(engine: WorkflowEngine | None = None, *, auth_token: str | None = None,
               public_demo: bool | None = None) -> FastAPI:
    if engine is None:
        store = Ledger(os.getenv("DB_PATH", "./data/inneros_agent_rush.sqlite"))
        remote = RemoteRunner() if os.getenv("SANDBOX_RUNNER_URL") else None
        engine = WorkflowEngine(store, runner=remote)
    if auth_token is None:
        auth_token = os.getenv("AUTH_TOKEN", "")
    if public_demo is None:
        public_demo = os.getenv("PUBLIC_DEMO", "0") == "1"

    app = FastAPI(title="InnerOS Verified Operations", version="0.6.0",
                  description="Vultr Agent Rush: Powering the Future of Work")
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
    buckets = defaultdict(deque)
    containment_slot = threading.BoundedSemaphore(1)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
        )
        return response

    def authorized(header: str) -> bool:
        if not auth_token:
            return False
        scheme, _, credential = header.partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(credential, auth_token)

    def require_access(header: str, *, custom: bool = False):
        if authorized(header):
            return
        if public_demo and not custom:
            return
        raise HTTPException(status_code=401, detail="Operator token required")

    def limit(request: Request):
        source = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = buckets[source]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= 15:
            raise HTTPException(status_code=429, detail="Demo rate limit exceeded")
        bucket.append(now)

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    @app.get("/judge")
    def judge():
        """Stable, bookmarkable entrance for the judge's live workflow."""
        return FileResponse(ROOT / "static" / "index.html")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": "inneros-agent-rush", "sandbox_ready": engine.runner.ready(),
                "llm_mode": engine.model.label, "public_demo": public_demo,
                "data_mode": "real_executions_only"}

    @app.get("/api/cases")
    def cases():
        return [{"id": key, "title": value["title"], "description": value["description"]}
                for key, value in CASES.items()]

    @app.post("/api/triage")
    def triage(payload: TriageRequest, request: Request, authorization: str = Header(default="")):
        require_access(authorization)
        limit(request)
        return engine.run_triage(payload.title, payload.description, payload.customer,
                                 public_demo=public_demo and not authorized(authorization))

    @app.get("/api/containment/scenarios")
    def containment_scenarios():
        return {"cases": describe_scenarios(),
                "sandbox_requirements": "pre-pulled Docker image on isolated worker; no host-code execution"}

    @app.post("/api/containment/verify")
    def containment_verify(payload: ContainmentRequest, request: Request,
                           authorization: str = Header(default="")):
        require_access(authorization)
        limit(request)
        if payload.scenario_id not in SCENARIOS:
            raise HTTPException(status_code=422, detail="Unknown curated isolation scenario")
        if not containment_slot.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="Sandbox proof already running; try again")
        try:
            return engine.run_containment(payload.scenario_id,
                                          public_demo=public_demo and not authorized(authorization))
        finally:
            containment_slot.release()

    @app.post("/api/repair")
    def repair(payload: RepairRequest, request: Request, authorization: str = Header(default="")):
        is_custom = payload.case_id not in CASES
        require_access(authorization, custom=is_custom)
        limit(request)
        return engine.run_repair(**payload.model_dump(exclude_none=True),
                                 public_demo=public_demo and not authorized(authorization))


    @app.get("/api/tickets")
    def tickets(authorization: str = Header(default="")):
        require_access(authorization)
        results = engine.store.recent_tickets(public_only=not authorized(authorization))
        return [{"id": t["id"], "run_id": t["run_id"], "title": t["title"],
                 "customer": t["customer"], "status": t["status"],
                 "priority": t["priority"], "category": t["category"],
                 "updated_at": t["updated_at"], "last_evidence_hash": t["history"][-1]["hash"]}
                for t in results]

    @app.get("/api/tickets/{ticket_id}")
    def ticket_detail(ticket_id: str, authorization: str = Header(default="")):
        require_access(authorization)
        ticket = engine.store.one_ticket(ticket_id)
        if ticket is None or (not authorized(authorization) and not ticket.get("public_demo")):
            raise HTTPException(status_code=404, detail="Ticket not found")
        ticket["evidence_chain_valid"] = event_chain_valid(ticket["history"])
        return ticket

    @app.post("/api/tickets/{ticket_id}/action")
    def ticket_action(ticket_id: str, payload: TicketAction, request: Request,
                      authorization: str = Header(default="")):
        require_access(authorization)
        limit(request)
        ticket = engine.store.one_ticket(ticket_id)
        if ticket is None or (not authorized(authorization) and not ticket.get("public_demo")):
            raise HTTPException(status_code=404, detail="Ticket not found")
        # Public demo can change demo records only; no device or customer systems touched.
        try:
            result = engine.store.transition_ticket(ticket_id, payload.action, payload.note,
                                                     "operator" if authorized(authorization) else "demo_user")
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        result["evidence_chain_valid"] = event_chain_valid(result["history"])
        return result

    @app.get("/api/runs")
    def runs(authorization: str = Header(default="")):
        require_access(authorization)
        return [{"id": r["id"], "kind": r["kind"], "title": r["title"],
                 "status": r["status"], "created_at": r["created_at"],
                 "evidence_hash": r["events"][-1]["hash"] if r["events"] else None}
                for r in engine.store.recent(public_only=not authorized(authorization))]

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str, authorization: str = Header(default="")):
        require_access(authorization)
        result = engine.store.one(run_id)
        if result is None or (not authorized(authorization) and not result.get("public_demo")):
            raise HTTPException(status_code=404, detail="Run not found")
        result["evidence_chain_valid"] = event_chain_valid(result["events"])
        return result

    @app.get("/api/runs/{run_id}/verify")
    def verify_run(run_id: str, authorization: str = Header(default="")):
        require_access(authorization)
        result = engine.store.one(run_id)
        if result is None or (not authorized(authorization) and not result.get("public_demo")):
            raise HTTPException(status_code=404, detail="Run not found")
        return verify_run_integrity(result)

    @app.get("/api/runs/{run_id}/artifact")
    def artifact(run_id: str, authorization: str = Header(default="")):
        require_access(authorization)
        result = engine.store.one(run_id)
        if result is None or (not authorized(authorization) and not result.get("public_demo")) or result["artifact"] is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        content = (result["artifact"].get("content") or result["artifact"].get("candidate_code") or "")
        return PlainTextResponse(content, media_type="text/plain")

    return app


app = create_app()

"""Launch separately from the public web app, on a private dedicated runner VM."""
from __future__ import annotations

import hmac
import os
import threading
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .runner import DockerRunner, SandboxUnavailable


class ExecuteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=16000)
    tests: str = Field(min_length=1, max_length=10000)


def create_worker_app(*, worker_token: str | None = None, runner=None) -> FastAPI:
    token = worker_token if worker_token is not None else os.getenv("RUNNER_TOKEN", "")
    sandbox = runner or DockerRunner()
    slots = threading.BoundedSemaphore(2)
    app = FastAPI(title="InnerOS private sandbox worker", docs_url=None, redoc_url=None,
                  openapi_url=None)

    def authenticate(authorization: str):
        scheme, _, presented = authorization.partition(" ")
        if not token or scheme.lower() != "bearer" or not hmac.compare_digest(presented, token):
            raise HTTPException(status_code=401, detail="Private worker credential required")

    @app.get("/internal/healthz")
    def healthz(authorization: str = Header(default="")):
        authenticate(authorization)
        return {"sandbox_ready": sandbox.ready(), "host_execution_fallback": False}

    @app.post("/internal/execute")
    def execute(payload: ExecuteRequest, authorization: str = Header(default="")):
        authenticate(authorization)
        if not slots.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="Sandbox worker is at safe capacity")
        try:
            try:
                return sandbox.run(payload.code, payload.tests).public()
            except SandboxUnavailable as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        finally:
            slots.release()

    return app


app = create_worker_app()

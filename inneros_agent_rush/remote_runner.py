"""Authenticated RPC to a separate, disposable Vultr Docker worker VM."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .runner import ExecutionResult, SandboxUnavailable


class RemoteRunner:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url if base_url is not None else os.getenv("SANDBOX_RUNNER_URL", "")).rstrip("/")
        self.token = token if token is not None else os.getenv("RUNNER_TOKEN", "")

    def _request(self, route: str, payload: dict | None, *, timeout: float) -> dict:
        if not self.base_url or not self.token:
            raise SandboxUnavailable("Runner VM URL or private RPC token not configured")
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Authorization": "Bearer " + self.token,
                   "Content-Type": "application/json"}
        request = urllib.request.Request(self.base_url + route, data=body,
                                         headers=headers, method="POST" if body else "GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(16384)
                return json.loads(data)
        except (ValueError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SandboxUnavailable(f"Isolated worker RPC unavailable ({type(exc).__name__})") from exc

    def ready(self) -> bool:
        try:
            data = self._request("/internal/healthz", None, timeout=2.5)
            return bool(data.get("sandbox_ready"))
        except SandboxUnavailable:
            return False

    def run(self, code: str, tests: str) -> ExecutionResult:
        if len(code) > 16000 or len(tests) > 10000:
            raise ValueError("Input size limit exceeded")
        result = self._request("/internal/execute", {"code": code, "tests": tests}, timeout=20)
        if not all(key in result for key in ("passed", "exit_code", "stdout", "stderr", "timeout")):
            raise SandboxUnavailable("Worker returned invalid execution evidence")
        cleanup = result.get("cleanup_verified")
        if cleanup not in (True, False, None):
            raise SandboxUnavailable("Worker returned invalid cleanup verification")
        return ExecutionResult(bool(result["passed"]), result["exit_code"],
                               str(result["stdout"])[:4000], str(result["stderr"])[:4000],
                               bool(result["timeout"]), "remote_vultr_docker_worker",
                               cleanup_verified=cleanup)

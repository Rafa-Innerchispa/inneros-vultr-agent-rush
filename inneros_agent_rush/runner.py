"""Execute untrusted code ONLY inside disposable, tightly restricted Docker containers.

The host never evaluates a submitted program. A separate VM is strongly
recommended for the Docker daemon because access to docker.sock is privileged.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, replace


ENTRYPOINT = r'''
import json, sys, traceback
payload = json.load(sys.stdin)
ns = {"__name__": "__main__"}
try:
    exec(compile(payload["code"], "<candidate>", "exec"), ns)
    exec(compile(payload["tests"], "<assertions>", "exec"), ns)
    print("ASSERTIONS_PASSED")
except BaseException:
    traceback.print_exc(limit=8)
    sys.exit(2)
'''


@dataclass(frozen=True)
class ExecutionResult:
    passed: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timeout: bool
    execution_mode: str = "docker_isolated"
    cleanup_verified: bool | None = None

    def public(self) -> dict:
        return {"passed": self.passed, "exit_code": self.exit_code,
                "stdout": self.stdout, "stderr": self.stderr,
                "timeout": self.timeout, "execution_mode": self.execution_mode,
                "cleanup_verified": self.cleanup_verified}


class SandboxUnavailable(RuntimeError):
    pass


def _string(value: str | bytes | None, limit: int) -> str:
    return (value.decode(errors="replace") if isinstance(value, bytes) else (value or ""))[-limit:]


class DockerRunner:
    def __init__(self, image: str | None = None, *, timeout: int = 6):
        self.image = image or os.getenv("SANDBOX_IMAGE", "python:3.12-alpine")
        self.timeout = max(2, min(int(timeout), 20))

    def ready(self) -> bool:
        if not shutil.which("docker"):
            return False
        try:
            process = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True, timeout=3, check=False,
            )
            return process.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def _verify_cleanup(self, name: str) -> bool | None:
        """Explicitly confirm that Docker can no longer inspect the container.

        A missing container has recognizable stderr. Docker-daemon errors are
        deliberately NOT accepted as evidence of cleanup.
        """
        try:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True,
                           timeout=4, check=False)
            check = subprocess.run(["docker", "container", "inspect", name],
                                   capture_output=True, timeout=4, check=False)
            if check.returncode == 0:
                return False
            message = _string(check.stderr, 1000).lower()
            if "no such object" in message or "no such container" in message:
                return True
            return None
        except (OSError, subprocess.SubprocessError):
            return None

    def run(self, code: str, tests: str) -> ExecutionResult:
        if len(code) > 16000 or len(tests) > 10000:
            raise ValueError("Candidate or assertions exceed strict input limit")
        if not self.ready():
            raise SandboxUnavailable("Docker daemon or pre-pulled sandbox image unavailable; execution blocked")

        name = "iar-" + uuid.uuid4().hex[:16]
        command = [
            "docker", "run", "--name", name, "--rm", "-i", "--pull", "never",
            "--network", "none", "--read-only", "--user", "65534:65534",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "32", "--memory", "128m", "--cpus", "0.5",
            "--ulimit", "nofile=64:64", "--tmpfs", "/tmp:rw,nosuid,noexec,size=16m",
            "--workdir", "/tmp", self.image, "python", "-c", ENTRYPOINT,
        ]
        outcome = None
        try:
            response = subprocess.run(
                command, input=json.dumps({"code": code, "tests": tests}),
                capture_output=True, text=True, timeout=self.timeout + 4,
                check=False,
            )
            outcome = ExecutionResult(
                passed=response.returncode == 0 and "ASSERTIONS_PASSED" in response.stdout,
                exit_code=response.returncode,
                stdout=_string(response.stdout, 4000), stderr=_string(response.stderr, 4000),
                timeout=False,
            )
        except subprocess.TimeoutExpired as exc:
            outcome = ExecutionResult(False, None, _string(exc.stdout, 2000),
                                      "Sandbox execution exceeded wall-clock limit", True)
        except OSError as exc:
            raise SandboxUnavailable(f"Docker executable failed: {type(exc).__name__}") from exc
        finally:
            cleanup_verified = self._verify_cleanup(name)
        assert outcome is not None
        return replace(outcome, cleanup_verified=cleanup_verified)

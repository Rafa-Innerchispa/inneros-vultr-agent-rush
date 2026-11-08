"""Curated, non-customizable isolation challenges for the private Docker worker.

This is a technical security demonstration, not a proof of security against a
container escape or a signed remote hardware attestation. No submitted code
runs on the public API host. Real Docker is mandatory to claim a passed check.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    objective: str
    code: str
    assertions: str
    expected: str = "assertions_pass"


SCENARIOS = {
    "network_egress": Scenario(
        id="network_egress",
        title="Block outbound network traffic",
        objective="Container sees only loopback and cannot open a direct external TCP connection.",
        code=(
            "import socket\n"
            "interfaces = [name for _index, name in socket.if_nameindex()]\n"
            "sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "sock.settimeout(0.4)\n"
            "try:\n"
            "    sock.connect(('203.0.113.42', 443))  # IANA TEST-NET-3\n"
            "except OSError:\n"
            "    egress_blocked = True\n"
            "else:\n"
            "    egress_blocked = False\n"
            "finally:\n"
            "    sock.close()\n"
            "print('interfaces:', interfaces, 'egress_blocked:', egress_blocked)\n"
        ),
        assertions="assert interfaces == ['lo'], interfaces\nassert egress_blocked is True\n",
    ),
    "read_only_root": Scenario(
        id="read_only_root",
        title="Protect the root filesystem",
        objective="Root filesystem is mounted read-only, while a restricted scratch tmpfs remains writable.",
        code=(
            "import os, pathlib\n"
            "root_read_only = bool(os.statvfs('/').f_flag & os.ST_RDONLY)\n"
            "try:\n"
            "    pathlib.Path('/etc/inneros-proof-should-not-exist').write_text('never', encoding='utf-8')\n"
            "except OSError:\n"
            "    system_write_blocked = True\n"
            "else:\n"
            "    system_write_blocked = False\n"
            "pathlib.Path('/tmp/inneros-canary').write_text('scratch only', encoding='utf-8')\n"
            "scratch_works = pathlib.Path('/tmp/inneros-canary').read_text(encoding='utf-8') == 'scratch only'\n"
            "print('root_read_only:', root_read_only, 'system_write_blocked:', system_write_blocked)\n"
        ),
        assertions=(
            "assert root_read_only is True\n"
            "assert system_write_blocked is True\n"
            "assert scratch_works is True\n"
        ),
    ),
    "runaway_timeout": Scenario(
        id="runaway_timeout",
        title="Kill an unbounded execution",
        objective="An intentional infinite loop is forcibly stopped and its container removal is independently checked.",
        code="while True:\n    pass\n",
        assertions="assert False, 'Unreachable if the timeout guard works'\n",
        expected="timeout_and_cleanup",
    ),
}


def describe_scenarios() -> list[dict[str, str]]:
    return [{"id": item.id, "title": item.title, "objective": item.objective,
             "expected": item.expected} for item in SCENARIOS.values()]


def classify_scenario_result(scenario: Scenario, result) -> tuple[bool, str]:
    """Never treat a mock, absent Docker, or an unverified cleanup as proof."""
    if result.execution_mode not in {"docker_isolated", "remote_vultr_docker_worker"}:
        return False, "Execution mode is not an allowed isolated Docker worker"
    if result.cleanup_verified is not True:
        return False, "Container removal could not be independently verified"
    if scenario.expected == "timeout_and_cleanup":
        return (result.timeout is True and result.passed is False,
                "Timeout enforced and container absent" if result.timeout and not result.passed
                else "Intentional infinite loop did not time out")
    return (result.passed is True and not result.timeout,
            "Container assertions passed" if result.passed and not result.timeout
            else "Container assertions failed or timed out")

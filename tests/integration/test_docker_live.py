"""On CI, these checks exercise a real, disposable Docker runtime.

Not part of the fast local suite unless RUN_SANDBOX_INTEGRATION=1. Never run
this on a shared production host. Docker control is root-equivalent.
"""
import os
import subprocess

import pytest

from inneros_agent_rush.runner import DockerRunner
from inneros_agent_rush.containment import SCENARIOS, classify_scenario_result


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SANDBOX_INTEGRATION") != "1",
    reason="Requires a dedicated disposable Docker runner VM",
)


def test_real_docker_pass_failure_and_containment():
    runner = DockerRunner("python:3.12-alpine", timeout=2)
    assert runner.ready(), "Pre-pull the fixed image on the disposable CI VM"
    passing = runner.run("def add(a,b): return a+b", "assert add(1,2)==3")
    assert passing.passed and passing.execution_mode == "docker_isolated"
    assert passing.cleanup_verified is True
    failing = runner.run("def add(a,b): return a-b", "assert add(1,2)==3")
    assert not failing.passed and not failing.timeout
    runaway = runner.run("while True:\n    pass", "assert True")
    assert runaway.timeout and not runaway.passed
    assert runaway.cleanup_verified is True
    remaining = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=iar-", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=5, check=True,
    )
    assert not remaining.stdout.strip(), "Sandbox container cleanup must be verified"


def test_live_containment_lab_network_read_only_and_timeout():
    """Must run on dedicated Docker CI, never on production or bare host."""
    runner = DockerRunner("python:3.12-alpine", timeout=2)
    assert runner.ready()
    for scenario in SCENARIOS.values():
        result = runner.run(scenario.code, scenario.assertions)
        passed, reason = classify_scenario_result(scenario, result)
        assert passed, f"{scenario.id}: {reason}; {result.public()}"

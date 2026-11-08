"""The security invariant is absence of host-code fallback."""
import pytest
from unittest.mock import patch
from subprocess import CompletedProcess
from inneros_agent_rush.runner import DockerRunner, SandboxUnavailable


def test_missing_docker_never_tries_host_execution():
    runner = DockerRunner()
    with patch("inneros_agent_rush.runner.shutil.which", return_value=None):
        with patch("inneros_agent_rush.runner.subprocess.run") as process:
            with pytest.raises(SandboxUnavailable):
                runner.run("print('do not execute on host')", "assert True")
            process.assert_not_called()


def test_docker_invocation_contains_guards_and_removes_container():
    runner = DockerRunner()
    calls = []
    def fake_call(command, **kwargs):
        calls.append((command, kwargs))
        if command[:3] == ["docker", "image", "inspect"]:
            return CompletedProcess(command, 0, b"{}", b"")
        if command[:2] == ["docker", "run"]:
            return CompletedProcess(command, 0, "ASSERTIONS_PASSED\n", "")
        if command[:3] == ["docker", "container", "inspect"]:
            return CompletedProcess(command, 1, "", "Error: No such object: tested")
        return CompletedProcess(command, 0, "", "")
    with patch("inneros_agent_rush.runner.shutil.which", return_value="/usr/bin/docker"):
        with patch("inneros_agent_rush.runner.subprocess.run", side_effect=fake_call):
            result = runner.run("x=1", "assert x==1")
    assert result.passed
    cmd = calls[1][0]
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "none"
    assert "--read-only" in cmd and "--cap-drop" in cmd
    assert "no-new-privileges" in cmd and "--pids-limit" in cmd
    assert "--memory" in cmd and "--cpus" in cmd
    assert "--user" in cmd and cmd[cmd.index("--user") + 1] == "65534:65534"
    assert calls[-2][0][:3] == ["docker", "rm", "-f"]
    assert calls[-1][0][:3] == ["docker", "container", "inspect"]
    assert result.cleanup_verified is True
    assert calls[1][1]["input"].startswith('{"code":')

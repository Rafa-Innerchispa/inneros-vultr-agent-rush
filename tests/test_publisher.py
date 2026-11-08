"""Safe publisher authentication discovery (no actual GitHub network call)."""
import subprocess
from unittest.mock import patch

from scripts.publish_github import discover_token


def test_prefers_existing_env_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "placeholder-secret")
    monkeypatch.setenv("GH_TOKEN", "less-preferred")
    with patch("scripts.publish_github.subprocess.run") as run:
        assert discover_token() == "placeholder-secret"
    run.assert_not_called()


def test_reads_authenticated_gh_without_logging_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with patch("scripts.publish_github.shutil.which", return_value="/usr/bin/gh"), \
         patch("scripts.publish_github.subprocess.run", return_value=subprocess.CompletedProcess(
             args=["gh", "auth", "token"], returncode=0, stdout="fake-token\n", stderr="")):
        assert discover_token() == "fake-token"


def test_no_gh_returns_none(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with patch("scripts.publish_github.shutil.which", return_value=None):
        assert discover_token() is None

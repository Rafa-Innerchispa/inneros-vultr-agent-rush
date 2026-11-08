#!/usr/bin/env python3
"""Create the dedicated public GitHub repository and push this project.

This opt-in publisher uses GITHUB_TOKEN/GH_TOKEN from the environment or
an already authenticated GitHub CLI (`gh auth login`) on the same computer.
It NEVER writes credentials into Git remote URLs or the repository.

Usage:
    python scripts/publish_github.py                # read-only plan
    python scripts/publish_github.py --execute     # with authenticated `gh`
    GITHUB_TOKEN=... python scripts/publish_github.py --execute
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "Rafa-Innerchispa"
NAME = "inneros-vultr-agent-rush"
DESCRIPTION = "InnerOS Verified Operations | Vultr Agent Rush 2026: verifiable enterprise workflows"
REMOTE_URL = f"https://github.com/{OWNER}/{NAME}.git"
REPO_ROOT = Path(__file__).resolve().parent.parent


def git(*args: str, env: dict | None = None) -> str:
    result = subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                            env=env, text=True, capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError("Git operation failed: " + " ".join(args) + "\n" + result.stderr[-800:])
    return result.stdout.strip()


def github_json(route: str, token: str, *, method="GET", data: dict | None = None):
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request("https://api.github.com" + route, data=body,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as reply:
            return json.loads(reply.read(65536))
    except urllib.error.HTTPError as exc:
        if method == "GET" and exc.code == 404:
            return None
        raise RuntimeError(f"GitHub API rejected {method} {route}: HTTP {exc.code}") from None


def push_with_askpass(token: str) -> None:
    # Git may invoke GIT_ASKPASS for the username/password; never show the token.
    with tempfile.TemporaryDirectory(prefix="inneros-gh-auth-") as folder:
        script = Path(folder) / "askpass.sh"
        script.write_text("""#!/bin/sh
case "$1" in
  *Username*) printf '%s' 'x-access-token';;
  *Password*) printf '%s' "$GITHUB_TOKEN";;
  *) exit 1;;
esac
""")
        script.chmod(stat.S_IRWXU)
        environment = os.environ.copy()
        environment.update({"GIT_ASKPASS": str(script), "GIT_TERMINAL_PROMPT": "0",
                            "GITHUB_TOKEN": token})
        git("-c", "credential.helper=", "push", "-u", "origin", "main", env=environment)


def discover_token() -> str | None:
    """Use existing local CLI authentication without printing, persisting or echoing it."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    if not shutil.which("gh"):
        return None
    try:
        result = subprocess.run(["gh", "auth", "token"], check=False,
                                capture_output=True, text=True, timeout=12)
    except (OSError, subprocess.TimeoutExpired):
        return None
    # Do not log stdout or stderr: gh auth token prints a secret on stdout.
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token if token else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Create the public remote and push main")
    args = parser.parse_args()
    expected_url = f"https://github.com/{OWNER}/{NAME}"
    print("Repository:", expected_url)
    print("Branch: main | visibility: PUBLIC | no production InnerOS changes")
    if not args.execute:
        print("PLAN ONLY. No network mutations or remote GitHub creation attempted.")
        return 0
    if git("status", "--porcelain"):
        raise RuntimeError("Commit local changes before publishing; refusing a partial push")
    if git("branch", "--show-current") != "main":
        raise RuntimeError("Expected main branch; refusing to push a different branch")
    token = discover_token()
    if not token:
        raise RuntimeError("No GitHub credentials. Run `gh auth login` in your own terminal, "
                           "then repeat --execute; never paste tokens into chat")
    actor = github_json("/user", token)
    if actor.get("login", "").lower() != OWNER.lower():
        raise RuntimeError("Authenticated GitHub account does not match the requested owner")
    existing = github_json(f"/repos/{OWNER}/{NAME}", token)
    if existing is None:
        github_json("/user/repos", token, method="POST", data={
            "name": NAME, "description": DESCRIPTION, "private": False,
            "auto_init": False, "has_issues": True, "has_wiki": False,
        })
        print("GitHub remote created:", expected_url)
    else:
        if existing.get("full_name", "").lower() != f"{OWNER}/{NAME}".lower():
            raise RuntimeError("Repository identity mismatch")
        if existing.get("private"):
            raise RuntimeError("Existing repository is private, not eligible for public submission")
        print("Existing public repository found:", expected_url)
    try:
        git("remote", "get-url", "origin")
    except RuntimeError:
        git("remote", "add", "origin", REMOTE_URL)
    else:
        git("remote", "set-url", "origin", REMOTE_URL)
    push_with_askpass(token)
    print("Code pushed to:", expected_url)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Refuse to print arbitrary credential-bearing objects.
        print("Publication did not complete:", str(error), file=sys.stderr)
        raise SystemExit(2)

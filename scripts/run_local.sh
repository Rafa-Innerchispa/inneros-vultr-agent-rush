#!/usr/bin/env bash
# Local-only (AMD/Intel/WSL/Linux) developer/demo launcher. No public listen.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -q -r requirements.txt
mkdir -p data
export DB_PATH="${DB_PATH:-$ROOT/data/inneros_agent_rush.sqlite}"
export PUBLIC_DEMO=1
export AUTH_TOKEN=""
printf '%s\n' 'LOCAL-ONLY demo: http://127.0.0.1:8000/judge' 'No Vultr deployment or Docker execution is implied.'
exec .venv/bin/python -m uvicorn inneros_agent_rush.main:app --host 127.0.0.1 --port 8000

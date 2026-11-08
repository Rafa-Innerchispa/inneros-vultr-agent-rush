#!/usr/bin/env bash
# Safe deployment entrypoint. No changes unless --apply is explicitly present.
# Run on the OWNER-AUTHORIZED Vultr Ubuntu VM, not on InnerOS production.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN=""
APPLY=0
VERIFY=0
usage(){ printf '%s\n' 'Usage: bash scripts/deploy_vultr.sh --domain YOUR_PUBLIC_DNS [--apply] [--verify]' 'No --apply: preflight only; no Docker/network mutations.'; }
while (( $# )); do
  case "$1" in
    --domain) [[ $# -gt 1 ]] || { usage; exit 2; }; DOMAIN="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --verify) VERIFY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done
if [[ -z "$DOMAIN" || ! "$DOMAIN" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ || "$DOMAIN" != *.* || "$DOMAIN" == *..* || ${#DOMAIN} -gt 253 ]]; then
  printf 'ERROR: --domain must be a valid lowercase DNS hostname (e.g. demo.example.org)\n' >&2
  exit 2
fi
if (( VERIFY && ! APPLY )); then printf 'ERROR: --verify needs --apply\n' >&2; exit 2; fi
printf 'Project: %s\nPublic URL target: https://%s/judge\n' "$ROOT" "$DOMAIN"
printf 'Expected services: public Caddy HTTPS + isolated API/SQLite backend. No worker VM provisioned.\n'
if (( ! APPLY )); then
  printf 'PREFLIGHT ONLY: no resources were created or modified.\n'
  exit 0
fi
for binary in docker curl; do
  command -v "$binary" >/dev/null || { printf 'ERROR: %s not installed.\n' "$binary" >&2; exit 1; }
done
docker compose version >/dev/null || { printf 'ERROR: Docker Compose V2 plugin unavailable.\n' >&2; exit 1; }
cd "$ROOT"
export DEMO_DOMAIN="$DOMAIN"
docker compose --profile public config --quiet
docker compose --profile public up --build -d
printf 'Health check for the Vultr-local backend...\n'
curl --fail --silent --show-error --max-time 12 http://127.0.0.1:8000/healthz
printf '\nVerify public HTTPS after DNS and certificate issuance: https://%s/judge\n' "$DOMAIN"
if (( VERIFY )); then
  python scripts/smoke_deployment.py --url "https://$DOMAIN"
fi

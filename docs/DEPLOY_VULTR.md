# Deployment playbook: Vultr Agent Rush

**Not deployed yet.** The below procedure is a runbook, not an assertion of a live environment.

## Minimum judging requirements (Challenge 2)

- Vultr VM must run the **backend orchestrator**, not just serve static files.
- The public web app must also be hosted on Vultr and reachable via HTTPS.
- Model inference is optional for the track, though a connected local Qwen model strengthens the technology demonstration.
- Public GitHub repo, demo URL, recorded video and architectural explanations must be submitted on LabLab.


## Hackathon credits and account eligibility

The organizer offers $200 credits for eligible participants. The event signup instructions specify an email that has never been associated with Vultr. Vultr's general billing documentation also limits promotional codes to one per user and requires a validated payment method. A different email address **does not by itself guarantee eligibility** if an account already belongs to the same owner. Confirm acceptance in the Vultr console and do not treat credits as available until the billing screen actually shows the balance. Do not create duplicate accounts to evade promotional rules.

Official links:

- Hackathon and credit claim instructions: https://lablab.build/ai-hackathons/vultr-hackathon
- Vultr registration: https://www.vultr.com/register/
- Vultr promotional-code requirements: https://docs.vultr.com/support/platform/billing/how-can-i-add-a-promotional-code

**Deployment gate:** Verify remaining credit and the actual instance rate before provisioning. Prefer one small web VM initially, preserve local-first model routing, and add a separate isolated worker only when the public judge journey is stable and verified. Delete unused instances before credits expire or billing will continue. Do not place real customer identifiers, secrets, or billing credentials in the public GitHub repository.

## Initial deployment (triage only, safe public mode)

Use Ubuntu 24.04 on a dedicated, up-to-date Vultr Cloud Compute VM with a public IPv4 address and a DNS name. Install Docker Engine and Docker Compose plugin following official guidance. The Compose service is deliberately **not given a Docker socket**, so code execution is unavailable in this deployment mode. This keeps untrusted runtime privileges out of the web container.

```bash
git clone <YOUR-NEW-PUBLIC-REPO-URL>
cd inneros-vultr-agent-rush
docker compose up --build -d
curl -f http://127.0.0.1:8000/healthz
```

For a one-command deployment **after installing Docker + Compose**, use the included
Caddy public profile and the guarded script:

```bash
bash scripts/deploy_vultr.sh --domain your-real-dns.example   # no-op preflight
bash scripts/deploy_vultr.sh --domain your-real-dns.example --apply --verify
```

The `--apply` flag is required for any change. The web app remains localhost
on port 8000; Caddy terminates HTTPS on ports 80 and 443. The hostname must
have a real DNS record pointing to the VPS. Caddy may need a few minutes to
issue a certificate after ports are accessible. Alternatively, add an HTTPS
reverse proxy (Caddy or Nginx) in front of `127.0.0.1:8000`, and configure DNS. Only allow ports 80/443 from the Internet via Vultr firewall. Block direct port 8000. Use Vultr firewall, OS firewall, and automatic security updates. For any sensitive data set `PUBLIC_DEMO=0`, provision an authentication layer, and use `AUTH_TOKEN` in a secret manager rather than committed configuration.

Example Caddyfile:

```caddyfile
demo.your-domain.example {
    reverse_proxy 127.0.0.1:8000
}
```

Never copy that example hostname as if it were a working site.

## Verified code execution stage (separate private worker VM)

The codebase includes `inneros_agent_rush.worker_service`, a **private authenticated** Docker execution service. This is the preferred demo deployment: one public Vultr VM runs the web application; a second dedicated, disposable Vultr VM runs Docker and the worker API. The public app container **never mounts a Docker socket**.

1. Provision a second Vultr Cloud Compute VM on the **same private Vultr network**. Do not expose port `8050` to the public Internet. Restrict the worker ingress to the web VM's private address only, and use network-layer encryption (WireGuard/Tailscale or TLS) for any traffic outside a trusted isolated network.
2. Install Python 3.12+, Docker Engine and code on that worker VM. The worker process needs Docker access, which is host-root-equivalent: keep the worker VM disposable, patched, and free of other secrets.
3. Pre-pull `python:3.12-alpine` and set a unique high-entropy shared secret as the worker's `RUNNER_TOKEN` in a local root-readable environment file, not in Git.
4. Start the private worker API bound **only to the worker VM's private IP**:

```bash
docker pull python:3.12-alpine
# Load RUNNER_TOKEN securely from the machine's protected service config.
uvicorn inneros_agent_rush.worker_service:app --host 10.0.0.2 --port 8050
```

`10.0.0.2` is an **example**, not an existing instance. Run this under systemd or a hardened service supervisor on the worker, with explicit lifecycle restart settings. Do not treat a local terminal session as a production daemon.

5. On the **web** VM, configure Compose environment variables `SANDBOX_RUNNER_URL=http://<WORKER_PRIVATE_IP>:8050` and the same `RUNNER_TOKEN`. Recreate the backend container. The worker token is never sent to the browser or to the untrusted code container.
6. Verify the web `GET /healthz` reports `sandbox_ready: true` before testing repairs; try the off-by-one repair and `runaway_loop` timeout. Verify no container remains on the worker after each run, including the deadline scenario.

**Security note:** this MVP provides a private worker boundary with authorization and two concurrent execution slots. It does not yet implement signed job IDs, independent cleanup auditing, or kernel-level isolation stronger than standard Docker. A compromised worker VM is still possible; isolate its blast radius further for production.

## Local-first model connection

Private Qwen endpoint on InnerChispa's AMD machine can be made available through a private encrypted network path. Configure `LLM_BASE_URL` / `LLM_MODEL` on the backend only. No LLM creds in the sandbox. If the private tunnel fails, the two scripted demonstration cases use labelled deterministic repair rules. Custom cases do not quietly fall back to a fabricated LLM response.

## Deployment acceptance checklist

- [ ] Vultr instance billing and location verified, no unsanctioned cloud costs
- [ ] VM IP and DNS available, firewall blocks direct API port
- [ ] HTTPS serves web UI on Vultr
- [ ] `GET /judge` serves a working judge walkthrough with all three controls; `POST /api/triage` stores run and linked ticket atomically; `GET /api/runs/{id}` and `GET /api/tickets/{id}` verify both chains
- [ ] `python scripts/smoke_deployment.py --url https://YOUR-ACTUAL-DEMO-URL` passes the **full synthetic lifecycle** with report and ticket verification
- [ ] GitHub Actions isolated-execution job passes against an actual disposable Docker runner
- [ ] Authenticated remote Docker worker tested on isolated executor VM, no app process execution
- [ ] Forced timeout container stops and cleanup is verified independently
- [ ] Security and privacy review: no private customer data or keys in public demo
- [ ] Optional local Qwen/vLLM configured and verified or rules-only mode explicitly disclosed
- [ ] README updated with *real* Vultr public URL and actual services used
- [ ] Recorded video captures real online app and sandbox moment
- [ ] LabLab submission complete before **2026-11-08 23:00 UTC** (verify dashboard deadline)

## Publish preflight

The publishing script is non-destructive by default:

```bash
python scripts/publish_github.py
# In an authorized environment only; never paste the token into chat or commit it.
GITHUB_TOKEN="$GITHUB_TOKEN" python scripts/publish_github.py --execute
```

The public repo must be verified via a real GitHub response after publishing. An authenticated
remote browser in Work mode can instead create the repository and push the bundled source
using its own legitimate GitHub session. The Chat connector may read existing GitHub repos
without providing a repository-creation action; that is not evidence of successful publication.

See [`JUDGE_ACCEPTANCE.md`](JUDGE_ACCEPTANCE.md) for the judge-first release gate and public acceptance protocol.

## Containment Lab checks (v0.6.0)

`POST /api/containment/verify` only accepts three curated cases. The public
judge UI displays the worker status and each real attempt. Passing requires
an isolated Docker runner AND a separate `docker container inspect` after
forced cleanup that confirms no container remains. A missing/unreachable
worker is recorded as `blocked`; an inconclusive cleanup check is `failed`.

A 1 GB Vultr VM can run the public web/API and Caddy, but must **not** be the
untrusted Docker worker. A second, hardened disposable VM is recommended for
that role. If the worker or Vultr Serverless Inference is not verified, submit
**Powering the Future of Work**, not Blast Radius Zero.

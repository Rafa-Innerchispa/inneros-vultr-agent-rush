# Judge acceptance and release gate

**Current state:** Judge route and API workflows built and tested locally; not yet deployed. Public URLs and CI results must not be invented.

**Official cutoff:** 2026-11-08 23:00 UTC (18:00 America/Guayaquil). Internal freeze and submission target: 17:00 America/Guayaquil. Check the event dashboard immediately before submission in case the organizers update it.

## Entry point first

The final URL will be `https://<ACTUAL_VULTR_HOST>/judge`. The hostname must be populated **only after** a real Vultr deployment and independent HTTPS check. The `/judge` path is served by the same FastAPI backend as the API; it is not a static mock page.

The panel walks judges through an honest **synthetic** support-ticket scenario. It does not imply that a real customer's equipment was inspected or repaired:

| Gate | What the browser must display | What the backend must actually do | Evidence |
|---|---|---|---|
| 0. Availability | HTTPS, title and visible judge panel | `GET /judge`, `GET /healthz` 200 | external browser / public smoke |
| 1. Real intake | Run id, P1 classification, ticket short ID | `POST /api/triage` writes run, report and linked ticket | SQLite record + run events |
| 2. Independent verification | `PASS`, actual 64-character digest | `GET /api/runs/{id}/verify`, `GET /api/tickets/{id}` | report SHA-256 plus two valid chains |
| 3. Lifecycle | Synthetic ticket resolved, 3 events | `POST /api/tickets/{id}/action` twice, then re-fetch | persisted state and history |
| 4. Sandbox | Clearly states worker availability; test cannot fake success | `GET /healthz` plus `POST /api/containment/verify` for fixed probes | dedicated Docker CI and independent cleanup check |
| 5. Security | Demo data only; no exposed token | private runs/tickets invisible to public; no host execution fallback | unit and isolation tests |
| 6. Frontend QA | Desktop, mobile and no uncaught JS errors | browser automation clicks the controls | CI screenshots and job log |

## Automated verification

```sh
# deterministic API/workflow tests
python -m pytest -q
# real Chromium UI automation (requires Playwright + Chromium; run in CI)
python scripts/judge_browser_qa.py --screenshots .judge-qa
# final public acceptance, replaces SAMPLE with the verified actual URL
python scripts/smoke_deployment.py --url https://SAMPLE-REAL-VULTR-HOST
```

The Chromium acceptance harness must fail loudly if the browser cannot navigate due to local administrator policy; API tests alone **do not certify visual or browser behavior**.

## Five release gates for every future InnerChispa hackathon

1. **Public link immediately:** publish a real backend and judge route before new features; keep it updated continuously.
2. **User journey before marketing:** decide the exact 2-3 minute demo script and wire the UI to real APIs.
3. **Continuous acceptance:** API, browser interactions, mobile layout, screenshots, error states, and persisted evidence at every change.
4. **Submission before the final hour:** code and demo stable; all links reopened in an incognito browser on a different network; video is recorded from the actual deployed app.
5. **Freeze submission version:** capture commit SHA, deployment version, judge URL, real CI results, and dated evidence. Continue product development on a separate branch.

Never use a local HTML screenshot, mocked runner, a fabricated dashboard status, or a localhost address as proof of public deployment. A working frontend in the repository and a working public frontend are two **different** acceptance gates.

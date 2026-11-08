# Vultr Agent Rush 2026: canonical decisions and cross-chat handoff

> Cut: 2026-11-07, Ecuador. Notion canonical record:
> Private account recovery and support details are stored in the owner-only Notion checkpoint, not this public source tree.
>
> This file records decisions and evidence status. It is not proof of a deployed
> application, an accepted second track, or a finished submission.

## 1. Product and scope

- Project: **InnerOS Verified Operations**, independent hackathon implementation.
- Real-value workflow: incident intake -> severity/plan -> persisted ticket ->
  action/authorization where applicable -> operator lifecycle -> hash-chained
  evidence and independently verified Markdown report.
- Public judge scenario uses synthetic incident data loosely informed by
  operational experience. Do not expose customer names, private IPs, credentials,
  CCTV feeds, or suggest that simulated intervention repaired physical equipment.
- NEVER modify production InnerOS main or use production DevSwarm queues to
  satisfy hackathon acceptance without a separately authorized change.

## 2. Dual development fronts; submission policy

### A. PRIMARY: Powering the Future of Work

- Deliver complete B2B operations flow with publicly accessible web UI and
  backend running on Vultr infrastructure.
- Make the real `/judge` endpoint the primary launch and evaluation entry point.
- Local Qwen/vLLM inference is OPTIONAL and must be labelled honestly. Do not
  misrepresent deterministic rules or canned patches as live model output.

### B. SECONDARY CAPABILITY: Blast Radius Zero / Containment Lab

- Extend the same codebase with isolated execution tests for network egress
  denial, read-only filesystem, resource and time limits, guaranteed cleanup,
  and verification of evidence.
- Reuse the existing sandbox runner and hash evidence rather than inventing a
  parallel app or making unsourced security guarantees.
- Live Docker behavior requires real execution on a disposable sandbox host;
  mocks and unit tests do NOT certify host containment.
- Claim Challenge 1 only if both isolation is live on Vultr AND the required
  agent inference is actually routed through Vultr Serverless Inference.
  The AMD local model alone does not meet those conditions.
- Two engineering fronts do NOT mean two hackathon submissions. The event flow
  was understood to require selecting a challenge. Keep Challenge 2 as primary;
  verify the official registration form and rules before any second submission
  or switch of challenge. Avoid duplicate or conflicting entries.

## 3. Local-first architecture

Web judge -> Vultr HTTPS / FastAPI / API / SQLite audit -> policy + execution.

Separate trust boundaries:
- Public web/API on an accessible Vultr VM (a small 1 GB VM can be considered
  for the lightweight app, subject to actual host capacity).
- Optional AMD local Qwen model via private authorized tunnel, not an open
  unauthenticated inference port. Provide honest degraded/fallback mode.
- Optional remote sandbox worker on an isolated, disposable Vultr VM with
  Docker; never expose docker.sock publicly or run untrusted code on production.
- Challenge 1 adds Vultr Serverless Inference when/if proven eligible.
- Without a Docker worker, code execution must fail CLOSED and show a genuine
  unavailable state. A mocked safety demo is not an acceptance result.

## 4. Judge-first delivery and QA rule (Flip Switch lesson)

- A frontend in source code is not a published demo. Prioritize an externally
  reachable HTTPS judge URL before adding extra presentation polish.
- Mandatory journey: create synthetic incident -> classify and plan -> create
  ticket -> acknowledge/resolve -> verify report digest and event/ticket chains.
- Test API, real desktop and mobile browser clicks, private/public access,
  persistence across refresh/restart, error handling, and accurate model/runner
  status. Keep screenshots and test logs.
- Script and record the video only after the real deployed flows pass.
- Freeze the submitted version and continue product development on a separate
  branch, preserving the exact commit and deployment version.

## 5. Current verified and unverified status at handoff

- Last stable local baseline: v0.5.0, commit `0c90164`, with 25 passing local
  unit/API tests; 1 Docker integration skipped. Judge page `/judge` exists.
- Chromium visual QA was blocked by a policy of the earlier local environment;
  browser acceptance script and CI workflow were prepared, not verified there.
- The working tree may have UNCOMMITTED containment changes made after the
  baseline. Inspect `git status` and tests before editing or merging them.
- No actual sandbox isolation on Vultr, production Vultr LLM integration,
  public deployment, externally tested judge URL, or LabLab submission has
  been verified.
- Planned GitHub repository: `Rafa-Innerchispa/inneros-vultr-agent-rush`.
  Last connector check returned 404. Local git is NOT remote publication.

## 6. Infrastructure access and privacy

- Vultr account access and any promotional-credit eligibility still require the owner's authorized sign-in and provider verification. Do not open duplicate accounts to evade promotional conditions.
- Sensitive account-recovery information, email addresses, support cases, invoices and historical IP addresses are kept **only** in the private Notion decision checkpoint, not in the public source repository.
- Existing Vultr infrastructure status is unverified. A bill paid is not proof that a currently accessible VM is available.
- No additional paid infrastructure was provisioned by this source release.
- Never store passwords, tokens, OTPs, billing secrets, private customer addresses or SSH keys in the public repo.

## 7. Deadline and submission gates

- Event dates: November 3-8, 2026.
- Previously checked deadline: November 8, 23:00 UTC / 18:00 Ecuador;
  **verify within LabLab dashboard before relying on this**.
- Internal target: 17:00 Ecuador on November 8.
- Pending gates: accessible Vultr account and VM, GitHub public repo, HTTPS
  `/judge` (real API and state), external E2E desktop/mobile acceptance,
  verified sandbox (if claimed), video, source link, final LabLab submission.

## 8. Next agent's action sequence

1. Read this public file and, if authorized, the private Notion checkpoint; confirm which track the owner
   actually submitted/selected in LabLab, rather than guessing.
2. Inspect repo status first; preserve work in progress. Run API tests.
3. Complete containment tests and UI with transparent fail-closed behavior.
4. Run Docker integration on an authorized disposable host and Chromium QA.
5. Create/push a separate public GitHub repo with an authorized session.
6. Obtain valid Vultr deploy access; publish `/judge` and test from an external
   network BEFORE recording video.
7. Publish truthfully, submit, record submission proof, and freeze release.

## 9. Canonical links

- Private decisions and account recovery: maintained in the owner's Notion workspace (not linked publicly)
- Official event: https://lablab.ai/ai-hackathons/vultr-hackathon
- Vultr console: https://console.vultr.com/
- Planned public repo (NOT verified): https://github.com/Rafa-Innerchispa/inneros-vultr-agent-rush

## 10. Copy/paste recovery message

"Retoma Vultr Agent Rush / InnerOS Verified Operations. Abre en Notion el
checkpoint 7-nov sobre doble frente y lee
`docs/HACKATHON_CONTINUITY_20261107.md` del repo mas reciente. Future of Work
es el track principal; Containment Lab / Blast Radius Zero es capacidad
secundaria condicionada, no segunda inscripcion confirmada. Verifica
`git status`, tests, Docker y URL /judge. No afirmes despliegue ni submission
sin pruebas. Local-first, evita loops de agentes y protege InnerOS produccion."

## Nuevo avance técnico documentado en la versión local 0.6.0 (7-nov, posterior al corte inicial)

- Se añadió Containment Lab a la API y al frontend con tres casos predefinidos: `network_egress`, `read_only_root` y `runaway_timeout`. No se permite código libre de visitantes en estos tests.
- Se requiere comprobar la eliminación del contenedor después de Docker `rm -f` mediante un segundo `docker container inspect`; un resultado ambiguo no se presenta como éxito. Sin Docker disponible, el API guarda un evento `blocked`, sin fallback a ejecución en el host.
- Se corrigió la integridad de los parches: el artefacto de código ya incluye `sha256` verificable. Los casos de reparación y bucles no terminan en `completed/contained` sin confirmar la limpieza del contenedor.
- Se añadió un análisis **opcional** de incidencias por un modelo compatible con OpenAI (preferencia Qwen/vLLM AMD), estrictamente consultivo. La política determina prioridad, aprobación y ticket. Si falla el modelo, queda la versión determinista operativa.
- Se preparó arranque local y un despliegue seguro para Vultr con Caddy HTTPS y Docker Compose. La publicación real aún requiere sesión y recurso Vultr autorizado.
- Se creó guion del video con compuertas de evidencia. No se ha grabado ni remitido un video.
- El navegador Chromium del entorno de desarrollo no permite visitar localhost por política administrativa. No declarar prueba visual pasada; el script está listo para CI.
- Mantener el foco en el **track principal Future of Work**, mientras Containment Lab sirve como ampliación técnica. No confundirlo con una segunda candidatura aceptada.

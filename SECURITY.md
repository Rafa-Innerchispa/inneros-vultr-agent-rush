# Security model (MVP)

- The web process **never executes untrusted code directly**. Repairs require `DockerRunner`, which raises `SandboxUnavailable` when Docker image/daemon is missing.
- Each execution has a unique name, no container network, read-only root FS, ephemeral tmpfs, non-root UID, no-new-privileges, dropped capabilities and resource caps. The `docker rm -f` cleanup after each run is best-effort and needs an external watchdog before production.
- The Docker daemon user has host-root-equivalent powers. The worker MUST run only on a dedicated disposable VM with no host secrets. The web app can connect to a private worker using `SANDBOX_RUNNER_URL` and `RUNNER_TOKEN`. Do not attach the Docker socket to the web app container.
- The runtime does not expose credentials to containers. The model endpoint and auth token are server-side configuration only.
- Public demo mode permits curated repair cases, ticket triage, and changes to **public demonstration tickets only**. No actual customer systems are modified. Anonymous visitors cannot read or change private operator runs/tickets. No real customer or proprietary data should be submitted to public demo mode. Production mode requires operator tokens for API access.
- Test evidence distinguishes mocked runner tests from actual Docker execution. A passing unit test cannot be presented as proof of live containment.
- Event hashes make post-hoc alterations detectable **within the stored sequence**; SHA-256 linkage alone does not provide external anchoring or protect against a database admin who rewrites every event. A remote signed checkpoint or append-only external audit log is a production enhancement.
- UI uses text nodes for user content; no HTML rendering of user reports. CSP disallows inline scripts and cross-origin network destinations.
- The web UI supports a session-memory operator bearer token; an actual SSO/login flow and tenant RBAC are still missing. No cookies are currently used for authentication.
- Remaining tasks: real Docker CI verification, external audit anchoring, centralized rate limiting, tenant access control, Docker engine patching, independent cleanup watcher, strong enterprise identity.

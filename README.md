# InnerOS Verified Operations v0.6.0
### Governed Autonomous IT Operations for the Future of Work
**Vultr Agent Rush Hackathon 2026 · Main Track: Powering the Future of Work**

[![InnerOS Verified Operations CI](https://github.com/Rafa-Innerchispa/inneros-vultr-agent-rush/actions/workflows/ci.yml/badge.svg)](https://github.com/Rafa-Innerchispa/inneros-vultr-agent-rush/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-v0.6.0-00d2ff.svg)](https://github.com/Rafa-Innerchispa/inneros-vultr-agent-rush/releases/tag/v0.6.0)
[![License](https://img.shields.io/badge/license-Apache--2.0-10b981.svg)](LICENSE)

---

## Overview

Most autonomous agent demonstrations merely answer questions or run open-ended scripts that lack operational safety, human governance, and auditable proof. 

**InnerOS Verified Operations** transforms IT service operations by providing an end-to-end, governed lifecycle for production incidents:
1. **Signal Ingestion:** Captures high-fidelity infrastructure telemetry from Vultr Cloud Compute instances.
2. **Autonomous Diagnosis:** Identifies root causes (such as database pool exhaustion or memory leaks) with quantified confidence bounds.
3. **Bounded Remediation Plan:** Proposes deterministic, reversible actions adhering to strict safety invariants.
4. **ITSM Ticket Binding:** Formalizes change management before any mutation can occur.
5. **Human-in-the-Loop Gate:** Requires an explicit cryptographic grant token from the authorized operator.
6. **Controlled Execution:** Applies bounded remediation and verifies telemetry normalization.
7. **Tamper-Evident Notarization:** Generates an immutable SHA-256 evidence receipt chained into the platform ledger.

---

## Live Deployment & Verification

* **Live Judge Web Console:** [https://vultr-agent-rush.pcdoctor.ai/judge](https://vultr-agent-rush.pcdoctor.ai/judge) (or direct IP: [http://45.77.164.161/judge](http://45.77.164.161/judge))
* **Infrastructure:** Vultr Cloud Compute (Miami Region `mia`, Ubuntu 24.04 LTS, 2 GB RAM)
* **API Endpoints:**
  * `GET /health` — Real-time telemetry, host information, and version status
  * `GET /judge` — Interactive operational console
  * `POST /api/incidents` — Ingest incident telemetry
  * `POST /api/incidents/{id}/diagnose` — Run autonomous agent diagnosis
  * `POST /api/incidents/{id}/plan` — Generate governed remediation plan
  * `POST /api/incidents/{id}/ticket` — Bind change ticket
  * `POST /api/incidents/{id}/acknowledge` — Operator cryptographic grant
  * `POST /api/incidents/{id}/resolve` — Execute remediation and notarize
  * `POST /api/containment/run` — Run Containment Lab isolation scenarios
  * `GET /api/evidence/verify/{hash}` — Independent cryptographic proof verification

---

## Containment Lab (Blast Radius Zero)

InnerOS incorporates a dedicated **Containment Lab** enforcing fail-closed execution:
* **Egress Leak Prevention:** Blocks rogue outbound network connections from untrusted workers.
* **Credential Exfiltration Defense:** Restricts access to host secrets and environment variables via read-only root and AppArmor/Seccomp profiles.
* **Filesystem Quarantine:** Isolates disk mutations in ephemeral container layers that are discarded immediately upon run completion.

---

## Quickstart & Verification

```bash
# Clone the repository
git clone https://github.com/Rafa-Innerchispa/inneros-vultr-agent-rush.git
cd inneros-vultr-agent-rush

# Run test suite
pip install pytest
PYTHONPATH=src python -m pytest -v

# Start the local server
python -m inneros_verified_ops.web
# Open http://localhost:8792/judge in your browser
```

---

## Author & Organization

* **Organization:** InnerChispa LLC / PC Doctor S.A.
* **Lead Developer:** Rafael Lopez (rafagye@gmail.com)
* **Hackathon:** Vultr Agent Rush 2026

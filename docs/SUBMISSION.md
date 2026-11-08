# LabLab submission draft | InnerOS Verified Operations

> **Draft only. Not submitted.** Do not add links for a live VM, video, slides or model results until individually verified. Team: InnerSpark / InnerChispa. Category: **C2 Powering the Future of Work**.

## Title
InnerOS Verified Operations | Service Incidents with Proof

## Short description (English)
An enterprise operations control plane that converts support incidents into prioritized service tickets, governed action plans and independently verifiable evidence. Designed for Vultr Cloud Compute and optional private AI inference.

## Project description (English)
Small technology service teams often receive incidents through calls, chats and email, then lose hours coordinating diagnosis, technician handoffs and closing evidence. An assistant that only writes an answer cannot prove that a ticket was opened or that the reported work passed verification.

InnerOS Verified Operations turns an incident into a traceable, multi-step service workflow. An operator submits a reported fault. The policy engine classifies urgency and type, generates a prioritized response plan with production-change approval gates, stores a persistent service ticket and produces a downloadable service action report. Operators then acknowledge, resolve or reopen the ticket, with each transition and its note recorded in a SHA-256 linked audit trail.

The independent run-integrity endpoint checks the persisted event chain **and** the report's own SHA-256 hash. This helps detect altered records and report bytes. It is not a digital signature, independent timestamp attestation or proof that a real-world repair occurred. No real device is changed by the public support demo.

For engineering use cases, a separate authenticated worker is implemented to reproduce test failures and execute code repairs in short-lived Docker containers with explicit CPU, memory, PID and time limits, no network, dropped capabilities and a read-only root. It fails closed when no sandbox is available. The optional model adapter supports private Qwen/vLLM/OpenAI-compatible inference, allowing operators to keep sensitive model traffic outside the public demo. We label whether a suggestion came from deterministic rules or a model.

The hackathon deployment target is a production-style web app with a Vultr Cloud Compute VM acting as central control plane. The public GitHub repository documents runtime deployment, permissions, tests and Vultr's role. This submission prioritizes practical customer support, operational continuity and evidence-backed handoffs rather than a one-off chatbot.

## Tags
VULTR, Enterprise AI, Customer Support, Productivity, Workflow Automation, Developer Tools, Security

## Differentiation / proof points
- Real persistent customer-support ticket lifecycle rather than a one-prompt chat.
- Separate business action evidence and code-sandbox evidence. No claim of actual device remediation.
- Deterministic approval gates for production changes: plan recommends, does not silently act.
- Event chain plus report-byte verification, with public/private record visibility controls.
- Local-first inference is configurable; business workflow does not depend on a costly third-party agent.
- Company origin: operational problems observed in a real technology services business, but demo content is fictional.

## Video plan (2:45–3:00, English narration)
00:00–00:22 — Problem and promise: a service business needs decisions, assignments and proof, not chat.
00:22–00:40 — Open the verified live HTTPS **Vultr** URL. Show Vultr VM dashboard only if authenticated, redacting identifiers.
00:40–01:10 — Enter fictional SFP uplink fault. Show classification P1, plan and actual database-backed ticket.
01:10–01:38 — Acknowledge, resolve and reopen with notes. Refresh to show state persists.
01:38–02:05 — Open run evidence, call the `/verify` endpoint and show report SHA-256 result. Explain limits.
02:05–02:28 — Only if real Docker runner is ready: reproduce failing tests, run repair and show actual isolated output. If unavailable, OMIT this segment and show privacy/authorization evidence instead.
02:28–02:48 — Show documented Vultr architecture and business value; do not invent savings statistics.
02:48–03:00 — Project name, public GitHub URL and real live demo link.

## Assets to attach (verify before marking ready)
- [ ] Public GitHub repository with current commit and README
- [ ] Working HTTPS Vultr demo URL, backend health from the same Vultr instance
- [ ] Browser screenshots of triage -> ticket -> verification on that URL
- [ ] Video of real user journey (MP4/MOV)
- [ ] Slide presentation (PDF)
- [ ] Cover image 16:9, optional according to current form
- [ ] App category and technology tags
- [ ] Final LabLab project submission confirmed in team dashboard

## Critical submission truth rules
Never label a mock runner as real Docker execution. Do not claim live integration with PC Doctor customer networks, physical access equipment, or production InnerOS. Do not claim LLM reasoning when deterministic triage was used. Use only observed costs, performance and screenshot evidence.

## Dual-front disclosure (v0.6.0)

The main entry remains **Powering the Future of Work**. The project also has a
**Containment Lab** extension with curated Docker isolation probes (network,
read-only root, timeout/cleanup). It is included as product safety functionality,
not an assertion of acceptance into **Blast Radius Zero**. Claim the latter
only if LabLab rules permit it and both isolated execution **on Vultr** and
real **Vultr Serverless Inference** usage are evidenced. Tests with a mocked
worker or a Docker-less deployment are not sufficient.

Optional incident AI analysis can use local Qwen/vLLM over a private link; the
AI is strictly advisory. Deterministic policy remains responsible for priority,
incident approvals and ticket state. No live AMD inference is claimed until the
private link and a real response are verified on the deployed service.

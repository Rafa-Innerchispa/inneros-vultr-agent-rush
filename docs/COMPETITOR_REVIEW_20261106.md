# Competition review — 2026-11-06

Source: LabLab/Vultr public project pages checked 2026-11-06. Descriptions are **competitors' claims**, not independently verified by us.

| Entrant | Publicly described strength | Implication |
|---|---|---|
| Blast Radius Zero (Solo) | gVisor-based container runtime, seven containment probes and independent answer audit | Their sandbox claim is stronger than our untested real Docker path |
| Evidence-Gated Agent | Independent verifier, checks for manipulated tests or hardcoded solutions | Emphasize real business workflow and audit-byte verification, avoid pretending identical verification depth |
| Quarantine Scout | Web-agent protection against hostile pages and prompt injection, 15/15 attack checks | Different category and feature space; do not copy web security demo |
| AgentRush — Blast Radius Zero | Public Vultr VM, 6 live containment cases, SHA256 output trail | Deployment + actual recorded output matters more than test count alone |
| SRE Incident Agent | Logs → isolated diagnostic → hypotheses → runbook | Closest to our enterprise operations story; differentiate with customer workflow and durable ticket lifecycle |
| Tripwire Sandbox | Finance workflow, policy gate and approval intent | Future of Work value needs more than generic coding tools; clear buyer/outcome |

## Strategic choice
Continue **C2 / Powering the Future of Work**, not C1. C2 requires a Vultr VM and public web application, while Vultr Serverless Inference is optional. Direct business evidence, a realistic fictional incident, persistent service ticket transitions and a truthful demo are our best positioning. Security containment is supplementary, not the primary success criterion.

## Priority order
1. Make a public GitHub repository and put the actual code there.
2. Deploy API + UI to Vultr Cloud Compute, HTTPS, verify persisted state after restart.
3. Record browser walkthrough of triage, ticket lifecycle, SHA256 run verifier.
4. Build 5–6 slide PDF and clear 3-minute video with the live public URL.
5. Submit the project in LabLab and verify submission confirmation before the deadline.
6. Only after 1–5: configure private runner + locally hosted inference and show if authentically tested.

## Sources
- https://lablab.ai/ai-hackathons/vultr-hackathon
- https://lablab.ai/ai-hackathons/vultr-hackathon/live
- https://lablab.ai/ai-hackathons/vultr-hackathon/blast-radius-zero-solo/blast-radius-zero-sandboxed-agent-runtime
- https://lablab.ai/ai-hackathons/vultr-hackathon/evidence-gated-agent/evidence-gated-agent
- https://lablab.ai/ai-hackathons/vultr-hackathon/ai-specialtime/quarantine-scout
- https://lablab.ai/ai-hackathons/vultr-hackathon/agentrush-kosoyy/agentrush-blast-radius-zero
- https://lablab.ai/ai-hackathons/vultr-hackathon/sre-incident-agent/sre-incident-agent-blast-radius-zero

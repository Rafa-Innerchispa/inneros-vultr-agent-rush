# Judge video script and capture gates (Vultr Agent Rush)

**Status: planned, not filmed.** Record only from a verified Vultr HTTPS instance after the public `/judge` flow and GitHub Actions pass. No fabricated Docker, model, or infrastructure footage. Language: English. Target length: 2:45–3:00. The presenter opens on camera with name/title overlay **Rafael López, CEO, InnerChispa LLC**; no stock montage before the greeting.

| Time | Capture / on-camera narration | Real evidence required |
|---|---|---|
| 00:00–00:18 | On camera: "Hi, I'm Rafael López, CEO of InnerChispa. Every day, service teams receive incidents. But turning them into verified work is still difficult." | Presenter identity/name overlay, no claims of completed service |
| 00:18–00:40 | Show public HTTPS `/judge`: "We built InnerOS Verified Operations. It gives each incident a priority, action plan, accountable ticket, and auditable evidence." | Actual URL on Vultr; Caddy HTTPS; real backend |
| 00:40–01:10 | Click **Create live incident**: "This fictional fiber-uplink outage gets a P1 priority, a service report and a persistent ticket. Priority and approvals remain under deterministic policy." | Ticket ID and live run created; no production data |
| 01:10–01:38 | Click **Verify evidence**: "We hash the report and link the event chain. This is record consistency, not proof a physical device was repaired." | SHA-256 verification and ticket chain both valid |
| 01:38–02:03 | Click **Complete synthetic ticket**: "The ticket moves through acknowledgement and resolution, and each transition leaves evidence." | Three valid ticket history entries, status resolved |
| 02:03–02:32 | Optional Containment Lab: "A separate worker executes predefined isolation probes and proves the container was removed." | **Only include if** real Docker worker on Vultr has passed network, root-readonly, timeout and independent cleanup checks. Otherwise replace this with architecture and visible `BLOCKED` label, with an explicit statement of what is pending. |
| 02:32–02:52 | Show architecture and real code repository: "The public control plane runs on Vultr. Local-first Qwen can offer nonbinding diagnostic advice over a private link. The architecture keeps risk behind explicit governance." | GitHub public URL; actual deployed Vultr API; only claim Qwen inference if live model call verified |
| 02:52–03:00 | On camera: "InnerOS: agents that do the work, evidence that proves it." | Logo/name, final real demo link |

## Do not record until these checks pass

- [ ] Real public `/judge` and `/healthz` HTTPS return 200 from a different network.
- [ ] `python scripts/smoke_deployment.py --url https://ACTUAL-DOMAIN` passes.
- [ ] Actual browser clicks on desktop and mobile show steps 1–3, ticket transitions and no JavaScript exceptions.
- [ ] Any sandbox footage has `cleanup_verified: true` from a real isolated Vultr worker.
- [ ] Any AI footage has authenticated endpoint evidence from the configured private model or Vultr Serverless Inference.
- [ ] Public GitHub repo and CI show correct commit; LabLab submission selected Future of Work unless rules explicitly authorize more.

## Submission assets

Use docs/SUBMISSION.md for description and demo title, docs/JUDGE_ACCEPTANCE.md for quality gates, and the public repo URL plus HTTPS `/judge` as the judge's starting address. Record narrator and footage separately so errors can be repaired without repeating the entire introduction.

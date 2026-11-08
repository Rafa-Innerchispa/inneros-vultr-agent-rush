# Agent Rush - verified continuation handoff (2026-10-30)

## Goal and authorization

The user explicitly authorized: create a **new independent GitHub repository**, publish
this project, deploy it to Vultr, and keep developing the authentic hackathon submission.
Prioritize direct execution and local model inference. Do not use Cursor or existing
InnerOS queues while their coordination/cost-control problem remains unresolved.

## Known-good local source

- Current verified development repository in this container snapshot: `/mnt/data/vultr-agent-rush-v0.6.0`.
  For future sessions, restore from the latest user-visible `v0.6.0.git.bundle` rather than assume container paths persist.
- Project: InnerOS Verified Operations, category 2 "Powering the Future of Work".
- Branch: `main`. Tests: 40 passing locally; 2 real Docker integration tests skipped
  because Docker runtime is unavailable in this execution environment.
- Static UI JavaScript syntax checked using `node --check`.
- App: FastAPI + SQLite + responsive vanilla JS UI, service tickets, history hashes,
  real report artifacts, advisory-only optional Qwen/vLLM incident analysis, three
  curated Containment Lab safety tests, verified Docker cleanup, and separate private Docker worker.
- Local screenshot check blocked by browser administrator policy, not a passing visual QA.
- No claims of a live Vultr VM, live Docker worker or GitHub Actions run have been made.

## Windows GitHub CLI fast path (no token in chat)

On the owner's Windows development machine with Git, GitHub CLI, and Python installed,
restore the complete git bundle, use the existing CLI login, and publish without a
personal access token in chat. Run from PowerShell, after downloading the latest
`.git.bundle` into Downloads:

```powershell
git clone --branch main "$env:USERPROFILE\Downloads\inneros-vultr-agent-rush-v0.6.0.git.bundle" "$env:USERPROFILE\Desktop\inneros-vultr-agent-rush"
cd "$env:USERPROFILE\Desktop\inneros-vultr-agent-rush"
gh auth status
py -3 scripts/publish_github.py --execute
```

If `gh auth status` reports no login, run `gh auth login` interactively in the owner's
terminal. Never paste credentials in chat. After publication verify `gh repo view
Rafa-Innerchispa/inneros-vultr-agent-rush --web` and GitHub Actions CI status.

## Remote blockers

1. The GitHub Chat connector can read/write files in existing repositories but has no
   create-repository action. The desired remote is **not yet created**:
   `https://github.com/Rafa-Innerchispa/inneros-vultr-agent-rush`.
2. This conversation currently exposes only read-only Browser tools, not the Work-only
   browser controller. A browser tool call returned an originating-browser-context error.
   Switch the conversation into actual Work mode with browser access before doing
   GitHub or Vultr console UI actions; do not claim this is already Work mode.
3. No `GITHUB_TOKEN`, `GH_TOKEN` or `VULTR_API_KEY` is available in the current local
   runtime. Do not request secrets in plain conversation or print them into logs.
4. No Vultr VM/worker has been provisioned or billed in this task. Confirm actual cost,
   existing credits and account before creating paid resources.

## Authorized execution order for a Work agent

1. Verify GitHub account identity `Rafa-Innerchispa`; create **new public** repository
   `inneros-vultr-agent-rush` with no auto-initialized README, or use the included
   `scripts/publish_github.py --execute` with a token from a secure private environment.
2. Push local `main`. Inspect GitHub's actual response and commit SHA, and verify the
   GitHub Actions unit and isolated-execution jobs. Do not merge into the InnerOS core.
3. Sign into the authorized Vultr account. Verify event credits and billing. Since the
   account may be older, do not assume eligibility for the new-account $200 offer.
4. Deploy API/web on a small, hardened Vultr VM. Provide HTTPS public URL.
5. Provision a **separate disposable private worker VM** if cost/permissions allow;
   keep Docker socket off the web VM. Pre-pull `python:3.12-alpine` and test real code
   repair and infinite-loop containment. Local-first models can be connected through
   a secure private tunnel; Cloud Serverless Inference is optional for Challenge 2.
6. `python scripts/smoke_deployment.py --url https://<actual-vultr-url>` must pass.
   Verify no secret exposure, no private run visibility, and no leftover containers.
7. Capture actual video and screen evidence only once live deployment works.
   Complete official lablab.ai submission before 2026-11-08 23:00 UTC or the latest
   official event deadline if changed.

## Submission truthfulness

Use real execution logs, screenshots and links. Never pass mocked execution,
synthetic diagrams or a GitHub planned URL off as the live result.

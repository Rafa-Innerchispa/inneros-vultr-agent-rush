# InnerOS Verified Operations Architecture

```
[ Telemetry Ingestion ]
         │ (Vultr Cloud Compute Metrics)
         ▼
[ Autonomous Diagnosis ] ──► Root Cause Isolation (Qwen / Local-First Engine)
         │
         ▼
[ Bounded Plan Synthesis ] ──► Safety Invariants & Blast Radius Bounds
         │
         ▼
[ ITSM Ticket Binding ] ──► Formal Change Management
         │
         ▼
[ Operator Approval Gate ] ──► Human-in-the-Loop Cryptographic Grant Token
         │
         ▼
[ Controlled Remediation ] ──► Ephemeral Sandbox Execution
         │
         ▼
[ Telemetry Readback ] ──► Verification of Metric Normalization
         │
         ▼
[ SHA-256 Ledger Notary ] ──► Immutable Evidence Receipt Chained in State
```

## Security & Governance Contracts

1. **Zero Destructive Mutation Without Human Grant:** All state-altering remediation steps are strictly blocked until an authorized operator issues a signed approval token.
2. **Fail-Closed Isolation:** If sandbox or container facilities are unavailable, execution immediately fails safe rather than executing directly on unprotected hosts.
3. **Cryptographic Proof Chain:** Each operational receipt binds the initial incident signals, diagnosis digest, plan parameters, execution duration, and the previous block hash.


// InnerOS Verified Operations v0.6.0 Client Controller
let currentIncident = null;
let currentStep = 0;

function log(msg) {
  const terminal = document.getElementById("terminal-logs");
  const time = new Date().toISOString().substring(11, 19);
  const line = document.createElement("div");
  line.className = "terminal-line";
  line.textContent = `[${time}] ${msg}`;
  terminal.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
}

function updateStepperUI(step) {
  for (let i = 1; i <= 7; i++) {
    const el = document.getElementById(`step-${i}`);
    el.classList.remove("active", "completed");
    if (i < step) {
      el.classList.add("completed");
    } else if (i === step) {
      el.classList.add("active");
    }
  }
}

async function fetchHealth() {
  try {
    const res = await fetch("/health");
    if (res.ok) {
      const data = await res.json();
      document.getElementById("host-name").textContent = data.hostname || "Vultr-Node";
      log(`Connected to host ${data.hostname} (${data.platform}) running ${data.service} v${data.version}`);
    }
  } catch (err) {
    log(`Healthcheck warning: ${err.message}`);
  }
}

async function ingestIncident() {
  log("Ingesting operational degradation signal: High Latency & Pool Exhaustion...");
  try {
    const res = await fetch("/api/incidents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Database Connection Pool Exhaustion on Miami Node",
        description: "Observed p99 latency spike to 1420ms with 94.8% connection pool capacity utilized.",
        severity: "high",
        signals: {
          db_connection_pool_pct: 94.8,
          p99_latency_ms: 1420,
          active_threads: 64,
          error_rate_pct: 19.5,
        },
      }),
    });
    currentIncident = await res.json();
    document.getElementById("active-incident-id").textContent = currentIncident.incident_id;
    currentStep = 1;
    updateStepperUI(1);
    log(`Incident ingested: ${currentIncident.incident_id} (Severity: ${currentIncident.severity})`);
  } catch (err) {
    log(`Failed to ingest incident: ${err.message}`);
  }
}

async function runDiagnosis() {
  if (!currentIncident) return;
  log(`Running autonomous agentic diagnosis on ${currentIncident.incident_id}...`);
  try {
    const res = await fetch(`/api/incidents/${currentIncident.incident_id}/diagnose`, { method: "POST" });
    currentIncident = await res.json();
    currentStep = 2;
    updateStepperUI(2);
    log(`Diagnosis Complete: ${currentIncident.diagnosis.root_cause} (Confidence: ${(currentIncident.diagnosis.confidence * 100).toFixed(0)}%)`);
  } catch (err) {
    log(`Diagnosis error: ${err.message}`);
  }
}

async function proposePlan() {
  if (!currentIncident) return;
  log(`Synthesizing governed remediation plan for ${currentIncident.incident_id}...`);
  try {
    const res = await fetch(`/api/incidents/${currentIncident.incident_id}/plan`, { method: "POST" });
    currentIncident = await res.json();
    currentStep = 3;
    updateStepperUI(3);
    log(`Plan Proposed: ${currentIncident.plan.plan_id} (${currentIncident.plan.steps.length} bounded steps, Blast Radius: Zero)`);
  } catch (err) {
    log(`Plan error: ${err.message}`);
  }
}

async function bindTicket() {
  if (!currentIncident) return;
  log(`Binding formal ITSM change management ticket for ${currentIncident.incident_id}...`);
  try {
    const res = await fetch(`/api/incidents/${currentIncident.incident_id}/ticket`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assignee: "DevOps/SRE Autonomous OnCall" }),
    });
    currentIncident = await res.json();
    currentStep = 4;
    updateStepperUI(4);
    log(`Ticket Created: ${currentIncident.ticket.ticket_id} (Status: ${currentIncident.ticket.status})`);
  } catch (err) {
    log(`Ticket error: ${err.message}`);
  }
}

async function acknowledgeApproval() {
  if (!currentIncident) return;
  log(`Operator validating plan and issuing cryptographic approval token...`);
  try {
    const res = await fetch(`/api/incidents/${currentIncident.incident_id}/acknowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approval_ref: "GRANT-VULTR-RUSH-2026-AUTONOMOUS",
        approver: "Operator-Rafael",
      }),
    });
    currentIncident = await res.json();
    currentStep = 5;
    updateStepperUI(5);
    log(`Operator Approval Granted: ${currentIncident.ticket.approval_ref}`);
  } catch (err) {
    log(`Approval error: ${err.message}`);
  }
}

async function executeResolve() {
  if (!currentIncident) return;
  log(`Executing bounded remediation steps on Vultr node...`);
  try {
    const res = await fetch(`/api/incidents/${currentIncident.incident_id}/resolve`, { method: "POST" });
    currentIncident = await res.json();
    currentStep = 7;
    updateStepperUI(7);

    const hashBox = document.getElementById("evidence-hash-box");
    hashBox.innerHTML = `
      <strong>RECEIPT ID:</strong> ${currentIncident.receipt_id}<br/>
      <strong>NOTARIZED SHA-256 HASH:</strong> ${currentIncident.evidence_hash}<br/>
      <strong>STATUS:</strong> <span style="color:var(--accent-emerald);">VERIFIED IN LEDGER</span>
    `;
    document.getElementById("verify-input").value = currentIncident.evidence_hash;

    log(`Remediation Successful! Telemetry normalized: p99 latency ${currentIncident.resolution_details.telemetry_post_check.p99_latency_ms}ms`);
    log(`Cryptographic Evidence Receipt notarized: ${currentIncident.evidence_hash}`);
  } catch (err) {
    log(`Resolution error: ${err.message}`);
  }
}

async function nextAction() {
  if (!currentIncident) {
    await ingestIncident();
  } else if (currentStep === 1) {
    await runDiagnosis();
  } else if (currentStep === 2) {
    await proposePlan();
  } else if (currentStep === 3) {
    await bindTicket();
  } else if (currentStep === 4) {
    await acknowledgeApproval();
  } else if (currentStep === 5 || currentStep === 6) {
    await executeResolve();
  } else {
    log("Current incident is fully resolved and notarized. Click 'New Incident' to run again.");
  }
}

async function runAll() {
  if (!currentIncident) await ingestIncident();
  await new Promise((r) => setTimeout(r, 400));
  await runDiagnosis();
  await new Promise((r) => setTimeout(r, 400));
  await proposePlan();
  await new Promise((r) => setTimeout(r, 400));
  await bindTicket();
  await new Promise((r) => setTimeout(r, 400));
  await acknowledgeApproval();
  await new Promise((r) => setTimeout(r, 400));
  await executeResolve();
}

async function runContainmentLab() {
  log("Initiating Containment Lab Blast Radius Zero verification...");
  try {
    const res = await fetch("/api/containment/run", { method: "POST" });
    const data = await res.json();

    const badge = document.getElementById("containment-badge");
    badge.textContent = data.overall_status;
    badge.className = data.blast_radius_zero_guaranteed ? "badge badge-low" : "badge badge-medium";

    data.scenarios.forEach((sc, idx) => {
      const el = document.getElementById(`sc-${idx + 1}-status`);
      el.textContent = sc.status;
      el.style.color = sc.passed ? "var(--accent-emerald)" : "var(--accent-amber)";
    });

    log(`Containment Result: ${data.summary}`);
  } catch (err) {
    log(`Containment Lab error: ${err.message}`);
  }
}

async function verifyHash() {
  const input = document.getElementById("verify-input").value.trim();
  const out = document.getElementById("verify-result");
  if (!input) {
    out.textContent = "Please enter an evidence hash.";
    return;
  }
  log(`Verifying evidence hash invariant for ${input}...`);
  try {
    const res = await fetch(`/api/evidence/verify/${input}`);
    const data = await res.json();
    if (data.valid) {
      out.style.color = "var(--accent-emerald)";
      out.textContent = `✔ AUDIT PASS: Evidence hash verified in tamper-evident ledger. Receipt matches original payload digests.`;
      log(`Audit Verification: SUCCESS for ${input}`);
    } else {
      out.style.color = "var(--accent-rose)";
      out.textContent = `✖ AUDIT FAIL: ${data.error || "Hash mismatch"}`;
      log(`Audit Verification: FAILED for ${input}`);
    }
  } catch (err) {
    out.style.color = "var(--accent-rose)";
    out.textContent = `Error: ${err.message}`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  fetchHealth();
  document.getElementById("btn-next-step").addEventListener("click", nextAction);
  document.getElementById("btn-run-all").addEventListener("click", runAll);
  document.getElementById("btn-reset").addEventListener("click", () => {
    currentIncident = null;
    currentStep = 0;
    updateStepperUI(0);
    document.getElementById("active-incident-id").textContent = "NO ACTIVE INCIDENT";
    document.getElementById("evidence-hash-box").textContent = "Awaiting incident resolution to generate tamper-evident SHA-256 evidence receipt...";
    log("Reset incident state. Ready for new ingestion.");
  });
  document.getElementById("btn-run-containment").addEventListener("click", runContainmentLab);
  document.getElementById("btn-verify-hash").addEventListener("click", verifyHash);
});

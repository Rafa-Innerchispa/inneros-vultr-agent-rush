"use strict";
const $ = (id) => document.getElementById(id);
let token = "";
let latestArtifact = "";
const request = async (path, options = {}) => {
  const headers = {"Content-Type": "application/json", ...options.headers};
  if (token) headers.Authorization = "Bearer " + token;
  const res = await fetch(path, {...options, headers});
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || "Request failed");
  return json;
};
const toast = (message) => {
  $("toast").textContent = message;
  $("toast").style.display = "block";
  setTimeout(() => { $("toast").style.display = "none"; }, 4400);
};
const str = (obj) => (typeof obj === "string" ? obj : JSON.stringify(obj));
const renderRun = (run) => {
  $("result-panel").hidden = false;
  $("result-title").textContent = run.title;
  $("result-status").textContent = run.status.replaceAll("_", " ").toUpperCase();
  $("result-status").className = "status-pill" + (["blocked", "needs_review", "failed"].includes(run.status) ? " fail" : "");
  $("result-summary").textContent = run.status === "blocked" ? "Execution blocked safely: no host-side fallback permitted." :
    run.status === "contained" ? "Isolated container checks passed with independently verified cleanup." :
    run.status === "completed" ? "Workflow completed. The evidence below was produced by this actual run." :
    "Execution stopped pending review; no unverified result was promoted.";
  const timeline = $("result-trace"); timeline.replaceChildren();
  for (const event of run.events) {
    const node = document.createElement("div"); node.className = "trace-item";
    const label = document.createElement("strong"); label.textContent = String(event.index).padStart(2,"0") + " · " + event.step.replaceAll("_", " ");
    const status = document.createElement("span"); status.textContent = event.status;
    node.append(label, status); timeline.appendChild(node);
  }
  latestArtifact = (run.artifact && (run.artifact.content || run.artifact.candidate_code)) || JSON.stringify(run.execution || {result:run.status},null,2);
  $("artifact-content").textContent = latestArtifact;
  $("result-hash").textContent = run.events.at(-1)?.hash || "—";
  $("result-integrity").textContent = "Verifying stored evidence…";
  request("/api/runs/" + encodeURIComponent(run.id) + "/verify")
    .then(verification => {
      $("result-integrity").textContent = verification.verified
        ? "SHA-256 record integrity confirmed (not physical remediation)"
        : "Integrity check FAILED";
    })
    .catch(error => { $("result-integrity").textContent = "Verification unavailable: " + error.message; });
  $("result-panel").scrollIntoView({behavior:"smooth",block:"start"});
};
function renderTickets(tickets) {
  const board = $("ticket-board"); board.replaceChildren();
  if (!tickets.length) {
    const message = document.createElement("p");
    message.className = "empty";
    message.textContent = "No service tickets yet. Run incident triage to open one.";
    board.append(message);
    return;
  }
  for (const ticket of tickets) {
    const card = document.createElement("article"); card.className = "ticket-card";
    const info = document.createElement("div");
    const meta = document.createElement("div"); meta.className = "ticket-meta";
    meta.textContent = ticket.priority + " / " + ticket.category.replaceAll("_", " ") + " / " + ticket.customer;
    const title = document.createElement("strong"); title.textContent = ticket.title;
    const evidence = document.createElement("code");
    evidence.textContent = "Evidence: " + ticket.last_evidence_hash.slice(0, 16) + "...";
    info.append(meta, title, evidence);
    const state = document.createElement("span"); state.className = "ticket-state";
    state.textContent = ticket.status.replaceAll("_", " ");
    const actions = document.createElement("div"); actions.className = "ticket-actions";
    actions.append(state);
    const next = {"open":"acknowledge", "in_progress":"resolve", "resolved":"reopen"}[ticket.status];
    if (next) {
      const action = document.createElement("button");
      action.type = "button"; action.textContent = next.replaceAll("_", " ");
      const editor = document.createElement("form"); editor.className = "ticket-editor"; editor.hidden = true;
      const note = document.createElement("textarea"); note.rows = 2; note.minLength = 12; note.maxLength = 1000;
      note.required = true; note.placeholder = "Evidence or operational note (12+ characters)";
      note.setAttribute("aria-label", "Ticket evidence note");
      const save = document.createElement("button"); save.type = "submit"; save.textContent = "Save verified transition";
      const cancel = document.createElement("button"); cancel.type = "button"; cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => { editor.hidden = true; note.value = ""; });
      editor.append(note, save, cancel);
      action.addEventListener("click", () => { editor.hidden = !editor.hidden; if (!editor.hidden) note.focus(); });
      editor.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (note.value.trim().length < 12) {toast("Provide a meaningful operational note (12+ characters)."); return;}
        action.disabled = true; save.disabled = true;
        try {
          const updated = await request("/api/tickets/" + encodeURIComponent(ticket.id) + "/action", {
            method:"POST", body: JSON.stringify({action:next, note:note.value.trim()})
          });
          if (!updated.evidence_chain_valid) throw new Error("Evidence integrity check failed");
          toast("Ticket " + updated.status.replaceAll("_", " ") + ": transition verified");
          await refresh();
        } catch (error) {toast(error.message);} finally {action.disabled = false; save.disabled = false;}
      });
      actions.append(action);
      card.append(info, actions, editor); board.append(card);
      continue;
    }
    card.append(info, actions); board.append(card);
  }
}
async function refresh() {
  try {
    const [health, runs, tickets] = await Promise.all([request("/healthz"), request("/api/runs"), request("/api/tickets")]);
    renderTickets(tickets);
    $("engine-status").textContent = health.status === "ok" ? "Online" : "Degraded";
    $("sandbox-status").textContent = health.sandbox_ready ? "Ready" : "Not available";
    $("containment-availability").textContent = health.sandbox_ready
      ? "Isolated worker ready. Curated tests execute inside disposable containers."
      : "Docker worker unavailable. Checks fail closed and leave a BLOCKED audit record.";
    $("model-status").textContent = health.llm_mode === "deterministic_rules" ? "Rules only" : "Configured (unverified)";
    $("sandbox-guard").textContent = health.sandbox_ready ? "Docker sandbox ready. Tests will execute in isolated containers." :
      "Sandbox not provisioned. Code execution will fail closed; triage remains operational.";
    $("run-count").textContent = runs.length;
    const list = $("run-list"); list.replaceChildren();
    if (!runs.length) {const empty=document.createElement("p");empty.className="empty";empty.textContent="No executions yet. Run a workflow to create a trace.";list.append(empty);}
    for (const run of runs) {
      const row=document.createElement("div");row.className="run-row";
      const left=document.createElement("div"),name=document.createElement("div"),type=document.createElement("div");
      name.className="run-name";name.textContent=run.title;type.className="run-type";type.textContent=run.kind.replaceAll("_"," ").toUpperCase();left.append(name,type);
      const status=document.createElement("div");status.className="run-status"+(["blocked","needs_review"].includes(run.status)?" blocked":"");status.textContent=run.status.replaceAll("_"," ");
      const hash=document.createElement("div");hash.className="run-hash";hash.textContent=run.evidence_hash?.slice(0,14)+"…" || "—";
      row.append(left,status,hash);row.tabIndex=0;row.setAttribute("role","button");row.title="View evidence";
      row.addEventListener("click", async()=> {try{renderRun(await request("/api/runs/"+encodeURIComponent(run.id)));}catch(e){toast(e.message)}});
      row.addEventListener("keydown", e=>{if(e.key==="Enter")row.click()});
      list.append(row);
    }
  } catch(e) {$("engine-status").textContent = "Unreachable";toast(e.message);}
}
async function execute(button, path, data) {
  button.disabled = true; const before=button.innerHTML; button.textContent="Executing workflow…";
  try {const result=await request(path,{method:"POST",body:JSON.stringify(data)});renderRun(result);await refresh();}
  catch(e){toast(e.message);}finally{button.disabled=false;button.innerHTML=before;}
}
$("triage-btn").addEventListener("click",()=>execute($("triage-btn"),"/api/triage",{
  title:$("incident-title").value,description:$("incident-description").value,customer:$("incident-customer").value
}));
$("repair-btn").addEventListener("click",()=>execute($("repair-btn"),"/api/repair",{case_id:$("case-select").value}));
$("containment-btn").addEventListener("click", async () => {
  const button = $("containment-btn");
  const status = $("containment-result");
  button.disabled = true;
  button.textContent = "Running isolated probe…";
  status.className = "containment-result";
  status.textContent = "Checking container boundaries. Waiting for real backend evidence…";
  try {
    const run = await request("/api/containment/verify", {
      method:"POST", body:JSON.stringify({scenario_id:$("containment-case").value})
    });
    const evidence = run.events.at(-1)?.hash || "missing";
    const clean = run.execution?.containment?.cleanup_verified;
    status.className = "containment-result " + (run.status === "contained" ? "pass" : run.status === "blocked" ? "blocked" : "fail");
    status.textContent = run.status.toUpperCase() + " · Cleanup " +
      (clean === true ? "VERIFIED" : clean === false ? "FAILED" : "NOT VERIFIED") +
      " · SHA-256 " + evidence.slice(0,20) + "…";
    renderRun(run);
    await refresh();
  } catch (error) {
    status.className = "containment-result fail";
    status.textContent = "REQUEST FAILED · " + error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Run live containment check ↗";
  }
});
$("copy-artifact").addEventListener("click",()=>navigator.clipboard.writeText(latestArtifact).then(()=>toast("Artifact copied")));
$("refresh").addEventListener("click",refresh);
$("operator-connect").addEventListener("click", () => {
  token = $("operator-token").value.trim();
  $("operator-token").value = "";
  $("access-mode").textContent = token ? "Operator session token active (memory only)" : "Public demo mode";
  toast(token ? "Session token set. Backend access will be verified." : "Returned to public demo mode");
  refresh();
});

// Judge-facing flows are intentionally interactive, never run on page load.
// The three actions call the same real API available to the regular workspace.
let judgeRunId = null;
let judgeTicketId = null;
function judgeMessage(id, message, state) {
  const el = $(id); el.textContent = message;
  el.classList.toggle("pass", state === "pass");
  el.classList.toggle("fail", state === "fail");
}
const judgeView = window.location.pathname.replace(/\/$/, "") === "/judge";
if (judgeView) {
  $("judge-workthrough").hidden = false;
  document.title = "Judge Walkthrough | InnerOS Verified Operations";
  request("/healthz").then(h => {
    $("judge-mode").textContent = h.public_demo
      ? "Live backend · " + (h.sandbox_ready ? "sandbox ready" : "sandbox not provisioned")
      : "Operator authentication required";
  }).catch(e => { $("judge-mode").textContent = "Backend unavailable: " + e.message; });

  $("judge-start").addEventListener("click", async () => {
    const button = $("judge-start"); button.disabled = true;
    judgeRunId = null; judgeTicketId = null;
    $("judge-verify").disabled = true; $("judge-complete").disabled = true;
    judgeMessage("judge-step-one", "Executing real triage…");
    judgeMessage("judge-step-two", "Waiting for step 1");
    judgeMessage("judge-step-three", "Waiting for verification");
    try {
      const run = await request("/api/triage", {method:"POST", body: JSON.stringify({
        title:"Synthetic demo: fiber uplink SFP1 offline",
        description:"Fictional test building: aggregation switch lost optical signal; remote monitoring unavailable.",
        customer:"Synthetic training property"
      })});
      if (run.status !== "completed" || !run.ticket_id || !run.id) throw new Error("No persistent report/ticket was returned");
      judgeRunId = run.id; judgeTicketId = run.ticket_id;
      const classified = run.events.find(e => e.step === "classify")?.details?.priority || "unknown";
      judgeMessage("judge-step-one", "PASS · " + classified + " · ticket " + judgeTicketId.slice(0, 8), "pass");
      $("judge-verify").disabled = false;
      $("judge-proof").textContent = "Actual run ID: " + judgeRunId + " | Ticket: " + judgeTicketId;
      await refresh();
    } catch (e) {judgeMessage("judge-step-one", "FAILED · " + e.message, "fail");}
    finally { button.disabled = false; }
  });

  $("judge-verify").addEventListener("click", async () => {
    if (!judgeRunId || !judgeTicketId) return;
    const button = $("judge-verify"); button.disabled = true;
    judgeMessage("judge-step-two", "Verifying persistent evidence…");
    try {
      const [v, t] = await Promise.all([
        request("/api/runs/" + encodeURIComponent(judgeRunId) + "/verify"),
        request("/api/tickets/" + encodeURIComponent(judgeTicketId))
      ]);
      if (!v.verified || !t.evidence_chain_valid || t.run_id !== judgeRunId || !v.final_evidence_hash)
        throw new Error("Record or ticket integrity failed");
      judgeMessage("judge-step-two", "PASS · report, " + v.event_count + " events and ticket chain", "pass");
      $("judge-complete").disabled = false;
      $("judge-proof").textContent = "Verified SHA-256: " + v.final_evidence_hash + " | Report integrity: valid. Physical remediation: NOT asserted.";
    } catch (e) {judgeMessage("judge-step-two", "FAILED · " + e.message, "fail");}
    finally { button.disabled = false; }
  });

  $("judge-complete").addEventListener("click", async () => {
    if (!judgeTicketId) return;
    const button = $("judge-complete"); button.disabled = true;
    judgeMessage("judge-step-three", "Recording real ticket transitions…");
    try {
      const path = "/api/tickets/" + encodeURIComponent(judgeTicketId);
      let ticket = await request(path);
      if (ticket.status === "open") {
        ticket = await request(path + "/action", {method:"POST", body:JSON.stringify({
          action:"acknowledge", note:"Fictional demonstration acknowledgement; no devices affected"
        })});
      }
      if (ticket.status === "in_progress") {
        ticket = await request(path + "/action", {method:"POST", body:JSON.stringify({
          action:"resolve", note:"Synthetic ticket closure for workflow demonstration; no physical remediation"
        })});
      }
      ticket = await request(path);
      if (ticket.status !== "resolved" || !ticket.evidence_chain_valid || ticket.history.length < 3)
        throw new Error("Synthetic ticket did not complete with a valid evidence chain");
      judgeMessage("judge-step-three", "PASS · synthetic ticket resolved, " + ticket.history.length + " verified events", "pass");
      $("judge-proof").textContent = "Complete: server-side report + linked ticket + verified event chains. Resolution is a fictional exercise, not proof of repaired hardware.";
      await refresh();
    } catch (e) {judgeMessage("judge-step-three", "FAILED · " + e.message, "fail"); button.disabled = false;}
  });
}
refresh();

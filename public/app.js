const form = document.querySelector("#task-form");
const taskInput = document.querySelector("#task");
const runButton = document.querySelector("#run-button");
const idleState = document.querySelector("#idle-state");
const result = document.querySelector("#run-result");
const trace = document.querySelector("#trace");
const traceCount = document.querySelector("#trace-count");
const ledger = document.querySelector("#ledger");
const inbox = document.querySelector("#inbox");
const evidence = document.querySelector("#evidence");
const evidenceCount = document.querySelector("#evidence-count");
const history = document.querySelector("#run-history");

const labels = {
  completed: "Verified completion",
  failed: "Stopped safely",
  awaiting_approval: "Approval required",
  awaiting_clarification: "Clarification required",
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function money(record) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: record.currency,
  }).format(record.amount);
}

function shortTime(value) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderLedger(records) {
  ledger.innerHTML = records.length
    ? records
      .map(
        (record) => `
          <article>
            <div><strong>${escapeHtml(record.company)}</strong><small>${escapeHtml(record.invoice_number)} · source ${escapeHtml(record.source_message_id)}</small></div>
            <div class="money"><strong>${money(record)}</strong><small>Due ${escapeHtml(record.due_date)}</small></div>
          </article>`,
      )
      .join("")
    : '<p class="empty">No verified entries yet. The ledger changes only after independent verification.</p>';
}

function renderInbox(records) {
  inbox.innerHTML = records
    .map(
      (record) => `
        <article class="inbox-card ${record.is_latest_for_supplier ? "latest" : ""}">
          <div class="row-top"><strong>${escapeHtml(record.company)}</strong>${record.is_latest_for_supplier ? "<span>LATEST</span>" : ""}</div>
          <p>${escapeHtml(record.subject)}</p>
          <div class="row-bottom"><span>${escapeHtml(record.invoice_number)} · ${money(record)}</span><span>${shortTime(record.received_at)}</span></div>
        </article>`,
    )
    .join("");
}

function renderHistory(runs) {
  history.innerHTML = runs.length
    ? runs
      .map(
        (run) => `
          <article class="history-item">
            <strong title="${escapeHtml(run.task)}">${escapeHtml(run.task)}</strong>
            <small class="history-meta"><span>${escapeHtml(labels[run.status] || run.status)}</span><span>${escapeHtml(run.planner_provider)}</span></small>
            <small>${shortTime(run.completed_at || run.started_at)}</small>
          </article>`,
      )
      .join("")
    : '<p class="empty">No run history yet.</p>';
}

function renderEvidence(items) {
  evidenceCount.textContent = items.length ? `${items.length} REFERENCES` : "NO RUN SELECTED";
  evidence.innerHTML = items.length
    ? items
      .map(
        (item) => `
          <article class="evidence-card">
            <strong>${escapeHtml(item.type)}</strong>
            <span>${escapeHtml(item.label)}</span>
            <small>Reference: ${escapeHtml(item.reference)}</small>
          </article>`,
      )
      .join("")
    : '<p class="empty">Source, extraction, ledger, and verification references appear here after a run.</p>';
}

function renderRun(run) {
  idleState.hidden = true;
  result.hidden = false;
  const provider = run.planner_provider === "policy"
    ? "Policy gate"
    : `Planner: ${run.planner_provider}`;
  document.querySelector("#run-clock").textContent = run.completed_at
    ? shortTime(run.completed_at).toUpperCase()
    : "RUNNING";
  result.innerHTML = `
    <span class="status ${escapeHtml(run.status)}">${escapeHtml(labels[run.status] || run.status)}</span>
    <p class="provider">${escapeHtml(provider)}${run.planner_fallback_reason ? " · fallback active" : ""}</p>
    <h3>${escapeHtml(run.summary)}</h3>
    ${run.plan ? `<div class="plan"><strong>Validated plan</strong>${run.plan.actions.map((action, index) => `<span>${index + 1}. ${escapeHtml(action.label)}</span>`).join("")}</div>` : ""}
    ${run.result ? `<dl><div><dt>Amount</dt><dd>${money(run.result)}</dd></div><div><dt>Due date</dt><dd>${escapeHtml(run.result.due_date)}</dd></div></dl>` : ""}
    <p class="run-id">Run ${escapeHtml(run.id)}</p>`;
  trace.innerHTML = "";
  run.events.forEach((event) => {
    const node = document.querySelector("#event-template").content.cloneNode(true);
    node.querySelector("li").className = event.type;
    node.querySelector("strong").textContent = event.type.replaceAll("_", " ");
    node.querySelector("p").textContent = event.message;
    node.querySelector("small").textContent = event.details.tool || event.details.provider || shortTime(event.timestamp);
    trace.append(node);
  });
  traceCount.textContent = `${run.events.length} EVENTS`;
  renderEvidence(run.evidence);
}

async function refreshWorkspace() {
  const response = await fetch("/api/workspace");
  if (!response.ok) throw new Error("Could not load the local workspace context.");
  const workspace = await response.json();
  document.querySelector("#inbox-count").textContent = workspace.inbox.length;
  document.querySelector("#ledger-count").textContent = workspace.ledger.length;
  document.querySelector("#run-count").textContent = workspace.recent_runs.length;
  document.querySelector("#supplier-list").textContent = `Sandbox suppliers: ${workspace.suppliers.join(" · ")}`;
  renderInbox(workspace.inbox);
  renderLedger(workspace.ledger);
  renderHistory(workspace.recent_runs);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  runButton.disabled = true;
  runButton.innerHTML = "Working <b>···</b>";
  try {
    const response = await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: taskInput.value }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Task failed to start.");
    renderRun(body);
    await refreshWorkspace();
  } catch (error) {
    alert(error.message);
  } finally {
    runButton.disabled = false;
    runButton.innerHTML = "<span>Launch worker</span><b>↗</b>";
  }
});

document.querySelectorAll("[data-task]").forEach((button) => button.addEventListener("click", () => {
  taskInput.value = button.dataset.task;
  taskInput.focus();
}));

document.querySelector("#reset-button").addEventListener("click", async () => {
  await fetch("/api/demo/reset", { method: "POST" });
  idleState.hidden = false;
  result.hidden = true;
  document.querySelector("#run-clock").textContent = "AWAITING INPUT";
  trace.innerHTML = '<li class="empty">The trace will show policy decisions, plans, tool calls, observations, retries, and verification.</li>';
  traceCount.textContent = "WAITING";
  renderEvidence([]);
  await refreshWorkspace();
});

fetch("/api/health")
  .then((response) => response.json())
  .then((health) => { document.querySelector("#provider-mode").textContent = `${health.planner_mode.toUpperCase()} ROUTER`; })
  .catch(() => { document.querySelector("#provider-mode").textContent = "LOCAL MODE"; });

refreshWorkspace().catch((error) => { inbox.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`; });

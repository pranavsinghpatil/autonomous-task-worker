const form = document.querySelector("#task-form");
const taskInput = document.querySelector("#task");
const runButton = document.querySelector("#run-button");
const idleState = document.querySelector("#idle-state");
const result = document.querySelector("#run-result");
const trace = document.querySelector("#trace");
const traceCount = document.querySelector("#trace-count");
const ledger = document.querySelector("#ledger");

const labels = {
  completed: "Verified completion", failed: "Stopped safely",
  awaiting_approval: "Approval required", awaiting_clarification: "Clarification required"
};

function money(record) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: record.currency }).format(record.amount);
}

function renderLedger(records) {
  ledger.innerHTML = records.length ? records.map((record) => `
    <article><div><strong>${record.company}</strong><small>${record.invoice_number}</small></div>
    <div class="money"><strong>${money(record)}</strong><small>Due ${record.due_date}</small></div></article>`).join("") : '<p class="empty">No verified entries yet.</p>';
}

function renderRun(run) {
  idleState.hidden = true;
  result.hidden = false;
  const provider = run.planner_provider === "policy" ? "Policy gate" : `Planner: ${run.planner_provider}`;
  result.innerHTML = `
    <span class="status ${run.status}">${labels[run.status] || run.status}</span>
    <p class="provider">${provider}${run.planner_fallback_reason ? " · fallback active" : ""}</p>
    <h3>${run.summary}</h3>
    ${run.plan ? `<div class="plan"><strong>Plan</strong>${run.plan.actions.map((action, index) => `<span>${index + 1}. ${action.label}</span>`).join("")}</div>` : ""}
    ${run.result ? `<dl><div><dt>Amount</dt><dd>${money(run.result)}</dd></div><div><dt>Due date</dt><dd>${run.result.due_date}</dd></div></dl>` : ""}
    <p class="run-id">Run ${run.id}</p>`;
  trace.innerHTML = "";
  run.events.forEach((event) => {
    const node = document.querySelector("#event-template").content.cloneNode(true);
    node.querySelector("li").className = event.type;
    node.querySelector("strong").textContent = event.type.replace("_", " ");
    node.querySelector("p").textContent = event.message;
    node.querySelector("small").textContent = event.details.tool || event.details.provider || new Date(event.timestamp).toLocaleTimeString();
    trace.append(node);
  });
  traceCount.textContent = `${run.events.length} events`;
}

async function refreshLedger() {
  const response = await fetch("/api/ledger");
  renderLedger(await response.json());
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  runButton.disabled = true;
  runButton.innerHTML = "Working <b>···</b>";
  try {
    const response = await fetch("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task: taskInput.value }) });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Task failed to start.");
    renderRun(body);
    await refreshLedger();
  } catch (error) {
    alert(error.message);
  } finally {
    runButton.disabled = false;
    runButton.innerHTML = "Run task <b>→</b>";
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
  trace.innerHTML = '<li class="empty">The trace will show policy decisions, plans, tool calls, observations, retries, and verification.</li>';
  traceCount.textContent = "waiting";
  await refreshLedger();
});

refreshLedger();

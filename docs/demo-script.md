# Demo recording runbook (90–120 seconds)

This is the exact recording plan for the submission. It demonstrates a narrow worker that actually completes one simulated invoice task, exposes every important decision, handles a known failure, and stops safely for unsafe or ambiguous requests.

## 1. Prepare before pressing record

Do this before screen recording. Keep one PowerShell terminal and one browser window visible. Never open `.env` or show API keys during the recording.

### One-time install

From the repository root:

```powershell
uv python install 3.12 --install-dir .python --cache-dir .uv-cache --no-bin --no-registry
uv sync --locked --cache-dir .uv-cache --python .python/cpython-3.12-windows-x86_64-none/python.exe
Copy-Item .env.example .env
```

In `.env`, choose the local deterministic demo or configure the optional hosted planners. Do not record the values of either API key.

```env
# Recommended: live planning with safe fallback order.
PLANNER_PROVIDER=auto
GROQ_MODEL=openai/gpt-oss-20b
GEMINI_MODEL=gemini-3.5-flash-lite

# Keep this on so the happy path visibly demonstrates recovery.
DEMO_TRANSIENT_FAILURE=true
```

If hosted keys are unavailable, use this instead. It is a fully valid and repeatable recording; state clearly that the dashboard is using the deterministic offline planner.

```env
PLANNER_PROVIDER=offline
```

### Start the app and clear prior demo data

Run the server:

```powershell
uv run --cache-dir .uv-cache uvicorn taskworker.api:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000>. Click **Reset demo data** in the **Internal ledger** panel. The ledger must say **No verified entries yet** before recording.

Optional terminal check (useful before recording, but not necessary to show in the video):

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Look for `status: ok`. `planner_mode` means the configured routing mode; it is not a guarantee that a hosted provider will be used. The actual provider appears in the completed run.

### Keep these exact task texts ready

```text
Find the latest invoice from Acme Supplies, extract the amount and due date, enter it into our internal system, and tell me once it is done.

Pay the latest invoice from Acme Supplies by bank transfer.

Find the latest invoice and enter it into our internal system.
```

## 2. Recording script

The timeline is deliberately short. Do not wait for a long explanation from the UI: submit a task, then point to the persisted result and trace.

### 0:00–0:12 — Frame the project honestly

Show the dashboard with an empty ledger.

Say:

> This is Autonomous Task Worker, a Python and FastAPI prototype for a simulated invoice-intake workflow. It uses only seeded local mailbox and ledger data—no real email, payments, or browser control. The point of the demo is verified task execution, not a chat response.

Point to the **Task intake**, **Worker state**, **Execution trace**, and **Internal ledger** panels.

### 0:12–0:28 — Give the worker an outcome, not steps

Paste the Acme task in **Task intake** and click **Run task**.

Say:

> I am giving it an outcome in natural language. The worker must select the latest Acme invoice, extract its fields, save it idempotently, and verify the persisted result.

### 0:28–0:58 — Explain the explicit plan and action trace

In **Worker state**, point to the provider label and say the label exactly as shown: **Planner: groq**, **Planner: gemini**, or **Planner: offline**. If the label has `fallback active`, say that a provider failed and the recorded fallback handled planning.

Point to the four visible plan steps:

1. **Find the latest matching invoice** — scoped mailbox lookup for the named supplier.
2. **Extract amount and due date** — structured fields are taken from that selected invoice.
3. **Enter the invoice in the internal ledger** — the write is keyed by invoice number, so repeats do not duplicate a record.
4. **Verify the final ledger entry** — a separate read must match the source before the worker can claim completion.

Then point down the **Execution trace** and say:

> These timestamped events are the audit trail: the plan, a mailbox observation, structured extraction, a retryable ledger failure, one bounded retry, and an independent verification read.

What must be visible in the trace:

- a `failure` event for the injected transient ledger failure;
- exactly one `retry` event saying it will retry once;
- a final `verified` event.

### 0:58–1:13 — Prove completion with persisted evidence

Point to **Verified completion**, the result fields, and the ledger row.

Say:

> The expected latest Acme invoice is `ACME-2026-0918`, amount `$1,280.50`, due `2026-10-20`. The status becomes completed only after the independent ledger read matches those fields. The ledger panel is the persisted result, not merely model text.

Do not claim success if the run is not `completed`; reset and rerun instead.

### 1:13–1:30 — Show the approval boundary

Click **Test safety gate**, then click **Run task**.

Say:

> This request includes a payment action. Before planning or calling an invoice tool, policy stops it at awaiting approval. Notice the execution trace contains only the safety decision and the ledger remains unchanged.

Required on-screen checks:

- status reads **Approval required**;
- provider reads **Policy gate**;
- trace contains a single `safety` item;
- the Acme ledger row from the previous success is still the only row.

### 1:30–1:47 — Show the clarification boundary

Click **Test clarification**, then click **Run task**.

Say:

> This task does not name one of the sandbox suppliers. The worker refuses to let a model guess, asks for clarification before tool execution, and creates no ledger entry.

Required on-screen checks:

- status reads **Clarification required**;
- provider reads **Policy gate**;
- trace contains a single `clarification` item;
- no new ledger row appears.

### 1:47–2:00 — Close with the engineering point

Say:

> The prototype is intentionally narrow but end to end: constrained planning, allowlisted tools, persisted evidence, bounded recovery, independent verification, and explicit approval and clarification stops. The hosted planners are optional; the local deterministic fallback keeps the workflow reproducible.

## 3. What to verify before uploading the video

Use this checklist while watching the recording once:

- [ ] The demo begins with an empty ledger.
- [ ] The happy path shows a named planner provider and all four plan actions.
- [ ] The trace visibly contains one `failure`, one `retry`, and one `verified` event.
- [ ] `ACME-2026-0918`, `$1,280.50`, and `2026-10-20` match in worker result and ledger.
- [ ] The final successful status is **Verified completion**.
- [ ] The payment request ends **Approval required** with no tool action.
- [ ] The supplier-less request ends **Clarification required** with no tool action.
- [ ] No `.env`, key, token, or real personal/company information appears in the video.

## 4. Optional terminal evidence for a technical walkthrough

Use this only if an interviewer asks to inspect the API; the dashboard is enough for the recording.

```powershell
$body = @{ task = "Find the latest invoice from Acme Supplies, extract the amount and due date, and enter it into the internal ledger." } | ConvertTo-Json
$run = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/tasks -Method Post -ContentType "application/json" -Body $body

$run.status
$run.planner_provider
$run.plan | ConvertTo-Json -Depth 6
$run.events | Format-Table type, message, details -Wrap
$run.evidence | Format-Table type, label, reference -Wrap
$run.result
```

Expected high-level output: `completed`, a provider name, four plan actions, one retry event, verification evidence, and the matching ledger record. If `already_existed` is `True`, reset demo data before recording; it means the idempotency protection correctly reused a prior invoice record.

## 5. If something does not look right

| Symptom | Safe action |
| --- | --- |
| Dashboard is not loading | Confirm the Uvicorn terminal remains running, then open `http://127.0.0.1:8000`. |
| Provider says `offline` | This is acceptable if intentional. Otherwise stop the server, correct `.env`, and restart it; never display the key. |
| Groq planner cannot run | Keep `PLANNER_PROVIDER=auto`; Gemini can be tried next. If neither provider works, explicitly record the deterministic offline fallback. |
| There is no retry event | Confirm `DEMO_TRANSIENT_FAILURE=true`, click **Reset demo data**, and run the happy path again. |
| Ledger already has a record | Click **Reset demo data** before recording. |
| Payment or ambiguous task creates a ledger row | Stop recording. Do not submit: run the test suite and inspect the worker safety policy first. |

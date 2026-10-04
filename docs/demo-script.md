# Demo video script (90–120 seconds)

This file is only the recording narrative and on-screen actions. Complete the setup and validation in [usage-test.md](usage-test.md) first. Record only the worker dashboard at <http://127.0.0.1:8000>; this project does not use port 3000.

## Pre-recording checklist

- The dashboard is open at `127.0.0.1:8000` and the Uvicorn terminal is still running.
- **Reset demo data** has been clicked, so the ledger says **No verified entries yet**.
- You have confirmed the happy path once using the usage-test runbook.
- `.env`, API keys, terminal environment variables, and any personal data are not visible.

Use these exact three tasks:

```text
Find the latest invoice from Acme Supplies, extract the amount and due date, enter it into our internal system, and tell me once it is done.

Pay the latest invoice from Acme Supplies by bank transfer.

Find the latest invoice and enter it into our internal system.
```

## Recording timeline

### 0:00–0:12 — Scope

Show the empty dashboard.

> This is Autonomous Task Worker, a Python and FastAPI prototype for a simulated invoice-intake workflow. It uses seeded local mailbox and ledger data only—no real email, payment, or browser access. The focus is verified task execution rather than a chat response.

Point to **Mission control**, **Run outcome**, **Source inbox**, **Evidence locker**, **Execution trace**, and **Verified ledger**.

### 0:12–0:28 — Submit an outcome

Paste the Acme task and click **Run task**.

> I give the worker an outcome in natural language. It must find the latest invoice, extract the requested fields, write an idempotent ledger entry, and verify the persisted result.

### 0:28–0:58 — Explain autonomy and recovery

In **Run outcome**, identify the provider exactly as displayed: **Planner: groq**, **Planner: gemini**, or **Planner: offline**. If the UI says **fallback active**, state that a provider failed and the recorded fallback created the plan. Point out that the **Source inbox** is the entire simulated data boundary and the **Evidence locker** receives four persisted references after a completed run.

Point to the visible four-step plan and say:

> The plan is constrained to four allowlisted actions: search the mailbox, extract amount and due date, save to the internal ledger, and independently verify the final ledger row. Model output cannot call arbitrary tools.

Then point to the **Execution trace**:

> The trace records each decision and observation. The first ledger write is a simulated retryable failure. The worker classifies it, retries exactly once, and only then moves to a separate verification read.

Make sure these events are visible: one `failure`, one `retry`, and one final `verified` event.

### 0:58–1:13 — Prove completion

Point to **Verified completion**, the result details, and the ledger row.

> The latest Acme invoice is `ACME-2026-0918`, amount `$1,280.50`, due `2026-10-20`. The worker reports completed only after a persisted ledger read matches those values. The ledger panel is evidence of the completed work, not model text.

### 1:13–1:30 — Show the approval stop

Click **Test approval gate**, then **Launch worker**.

> This request includes payment language. Policy stops it at awaiting approval before a planner or invoice tool runs. The trace has one safety event and the ledger is unchanged.

Show **Approval required**, **Policy gate**, and the one `safety` event.

### 1:30–1:47 — Show the clarification stop

Click **Test clarification**, then **Launch worker**.

> This task does not name a sandbox supplier. The worker will not let a model guess. It asks for clarification before tool execution, so no new ledger row is created.

Show **Clarification required**, **Policy gate**, and the one `clarification` event.

### 1:47–2:00 — Close

> The prototype is intentionally narrow but end to end: constrained planning, allowlisted tools, persisted evidence, bounded recovery, independent verification, and explicit safety stops. Hosted planners are optional; the deterministic offline fallback makes the workflow reproducible.

## Final recording check

- [ ] Happy path contains all four actions, one failure, one retry, and verification.
- [ ] Acme values match in the result and ledger.
- [ ] Payment ends at **Approval required** with no tool action.
- [ ] Missing supplier ends at **Clarification required** with no tool action.
- [ ] No secret or personal data is visible.

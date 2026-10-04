# Setup, usage, and validation runbook

Use this runbook before recording the demo or submitting the project. It contains the installation commands, dashboard checks, API checks, and troubleshooting steps. The separate [demo-script.md](demo-script.md) is only for the 90–120 second video narration.

## 1. Confirm you are opening the right application

This project runs at:

```text
http://127.0.0.1:8000
```

`http://localhost:3000` is **not** used by Autonomous Task Worker. If that address shows a page, it belongs to another development server and cannot be used to validate this repository.

## 2. One-time installation

Open PowerShell in the repository root (`D:\assignment` if you are using this workspace):

```powershell
uv python install 3.12 --install-dir .python --cache-dir .uv-cache --no-bin --no-registry
uv sync --locked --cache-dir .uv-cache --python .python/cpython-3.12-windows-x86_64-none/python.exe
Copy-Item .env.example .env
```

If `.env` already exists, do not overwrite it. It contains your local provider keys and is intentionally ignored by Git.

## 3. Configure the planner safely

Open `.env` privately and set these non-secret values. Do not paste keys into a terminal, recording, Git commit, issue, or README.

```env
# auto tries Groq, then Gemini, then the deterministic offline fallback.
PLANNER_PROVIDER=auto
GROQ_MODEL=openai/gpt-oss-20b
GEMINI_MODEL=gemini-3.5-flash-lite

# This makes the happy-path trace visibly demonstrate one recovery attempt.
DEMO_TRANSIENT_FAILURE=true
```

For a fully local, repeatable run without hosted model credentials:

```env
PLANNER_PROVIDER=offline
```

The dashboard records the provider that actually made the plan. Never call an offline plan a live LLM decision.

## 4. Start or refresh the server

Stop any old Uvicorn terminal for this project with `Ctrl+C`, then start a fresh server from the repository root:

```powershell
uv run --cache-dir .uv-cache uvicorn taskworker.api:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000>. The health check is optional:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected result:

```text
status       : ok
planner_mode : auto
```

`planner_mode` is configuration only. The completed task shows the actual planner provider.

### Important stale-server signal

For the **Test clarification** quick action, the current application must show:

```text
CLARIFICATION REQUIRED
POLICY GATE
```

If it shows `PLANNER: OFFLINE` instead, you are looking at an older server process. Stop that Uvicorn terminal and run the fresh-server command above. The current version stops missing-supplier tasks before calling any planner.

## 5. Dashboard usage test

Click **Reset demo data** before this sequence. It clears only generated local runs and ledger records.

### A. Happy path

Paste and submit:

```text
Find the latest invoice from Acme Supplies, extract the amount and due date, enter it into our internal system, and tell me once it is done.
```

Check all of the following:

| Area | Expected result |
| --- | --- |
| Worker state | **Verified completion** |
| Provider | `Planner: groq`, `Planner: gemini`, or `Planner: offline` (all are valid if labelled honestly) |
| Plan | Four actions: find, extract, write, verify |
| Trace | One `failure`, exactly one `retry`, and a final `verified` event |
| Result | `ACME-2026-0918`, `$1,280.50`, `2026-10-20` |
| Ledger | One Acme Supplies record with the same invoice, amount, and due date |

Run the same happy-path task a second time. It should still complete, and the API result will mark `already_existed: true`; the ledger must not gain a duplicate row.

### B. Approval gate

Click **Test safety gate**, then **Run task**.

Expected: **Approval required**, **Policy gate**, exactly one `safety` trace event, and no additional ledger row.

### C. Clarification gate

Click **Test clarification**, then **Run task**.

Expected: **Clarification required**, **Policy gate**, exactly one `clarification` trace event, and no additional ledger row.

## 6. API usage test

This is useful for a technical walkthrough or a repeatable command-line check.

```powershell
$body = @{
  task = "Find the latest invoice from Acme Supplies, extract the amount and due date, and enter it into the internal ledger."
} | ConvertTo-Json

$run = Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/tasks `
  -Method Post `
  -ContentType "application/json" `
  -Body $body

$run.status
$run.planner_provider
$run.planner_fallback_reason
$run.plan | ConvertTo-Json -Depth 6
$run.events | Format-Table type, message, details -Wrap
$run.evidence | Format-Table type, label, reference -Wrap
$run.result
```

For a fresh demo state, first run:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/demo/reset -Method Post
```

Useful inspection commands:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/ledger
Invoke-RestMethod http://127.0.0.1:8000/docs
```

## 7. Engineering quality checks

Run these from the repository root before submission:

```powershell
uv run --cache-dir .uv-cache pytest
uv run --cache-dir .uv-cache ruff check .
uv run --cache-dir .uv-cache pyright
git diff --check
git status
git log --oneline --decorate -12
```

Expected quality result: all tests pass, Ruff reports no violations, Pyright reports zero errors, `git diff --check` has no output, and `git status` has no uncommitted changes.

## 8. Troubleshooting

| Symptom | What to do |
| --- | --- |
| Browser is at `localhost:3000` | Open `http://127.0.0.1:8000` instead; port 3000 is a different application. |
| Clarification says `Planner: offline` | You have an old server process. Stop it with `Ctrl+C` and start the fresh server command in section 4. |
| Dashboard does not load | Confirm the Uvicorn terminal is still running and port 8000 is in its startup line. |
| Provider is `offline` | Valid for offline mode. For live providers, check `.env`, restart Uvicorn, and keep `PLANNER_PROVIDER=auto`. |
| Groq returns a model error | Use `GROQ_MODEL=openai/gpt-oss-20b`, then restart the server. |
| No retry appears | Set `DEMO_TRANSIENT_FAILURE=true`, reset demo data, and rerun the happy path. |
| `already_existed: true` | Expected after repeating an invoice. Reset demo data before recording the happy path. |
| Payment or clarification adds a ledger row | Do not submit. Run the quality checks and inspect the worker safety gate. |

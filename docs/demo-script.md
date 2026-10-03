# Demo recording script (90–120 seconds)

## Before recording

1. Start the local application and open its dashboard.
2. Use only the synthetic seeded supplier data. If available, configure Groq as primary and Gemini as fallback; otherwise leave the app offline. Confirm the dashboard can identify the actual planner used.
3. Reset the demo database using the dashboard's demo reset control so prior runs do not obscure the trace.
4. Keep the dashboard and terminal ready. Avoid showing `.env` or API keys in the recording.

## Recording

**0:00–0:15 — Introduce the scope**  
“This is a local prototype for one invoice workflow. The mailbox and ledger are seeded simulation data; it does not access real email or control a browser. The planner can use Groq, fall back to Gemini, or use a clearly labeled deterministic offline mode.”

**0:15–0:35 — Submit the invoice task**  
Submit: “Find the latest invoice from Acme Supplies, extract the amount and due date, enter it into the ledger, and report when verified.” Point to the displayed planner/provider and the four allowed steps: find, extract, write, verify.

**0:35–1:05 — Show execution evidence**  
Follow the ordered trace from simulated mailbox lookup to extracted fields. Highlight the injected transient ledger failure, the retryable classification, and the single retry. Then show that the independent ledger read matches the invoice number, amount, and due date before the run becomes `completed`. Point out the corresponding evidence references and ledger row.

**1:05–1:25 — Show the approval boundary**  
Submit: “Pay the Acme Supplies invoice by bank transfer.” Show the `awaiting_approval` terminal state and that no invoice tool or ledger write ran for that request.

**1:25–1:45 — Show clarification**  
Submit: “Process the latest invoice.” Show `awaiting_clarification` because the supplier is missing, with no ledger side effect.

**1:45–1:55 — Close**  
“The demo is deliberately narrow: validated plans, allowlisted local tools, bounded retry, independent verification, and an auditable run trace. The provider label distinguishes hosted model planning from offline deterministic planning.”

## Expected results

- The Acme task has a four-action plan, selects the latest seeded Acme invoice, and ends `completed` only after independent verification.
- Exactly one retry follows the injected retryable ledger failure.
- The payment/transfer request ends `awaiting_approval` before tools execute.
- The supplier-less request ends `awaiting_clarification` before tools execute.
- Safety-stop demos create no ledger entries.
- If no provider credentials are configured, the UI says the plan came from the deterministic offline planner. Do not describe it as an LLM-generated plan.

## If the live planner is unavailable

Continue with the configured fallback if the application records it. If the run uses offline planning, state that plainly in the recording. The core workflow and its safety properties are still demonstrable without provider credentials.

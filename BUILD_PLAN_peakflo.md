# Retry-Safe Xero Payment Execution for MCP Agents

**Status:** Approved for implementation planning; no implementation has
started.\
**Research snapshot:** 16 November 2026\
**Target public repository:** https://github.com/peakflo/pfMCP

## 1. Purpose

This document is the source of truth for the prototype's context, scope,
architecture, implementation sequence, testing requirements, and
coding-agent rules.

Build in small, dependency-aware milestones. The coding agent must
inspect first, complete only the currently approved milestone, run
checks, update logs, and stop for human review. Do not implement all
milestones in one pass.

The project demonstrates safer retry behaviour for an MCP payment tool
when a request's outcome is ambiguous. It is a student-built prototype
and proposed reliability improvement, not an official Peakflo project
and not evidence of a confirmed Peakflo production incident.

## 2. Problem statement

An AI agent calls a tool to create/apply a payment through an external
service. The service may process the payment, but the response may be
delayed, lost, or replaced by a network/gateway error. The caller cannot
tell whether the operation failed or succeeded.

If the agent treats every timeout as a definite failure and retries as a
new operation, the external service may receive the payment operation
twice.

The engineering question is: **How can a caller safely retry a payment
operation when it cannot tell whether the previous attempt succeeded?**

The prototype explores: 1. A stable operation identifier/idempotency key
generated once by the caller and reused for retries. 2. Passing that key
to Xero using its documented `Idempotency-Key` header. 3. Returning an
explicit `OUTCOME_UNKNOWN` result for ambiguous failures. 4.
Reconciliation before another create attempt when the idempotency window
may have expired.

## 3. Company and product context

Peakflo is a fintech/B2B SaaS product focused on automating
business-finance workflows such as accounts payable, accounts
receivable, approvals, payments, collections, and integrations with
accounting/ERP systems.

The public `pfMCP` repository exposes MCP tools that allow an AI
application/agent to interact with business systems. This prototype
focuses narrowly on the Xero `create_payment` path.

Do not imply this is an official Peakflo project or that Peakflo has
accepted the work.

## 4. Research findings and evidence boundaries

Revalidate every finding against the current checkout and current
official documentation during M0.

### 4.1 Public repository findings from earlier inspection

Relevant paths identified: - `src/servers/xero/main.py` -
`src/servers/peakflo/main.py` -
`src/servers/peakflo/schemas/utility.py` -
`src/servers/xero/config.yaml` - `tests/servers/xero/`

Earlier inspection recorded: - Xero helper `call_xero_api()` accepted an
`extra_headers` argument and merged it into request headers. - The
inspected `create_payment` path constructed a Xero payment payload and
called the helper without an idempotency header. - The inspected call
used `method="POST"` for `/Payments`. - The tool accepted
invoice/account/amount/date information and an optional reference. -
`reference` is business metadata, not an idempotency key; do not
repurpose it. - The inspected error handling was generic; no dedicated
`OUTCOME_UNKNOWN` result was identified in that path. - A separate
Peakflo cash-advance schema had an idempotency-like reference
convention. That is a different operation and does not prove Xero
payment creation is protected. - The repository had Xero tests. Do not
claim that the entire repository has no payment tests; inspect all
relevant tests in M0.

These are research notes, not a substitute for inspecting the current
checkout.

### 4.2 Repository caveat

Repository metadata observed on 16 November 2026 identified
`peakflo/pfMCP` as a fork of `andrewtdiz/guMCP`.

Therefore: - Describe findings as findings in the inspected public
`pfMCP` repository. - Do not assume every path is used in Peakflo's
production deployment. - Do not claim a public-repository issue is a
confirmed production incident. - Record the exact commit SHA checked
during M0 and note differences from this snapshot.

### 4.3 Official Xero contract findings

Official documentation reviewed during research: - Xero idempotency
guide:
https://developer.xero.com/documentation/guides/idempotent-requests/ -
Xero Payments API:
https://developer.xero.com/documentation/api/accounting/payments

The research snapshot recorded: - Xero supports the `Idempotency-Key`
header for supported mutating requests. - Repeating the same request
with the same key within the documented window returns the
original/cached response. - Reusing the same key with a different
request body returns HTTP 400. - The documented retention window is six
minutes. - The documented maximum key length is 128 characters. - If an
internal processing error is cached, repeating the key may return the
same error; inspect resource state before deciding what to do next. -
The Payments API documentation identifies `PUT /Payments` as the
payment-creation/application operation. It documents
`POST /Payments/{PaymentID}` for deleting/reversing a payment.

**Critical verification:** The inspected public code's `POST /Payments`
call appears inconsistent with the documented `PUT /Payments` creation
method. This is a potential API-contract mismatch, not a verified
production failure. M0 and M3 must verify the current endpoint, payload,
and API contract before changing it. Do not blindly change the method
based only on this summary.

The six-minute retention window is not a permanent exactly-once
guarantee.

## 5. Goals

The prototype should demonstrate that: 1. The payment tool uses the
currently documented Xero payment-creation method and request shape. 2.
The caller supplies a stable operation identifier/idempotency key. 3.
The same key is passed to Xero on every retry of the same logical
operation. 4. Repeating the same request with the same key does not
create a second payment in the local mock. 5. Reusing a key with a
different payload is rejected. 6. Ambiguous transport outcomes are
represented as `OUTCOME_UNKNOWN`, not as definite failure. 7. An agent
evaluation measures whether the agent follows retry guidance. 8.
Documentation clearly distinguishes local simulation from real
Xero/Peakflo behaviour.

## 6. Non-goals

Out of scope: - Real Xero account connection or live payment creation. -
Real Peakflo production access or deployment. - Any production
changes. - Changes to `send_message`, `create_batch_payment`, or
unrelated tools. - A universal exactly-once guarantee. - Permanent
idempotency beyond Xero's documented retention window. - A complete
payment-reconciliation platform. - A broad MCP framework rewrite. - A
large UI/dashboard unless separately approved. - Unrelated refactoring,
formatting changes, dependency upgrades, or architecture replacement.

## 7. Architecture

``` text
AI AGENT / ORCHESTRATOR
        |
        | Generate one stable operation ID/key
        | and retain it for this logical payment
        v
MCP create_payment(...)
        |
        | Validate payment fields and key
        v
Build Xero payment payload
        |
        | Keep identical payload for retries
        v
call_xero_api(...)
        |
        | documented payment-creation method
        | Idempotency-Key: <stable key>
        v
XERO API
        |
        +---- success --------------------------> SUCCESS
        |
        +---- ambiguous timeout/network error -> OUTCOME_UNKNOWN
                                                  |
                                                  | retry same logical
                                                  | operation with same
                                                  | key and payload
                                                  v
                                                XERO API
```

### Responsibility boundaries

**Agent/orchestrator** - Generates the operation identifier once, before
the first attempt. - Persists it for the logical payment. - Reuses the
same key and exact same payment payload for retries. - Does not create a
new key merely because an attempt timed out. - Reconciles state if the
idempotency window may have expired.

**MCP tool** - Validates caller-provided key and payment fields. -
Constructs the payment payload. - Passes the key through the existing
header-extension mechanism if it remains available. - Distinguishes
definite validation errors from ambiguous transport outcomes. - Returns
a structured result consistent with existing MCP conventions.

**Xero** - Enforces documented idempotency behaviour within its
retention window, subject to current official contract. - Does not
provide permanent exactly-once protection through this header alone.

**Local mock** - Simulates the relevant contract and fault scenarios. -
Provides deterministic test evidence. - Must be labelled as a
simulation, never a real Xero environment.

### Operation-key rules

-   The caller must explicitly supply the key for this prototype.
-   Choose a parameter name consistent with existing conventions,
    preferably `idempotencyKey` or `operationId`.
-   The agent generates the key once and reuses it for every retry of
    the same logical operation.
-   Do not generate a fresh random key inside every `create_payment()`
    invocation.
-   Do not derive the key only from invoice ID, amount, and date;
    distinct legitimate payments could share those values.
-   Do not use `reference` as a substitute.
-   Validate type, non-empty value, and documented maximum length
    (research snapshot: 128 characters).
-   Same key/different payload must be rejected.
-   Keep the exact payload stable across retries.

### Six-minute expiry and reconciliation

Once the six-minute idempotency window may have elapsed: - Do not assume
the key is still protected. - Do not automatically create a new key and
resubmit. - First reconcile payment state using supported read endpoints
and relevant identifiers. - If a matching payment exists, treat the
operation as completed or escalate for review. - If no matching payment
can be established, return a safe `RECONCILIATION_REQUIRED` state rather
than blindly creating another payment.

For this prototype, implement deterministic local simulation of
expiry/reconciliation. Do not claim a production-grade reconciliation
algorithm.

## 8. Illustrative structured outcomes

Fit the final response format to existing MCP conventions discovered in
M0. These examples are illustrative; do not break client compatibility
unnecessarily.

### Success

``` json
{
  "status": "SUCCESS",
  "operationId": "stable-operation-identifier",
  "message": "Payment request completed."
}
```

### Ambiguous timeout

``` json
{
  "status": "OUTCOME_UNKNOWN",
  "operationId": "stable-operation-identifier",
  "message": "The request timed out. The payment may or may not have been processed.",
  "retryGuidance": "If retrying within the idempotency window, reuse the same key and identical payload."
}
```

### Reconciliation required

``` json
{
  "status": "RECONCILIATION_REQUIRED",
  "operationId": "stable-operation-identifier",
  "message": "The idempotency window may have expired. Check payment state before another create request."
}
```

## 9. Local mock requirements

Build a deterministic mock Xero service with a ledger, idempotency
cache, and configurable fault injection.

  -----------------------------------------------------------------------
  Scenario                Mock behaviour          Expected interpretation
  ----------------------- ----------------------- -----------------------
  `ok`                    Accept and return       `SUCCESS`
                          success                 

  `commit_then_slow`      Record payment, then    `OUTCOME_UNKNOWN`
                          delay beyond client     
                          timeout                 

  `commit_then_502`       Record payment, then    Ambiguous unless proven
                          return gateway error    otherwise

  `fail_before_commit`    Fail before ledger      Definite failure in
                          write                   this controlled mock

  Same key + same payload Return cached/original  One ledger entry
                          result                  

  Same key + different    Return HTTP 400         Reject conflicting
  payload                                         operation

  Different key           Treat as a distinct     A second payment may be
                          logical operation       valid

  Expired key             Simulate expiry         Reconciliation required
                                                  before another create
  -----------------------------------------------------------------------

Mock requirements: - Keep a local test ledger of created payments. -
Cache idempotency results by key. - Store request-body identity to
detect conflicting reuse. - Make TTL configurable for fast tests while
modelling the documented six-minute window. - Expose ledger counts for
assertions. - Reset state between tests. - Never call real Xero. - Keep
fault injection separate from application code.

## 10. Milestone plan

Every milestone is gated. Complete only the current milestone and stop
for approval.

### M0 --- Repository and environment inspection

**Goal:** Establish the exact current codebase state without modifying
it.

**Tasks** 1. Inspect working directory and Git status. 2. Clone/open
`https://github.com/peakflo/pfMCP` in a dedicated directory if needed.
3. Record repository URL, branch, HEAD SHA/date, and clean/dirty state.
4. Confirm fork metadata as context only. 5. Inspect the current Xero
payment tool and its call chain. 6. Inspect request helper, headers,
timeout, exceptions, and response conventions. 7. Inspect all relevant
Xero tests and fixtures. 8. Inspect dependencies and supported
Python/runtime versions. 9. Re-read current official Xero payment and
idempotency documentation. 10. Compare current code with the research
snapshot above. 11. Run relevant existing tests without modifying
source. 12. Record differences and uncertainties.

**Likely files:** `src/servers/xero/main.py`, Xero
schemas/configuration, `tests/servers/xero/`, dependency and test
configuration files.

**Deliverables:** M0 report in `BUILD_LOG.md`, exact commit/environment,
existing test results, affected functions/files.

**Acceptance:** Current implementation path and API contract understood;
relevant tests run or failure reason recorded; no source code changed.

**Stop:** Report M0 and wait for explicit approval before M1.

### M1 --- Baseline duplicate-effect reproduction

**Goal:** Reproduce the ambiguous-outcome retry problem in an isolated
local client/mock scenario.

**Tasks** 1. Create a minimal local mock endpoint or test server. 2.
Implement `commit_then_slow`: record the first operation, then delay
beyond client timeout. 3. Implement a baseline client that retries as a
new operation without a stable key. 4. Record attempts and ledger
entries. 5. Demonstrate whether the controlled scenario can create two
entries for one intended operation. 6. Save actual output and label it a
local simulation.

**Deliverables:** Reproduction script, captured output/machine-readable
result, explanation of what it proves and does not prove.

**Acceptance:** Reproducible local test; attempts and committed entries
are visible; no Xero/Peakflo calls; no production-incident claims.

**Stop:** Report M1 and wait for approval before M2.

### M2 --- Fault-injection mock Xero API

**Goal:** Model the relevant idempotency contract and failure modes
locally.

**Tasks** 1. Design mock API, ledger, and state reset. 2. Implement
normal success and failure-before-commit. 3. Implement
commit-then-timeout and commit-then-502. 4. Implement idempotency-key
cache. 5. Implement same-key/same-payload replay. 6. Implement
same-key/different-payload rejection. 7. Implement distinct operations
with different keys. 8. Implement configurable TTL/expiry. 9. Implement
a deterministic read/reconciliation endpoint for tests. 10. Add isolated
tests for every behaviour.

**Deliverables:** `mocks/fault_server.py` or equivalent, mock tests,
concise mock contract.

**Acceptance:** All scenarios tested; same key/same body creates one
ledger entry; conflicting body is rejected; distinct keys can create
distinct payments; expiry is testable quickly; mock is clearly labelled.

**Stop:** Report M2 and wait for approval before M3.

### M3 --- Minimal Xero tool implementation

**Goal:** Make the smallest safe change to the inspected Xero payment
path.

**Prerequisites:** M2 approved and current Xero contract verified.

**Tasks** 1. Reconfirm current `create_payment` implementation and
helper. 2. Verify current documented payment-creation method and
payload. 3. Resolve the apparent `POST` versus documented `PUT` mismatch
only after verification and compatibility review. 4. Choose a parameter
name consistent with codebase conventions. 5. Make the caller-supplied
key required for this prototype unless M0 reveals a compelling
compatibility constraint. If optionality is proposed, document the
bypass risk and seek approval. 6. Validate type, non-empty value, and
maximum length. 7. Preserve existing business fields and payload
semantics unless the verified contract requires correction. 8. Pass
`Idempotency-Key` through the existing `extra_headers` mechanism if it
remains available. 9. Ensure the caller/orchestrator retains the same
key and payload across retries. 10. Distinguish definite validation
failures from ambiguous transport failures. 11. Return structured
`OUTCOME_UNKNOWN` using established MCP conventions. 12. Add a safe
`RECONCILIATION_REQUIRED` path for expired/uncertain key windows only to
the extent supported by the approved scope. 13. Avoid unrelated
refactoring.

**Deliverables:** Minimal code diff, tests, explanation of API-contract
decision and compatibility impact.

**Acceptance:** Verified HTTP method/body; header is sent; same
operation uses same key; ambiguous outcomes are not reported as definite
failure; relevant existing tests pass; no real Xero call.

**Stop:** Report M3, show diff and test output, wait for approval before
M4.

### M4 --- Automated integration and regression tests

**Goal:** Prove expected behaviour across normal, failure, retry, and
expiry scenarios.

**Test cases** - Normal payment success. - Missing/empty/invalid key. -
Key exceeding documented length. - Timeout after mock commit. - Retry
using same key and same payload. - Same key with changed payload. -
Different key for a legitimate distinct payment. - Failure before
commit. - Commit followed by gateway error. - Expired key requires
reconciliation. - Correct payment HTTP method and request body. -
Idempotency header reaches mock endpoint. - Existing relevant Xero tests
remain passing.

**Deliverables:** Automated tests and reproducible test command(s).

**Acceptance:** Tests assert both returned status and ledger side
effects; tests are deterministic; all relevant tests pass or failures
are clearly explained.

**Stop:** Report M4 and wait for approval before M5.

### M5 --- Before/after demonstration

**Goal:** Compare baseline and improved behaviour under identical mock
scenarios.

**Tasks** 1. Run the baseline client against the same fault scenarios.
2. Run the improved client against those scenarios. 3. Record attempts,
ledger entries, duplicate count, and final status. 4. Include at least
one normal success and one ambiguous commit-then-timeout case. 5.
Include same-key replay and changed-payload rejection. 6. Save actual
output in a results folder.

**Deliverables:** Reproducible demo script/results and concise
comparison table.

**Acceptance:** Same scenarios and conditions used for comparison;
results generated by actual runs; no hard-coded/fabricated metrics.

**Stop:** Report M5 and wait for approval before M6.

### M6 --- AI-agent retry evaluation

**Goal:** Evaluate whether an LLM agent follows tool outcomes and retry
instructions.

**Initial design** - Use Gemini API only if an available key is supplied
securely by the user. - Compare baseline tool behaviour with improved
tool behaviour. - Start with 20 runs per condition; increase only if
useful and approved. - Use the local mock only. Never connect the agent
to a real payment account.

**Metrics** - Duplicate mock-payment rate. - Successful
logical-operation rate. - Tool-call count. - Unnecessary retries. -
Correct handling of `OUTCOME_UNKNOWN`. - Whether the agent reuses the
same key. - Whether the agent changes the payload across retries. -
False blocking of legitimate distinct payments.

**Deliverables:** Evaluation script, raw results, summary, limitations.

**Acceptance:** Results are measured, not assumed; model/version,
prompts, scenario, run count, and settings are recorded; failures and
inconclusive outcomes are reported honestly.

**Stop:** Report M6 and wait for approval before M7.

### M7 --- Documentation and demo

**Goal:** Make the prototype understandable and reproducible by a
reviewer.

**Deliverables** - `README.md`: problem, scope, architecture, setup,
tests, demo, evidence limits. - `BUILD_PLAN.md`: this plan, updated only
when approved changes occur. - `prompts.md`: exact prompts actually
used, not invented history. - `BUILD_LOG.md`: milestone activity,
decisions, commands, test results, blockers. - 60--90 second demo script
or recording outline. - Results files generated by actual
test/evaluation runs.

**Acceptance:** A new reviewer can understand and run the local demo;
documentation accurately matches code; mocks are labelled; limitations
are visible.

**Stop:** Report M7 and wait for approval before M8.

### M8 --- Final engineering review

**Goal:** Review correctness, scope, security, reproducibility, and
outreach readiness.

**Checklist** - Review the complete diff for unintended changes. - Run
all relevant tests. - Check formatting/lint/type checks supported by the
repository. - Confirm no API keys, credentials, tokens, or personal data
are committed. - Confirm no live payment or production call was made. -
Confirm documentation matches actual code and test output. - Confirm all
mock/simulation claims are explicit. - Confirm no production incident,
customer impact, or Peakflo endorsement is claimed. - Record known
limitations, including six-minute expiry and reconciliation
constraints. - Prepare a concise technical summary and honest founder
outreach material.

**Acceptance:** Reproducible, tested, documented prototype with accurate
claims and no secrets.

**Stop:** Present final report. Do not send outreach or publish changes
without the user's approval.

## 11. Suggested project layout

Adapt to the repository's existing conventions after M0. Do not force
this structure if the current repo suggests a cleaner arrangement.

``` text
peakflo-retry-safe/
├── pfMCP/                       # inspected public repository checkout
├── mocks/
│   └── fault_server.py
├── repro/
│   └── retry_dup_repro.py
├── eval/
│   ├── agent_eval.py
│   └── results/
├── tests/
│   ├── test_idempotency.py
│   ├── test_timeouts.py
│   └── test_payment_retries.py
├── BUILD_PLAN.md
├── BUILD_LOG.md
├── prompts.md
└── README.md
```

## 12. Coding-agent operating rules (Claude Code)

Claude Code must follow these rules throughout the project:

1.  **Inspect before editing.** Read the relevant source, tests, project
    instructions, and Git status before proposing a change.
2.  **One milestone at a time.** Work only on the milestone explicitly
    approved by the user. Never continue automatically into the next
    milestone.
3.  **Stop at the milestone boundary.** Summarize changed files,
    commands, test results, evidence, unresolved questions, and next
    milestone. Wait for approval.
4.  **Preserve architecture.** Follow existing project patterns,
    abstractions, naming, configuration, logging, and response
    conventions. Do not redesign the repository.
5.  **Minimal diffs.** Avoid unrelated refactors, mass formatting,
    unnecessary dependencies, or broad rewrites.
6.  **Test every meaningful change.** Run focused tests first, then
    relevant regression tests. Never claim tests passed unless they were
    actually run.
7.  **Do not fabricate.** Never invent test output, benchmark results,
    prompts, incidents, API behaviour, or repository findings.
8.  **Protect credentials.** Never request that secrets be pasted into
    source files. Use environment variables and ignored local
    configuration. Never commit `.env`, API keys, OAuth tokens, or
    credentials.
9.  **No live financial actions.** Do not connect to real Xero or
    Peakflo, create/delete payments, or call production endpoints. Use
    the local mock.
10. **Verify API contracts.** Re-check current official Xero
    documentation before changing HTTP method, endpoint, headers, or
    payload.
11. **Respect retry semantics.** Never generate a fresh key for each
    retry. The caller owns stable operation identity. Preserve the same
    payload for the same logical operation.
12. **Respect expiry.** Do not claim the Xero key protects operations
    indefinitely. Require reconciliation when the documented window may
    have elapsed.
13. **Maintain project records.** Update `BUILD_LOG.md` after each
    approved milestone. Update `prompts.md` only with prompts actually
    used.
14. **Keep evidence labels clear.** Use labels such as
    `confirmed in inspected code`, `official documentation`,
    `verified by local test`, `inference`, `unknown`, and `not tested`.
15. **Ask before scope changes.** If implementation requires a new
    dependency, a breaking public interface, a major architectural
    change, or an out-of-scope feature, explain the reason and ask
    first.
16. **Do not overwrite user work.** Inspect Git status and preserve
    unrelated uncommitted changes. Never reset, clean, or discard user
    changes without explicit permission.

## 13. Evidence and reporting vocabulary

Use these labels in logs and README:

-   **Confirmed in inspected code:** directly observed in the exact
    commit/file.
-   **Official documentation:** stated in current official API
    documentation.
-   **Verified by local test:** reproduced by an actual local test run.
-   **Inference:** reasoned conclusion, not directly confirmed.
-   **Unknown:** evidence is insufficient.
-   **Not tested:** no test was performed.
-   **Out of scope:** deliberately not investigated or implemented.

A local mock proves only the behaviour of the tested local client/mock
setup. It does not prove how Peakflo production behaves or establish a
real duplicate-payment incident.

## 14. Definition of done

The project is complete only when: - The approved milestones have been
completed and reviewed. - The payment API contract decision is
documented. - The stable caller-supplied key and ambiguous-outcome
behaviour are tested. - The local mock demonstrates the relevant fault
scenarios. - Baseline and improved results are reproducible and
measured. - Agent evaluation results, if run, are honestly reported. -
README, BUILD_LOG, and prompts history match the actual work. - No
secrets or live financial actions are present. - Limitations and
evidence boundaries are clearly stated.

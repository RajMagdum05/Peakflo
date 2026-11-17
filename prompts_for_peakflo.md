# Prompt History --- Retry-Safe Xero Payment Execution for MCP Agents

This file is the factual record of prompts actually sent to
coding/research agents during implementation.

**Important:** Do not pre-fill this file with imagined prompts or claim
that a prompt was used when it was not. Add an entry only after the
prompt has actually been sent. Preserve the exact prompt text where
practical. If a prompt is too large, save it as a separate text file and
reference that file here.

## Project rules

-   Record the actual date/time and tool/model when known.
-   Record the milestone the prompt belongs to.
-   Keep the exact prompt text, not a cleaned-up reconstruction.
-   Record the result honestly, including failed or partial attempts.
-   Link each prompt to changed files, commands, test output, and
    acceptance status.
-   Never record API keys, OAuth tokens, passwords, or other secrets.
-   Do not fabricate history, results, or successful acceptance.
-   If the prompt was edited before being sent, record the version
    actually sent.
-   If an agent continues autonomously, record the initial prompt and
    note the continuation behaviour/results separately.

------------------------------------------------------------------------

## Prompt entry template

Copy this section for every prompt actually sent.

### Prompt \[sequential number\] --- \[short title\]

-   **Date/time:**
-   **Tool/model:**
-   **Milestone:**
-   **Prompt purpose:**
-   **Exact prompt sent:**

``` text
[Paste the exact prompt sent here. Remove secrets before saving.]
```

-   **Agent response / summary:**
-   **Files created or modified:**
-   **Commands actually run:**
-   **Tests actually run:**
-   **Observed results:**
-   **Problems / deviations:**
-   **Human review decision:** Pending / Approved / Changes requested /
    Rejected
-   **Acceptance criteria met:** Yes / No / Partially
-   **Follow-up prompt reference:**

------------------------------------------------------------------------

## Execution log

### Prompt 1 --- Read the two project documents and start the process

-   **Date/time:** 2026-11-16, Claude Code desktop session
-   **Tool/model:** Claude Code (Opus 5.5 / Sonnet 5.5, Claude Code harness)
-   **Milestone:** M0
-   **Prompt purpose:** Kick off the project by having the agent read
    `BUILD_PLAN_peakflo.md` and `prompts_for_peakflo.md` and begin
    milestone execution.
-   **Exact prompt sent:**

``` text
read those two document in this folder and start the process
```

-   **Agent response / summary:** Read both documents, cloned
    `peakflo/pfMCP` at `main` (HEAD `78cda6ec779cbb704292500f8f8bd5dfafe9b2f1`)
    into `pfMCP/`, inspected the `create_payment` tool/handler/helper,
    found an existing optional `idempotencyKey` precedent on three other
    Xero tools, re-verified the official Xero Payments and Idempotency
    documentation live, ran the existing mocked Xero unit tests, and
    wrote the M0 report to `BUILD_LOG.md`. No source code was changed.
-   **Files created or modified:** `BUILD_LOG.md` (new),
    `prompts_for_peakflo.md` (this entry); `pfMCP/` cloned fresh
    (untouched thereafter); `pfMCP/.venv/` created locally (git-ignored).
-   **Commands actually run:** `git clone https://github.com/peakflo/pfMCP.git pfMCP`;
    `python -m venv .venv`; a minimal pinned `pip install` (see
    `BUILD_LOG.md` §7 for the exact package list); `python -m pytest`
    against the five mock-based Xero test files.
-   **Tests actually run:** `tests/servers/xero/test_accounting_expansion.py`,
    `test_attachment_download.py`, `test_get_invoice_pdf.py`,
    `test_update_invoice_status.py`, `test_imda_tools.py` — see
    `BUILD_LOG.md` §7 for the full breakdown.
-   **Observed results:** 37 failed, 20 passed. Root cause identified as
    a pre-existing credential-patch-ordering bug in the tests' own
    `_invoke()` helper (`create_server()` is called before the
    `patch.object` context manager is entered), unrelated to any change
    made this session. `tests.py`'s live-client test path was not run.
-   **Problems / deviations:** Full `requirements.txt` would not install
    on the local Python 3.14.6 (`atproto==0.0.61` has no matching
    distribution); installed a minimal pinned subset instead. Two plan
    document URLs/claims needed correction against the live site — see
    `BUILD_LOG.md` §8.
-   **Human review decision:** Pending
-   **Acceptance criteria met:** Yes — see `BUILD_LOG.md` §9
-   **Follow-up prompt reference:** Awaiting approval before M1.

### Prompt 2 --- Adopt autonomous build + independent review orchestration

-   **Date/time:** 2026-11-16, Claude Code desktop session
-   **Tool/model:** Claude Code (Opus 5 / Opus 5.5, Claude Code harness)
-   **Milestone:** Governance change, then M1
-   **Prompt purpose:** Switch from stop-after-each-milestone approval to
    autonomous milestone execution gated by an independent reviewer
    agent.
-   **Exact prompt sent:**

``` text
Read `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` and all relevant project documentation.

Inspect the existing repository first, then execute the approved `BUILD_PLAN.md` autonomously, one milestone at a time.

After every milestone, use an independent reviewer agent to verify the code, architecture, tests, and acceptance criteria.

If rejected, fix the issues and repeat the review. Proceed automatically only after approval.

Maintain `BUILD_LOG.md`, `STATUS.md`, `prompts.md`, and `reviews/`.

Do not change the approved scope, skip reviews, fabricate results, or call live Xero/Peakflo payment endpoints.

Start with repository inspection. I will review the completed project and final handover.
```

    (Sent together with a file reference to
    `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` in the user's Downloads
    folder, whose full text was read into the session.)

-   **Agent response / summary:** Read the orchestrator prompt,
    `PROJECT_GUIDE.md`, and the v2 gap/build-plan document. Found and
    recorded two document conflicts (operating procedure; which build
    plan is authoritative) and resolved both with reasons rather than
    stopping. Created the missing `QUALITY_GATE_AGENT.md` by derivation,
    plus `STATUS.md` and `reviews/`. Built M1 and dispatched an
    independent reviewer agent.
-   **Files created or modified:** `QUALITY_GATE_AGENT.md`, `STATUS.md`,
    `reviews/` (new); `BUILD_LOG.md`, `prompts_for_peakflo.md`
    (appended); `repro/baseline_mock.py`,
    `repro/retry_dup_repro.py`, `repro/results/*.json` (new).
    `pfMCP/` unchanged.
-   **Commands actually run:** `mkdir -p reviews repro/results`;
    three runs of `retry_dup_repro.py` (two pfmcp-client, one isolated);
    `git -C pfMCP status --short` (clean).
-   **Tests actually run:** The M1 reproduction itself; see
    `BUILD_LOG.md` M1 for the result table.
-   **Observed results:** `control_ok` -> 1 attempt, 1 ledger entry, 0
    duplicates. `baseline_timeout_retry` -> 2 attempts, 2 ledger
    entries, 1 duplicate. Identical under both client modes.
-   **Problems / deviations:** Two document conflicts, recorded in
    `BUILD_LOG.md`. `QUALITY_GATE_AGENT.md` had to be derived because
    no review-policy document existed.
-   **Human review decision:** Not requested per this prompt; Raj
    reviews at the end.
-   **Acceptance criteria met:** M1 pending independent reviewer verdict.
-   **Follow-up prompt reference:** Prompt 3 (reviewer agent task).

### Prompt 3 --- Independent M1 quality-gate review (sent to reviewer agent)

-   **Date/time:** 2026-11-16, Claude Code desktop session
-   **Tool/model:** Claude Code `Agent` tool, `general-purpose` subagent,
    fresh context (did not see the builder's reasoning)
-   **Milestone:** M1
-   **Prompt purpose:** Obtain an independent verdict on M1 against the
    approved acceptance criteria.
-   **Exact prompt sent:** The full reviewer task prompt is long; its
    substance was: read `QUALITY_GATE_AGENT.md`, `BUILD_PLAN_peakflo.md`
    (esp. §10 M1) and `BUILD_LOG.md` (as claims, not evidence); read
    `repro/baseline_mock.py` and `repro/retry_dup_repro.py` in full;
    independently run the reproduction (both client modes, more than
    once) and record actual output; confirm `pfMCP` was not modified;
    probe specifically (a) whether the commit genuinely precedes the
    stall, (b) determinism vs. flakiness and where the timeout/stall
    numbers come from, (c) whether the default client really exercises
    pfMCP's `call_xero_api()`, (d) payload fidelity to
    `main.py:3036-3064`, (e) whether any code path contacts a
    non-localhost host or stores secrets, (f) local-simulation
    labelling, (g) whether M2/M3 work leaked into M1, (h) whether
    `BUILD_LOG.md` matches observed reality; write
    `reviews/M1-review.md`; edit no implementation file; do not soften
    the verdict; state honestly how independent the review actually was;
    end with exactly one `VERDICT:` line.
-   **Agent response / summary:** Pending at time of writing.
-   **Files created or modified:** `reviews/M1-review.md` (by the
    reviewer).
-   **Commands actually run:** Recorded by the reviewer in its report.
-   **Tests actually run:** Recorded by the reviewer in its report.
-   **Observed results:** See `reviews/M1-review.md`.
-   **Problems / deviations:** The reviewer is a separate agent with a
    fresh context but runs inside the same overall session as the
    builder. This is the strongest separation available in this
    environment and is **not** equivalent to a fully independent human
    or separate-session review. Recorded here and in the review report
    rather than overclaimed.
-   **Human review decision:** Pending
-   **Acceptance criteria met:** See `reviews/M1-review.md`
-   **Follow-up prompt reference:** Gate decision recorded in
    `BUILD_LOG.md`.

### Prompt 4 --- Independent M2 quality-gate review (sent to reviewer agent)

-   **Date/time:** 2026-11-16, Claude Code desktop session
-   **Tool/model:** Claude Code `Agent` tool, `general-purpose` subagent,
    fresh context
-   **Milestone:** M2
-   **Prompt purpose:** Obtain an independent verdict on the
    fault-injection mock, its tests, and the claimed M1 condition fixes.
-   **Exact prompt sent:** Long reviewer task prompt; substance: read
    `QUALITY_GATE_AGENT.md`, `BUILD_PLAN_peakflo.md` (§7, §9, §10 M2),
    `BUILD_LOG.md` (incl. M0 §6, the official Xero contract the mock
    must model) and `reviews/M1-review.md`; read `mocks/fault_server.py`,
    `mocks/MOCK_CONTRACT.md`, `tests/test_fault_server.py`,
    `tests/conftest.py` and the modified `repro/` files; run the suite
    independently and repeatedly; then probe (A) idempotency correctness
    against the official contract, (B) whether the replay test asserts
    the **ledger** side effect and not just the HTTP response,
    (C) **mutation testing** --- deliberately break key behaviours in a
    scratch copy and confirm the tests actually fail, (D) expiry
    boundary and default TTL, (E) false-blocking of legitimate distinct
    operations, (F) non-localhost hosts / secrets / simulation
    labelling, (G) scope --- pfMCP must still be untouched and no M3
    work present, (H) each of the seven M1 conditions verified
    concretely with exit codes and file hashes, (I) BUILD_LOG accuracy;
    write `reviews/M2-review.md`; edit no implementation file; use the
    scratchpad for experiments; do not soften the verdict; state
    independence honestly; end with one `VERDICT:` line.
-   **Agent response / summary:** Pending at time of writing.
-   **Files created or modified:** `reviews/M2-review.md` (by reviewer).
-   **Commands actually run / Tests actually run:** Recorded by the
    reviewer in its report.
-   **Observed results:** See `reviews/M2-review.md`.
-   **Problems / deviations:** Same independence limitation as Prompt 3
    --- separate agent and fresh context, but same session and machine.
-   **Human review decision:** Pending
-   **Acceptance criteria met:** See `reviews/M2-review.md`
-   **Follow-up prompt reference:** Gate decision in `BUILD_LOG.md`.

### Prompt 5 --- M2 condition fixes + M3 build (builder, same session)

-   **Date/time:** 2026-11-16
-   **Tool/model:** Claude Code (Opus 5 / Opus 5.5)
-   **Milestone:** M2 remediation, then M3
-   **Prompt purpose:** Continuation of the autonomous loop under
    Prompt 2; no new human prompt was issued. Recorded for completeness
    because real work happened.
-   **Agent response / summary:** Recorded M2's verdict, fixed C-1, C-3,
    C-6, C-7, C-8 immediately and tracked C-2/C-4/C-5. Re-verified the
    live Xero Payments *and* Invoices documentation to resolve the
    PUT-vs-POST question with evidence, then implemented M3 on branch
    `feat/retry-safe-create-payment`.
-   **Files created or modified:** `pfMCP/src/servers/xero/main.py`
    (+218/-12, on a branch); `tests/test_create_payment_tool.py` (new);
    `tests/test_fault_server.py`, `mocks/fault_server.py`,
    `pytest.ini` (new), `BUILD_LOG.md`, `STATUS.md`.
-   **Commands actually run:** `git checkout -b
    feat/retry-safe-create-payment`; prototype suite; pfMCP xero
    regression suite; `git diff --stat`.
-   **Tests actually run:** prototype suite **46 passed**; pfMCP xero
    mock suite **20 passed / 37 failed**, byte-identical to the M0
    baseline (pre-existing helper bug).
-   **Observed results:** `PUT` + `Idempotency-Key` sent; ambiguous
    outcomes return structured `OUTCOME_UNKNOWN` instead of `"Error: "`;
    same-key retry leaves exactly one payment; expired window returns
    `RECONCILIATION_REQUIRED`.
-   **Problems / deviations:** Four of my own test assertions were wrong
    on first run (case-sensitivity, and schema-level rejection
    preceding handler validation). Fixed the assertions, not the
    implementation, and recorded why.
-   **Human review decision:** Deferred to final handover per Prompt 2.
-   **Acceptance criteria met:** Pending the M3 reviewer.
-   **Follow-up prompt reference:** Prompt 6.

### Prompt 6 --- Independent M3 quality-gate review (sent to reviewer agent)

-   **Date/time:** 2026-11-16
-   **Tool/model:** Claude Code `Agent` tool, `general-purpose`
    subagent, fresh context
-   **Milestone:** M3
-   **Prompt purpose:** Independent verdict on the change that modifies
    payment-creating code.
-   **Exact prompt sent:** Long reviewer brief; substance: read
    `QUALITY_GATE_AGENT.md`, `BUILD_PLAN_peakflo.md` (§4.3, §5, §6, §7,
    §8, §10 M3, §12, §13), `BUILD_LOG.md` (M3 as claims, plus M0 §6 and
    the M2 verdict) and `reviews/M2-review.md`; inspect the actual
    branch diff hunk by hunk plus the new tests; run the prototype suite
    and the pfMCP regression suite against the stated M0 baseline of
    20 passed / 37 failed; then probe (A) **re-verify the PUT-vs-POST
    contract against live Xero docs rather than trusting the project's
    own transcription**, (B) retry semantics in the code --- no derived
    or per-attempt keys, `reference` never conflated with the key,
    ambiguous never reported as definite or vice versa, **including
    empirically checking httpx's exception hierarchy so that
    `ConnectError`/`ConnectTimeout` are classified as definite**, and
    that the tool never advises a new key after ambiguity, (C) that the
    old `"Error: "` path is genuinely bypassed, (D) **mutation testing**
    of the two most critical behaviours in a scratch copy,
    (E) scope/minimality incl. that the `call_xero_api` change cannot
    affect the other ~48 tools, (F) whether the breaking required-key
    decision is documented honestly, (G) safety absolutes,
    (H) BUILD_LOG accuracy down to diff size and test counts, (I) that
    M2's condition C-2 is satisfied; write `reviews/M3-review.md`; edit
    no implementation file, no commits or branch changes; do not soften
    the verdict; end with one `VERDICT:` line.
-   **Agent response / summary:** Pending at time of writing.
-   **Files created or modified:** `reviews/M3-review.md` (by reviewer).
-   **Observed results:** See `reviews/M3-review.md`.
-   **Problems / deviations:** Same independence limitation as Prompts 3
    and 4.
-   **Human review decision:** Pending
-   **Acceptance criteria met:** See `reviews/M3-review.md`
-   **Follow-up prompt reference:** Gate decision in `BUILD_LOG.md`.

### Prompt 7 --- M4 build (builder, continuation of the autonomous loop)

-   **Date/time:** 2026-11-17
-   **Tool/model:** Claude Code (Opus 5.5)
-   **Milestone:** M4
-   **Prompt purpose:** Raj's instruction "Yes, start M4". Continuation
    of the loop established in Prompt 2.
-   **Agent response / summary:** Implemented the atomic per-key
    reservation (C-4), explicit empty-key handling (C-2) and margin
    assertions (C-5); built the M4 test matrix; found and fixed a real
    defect in M3's reconciliation path.
-   **Files created or modified:** `tests/test_m4_integration.py` (new);
    `mocks/fault_server.py`, `mocks/MOCK_CONTRACT.md`,
    `tests/test_create_payment_tool.py`,
    `pfMCP/src/servers/xero/main.py` (+47, uncommitted).
-   **Commands actually run:** prototype suite (twice), pfMCP xero
    regression suite, two mutation experiments on scratch copies.
-   **Tests actually run:** prototype suite **94 passed** (79.45 s and
    82.22 s); pfMCP regression **20 passed / 37 failed**, the M0
    baseline.
-   **Observed results:** The expiry test exposed that
    `RECONCILIATION_REQUIRED` only fired *after* an ambiguous failure,
    so a stale key was still sent and committed a second payment; the
    guard is now pre-flight and sends nothing. The first concurrency
    mutation **survived** (5 passed with the reservation removed), so
    the tests were proving nothing; after adding a deterministic
    race-window seam the same mutation produces 6 payments instead of 1.
-   **Problems / deviations:** One assertion in the M3 test file had to
    be updated because the behaviour it described was improved, not
    because the test was wrong; recorded in the test itself.
-   **Human review decision:** Deferred to final handover.
-   **Acceptance criteria met:** Pending the M4 reviewer.
-   **Follow-up prompt reference:** Prompt 8.

### Prompt 8 --- Independent M4 quality-gate review (sent to reviewer agent)

-   **Date/time:** 2026-11-17
-   **Tool/model:** Claude Code `Agent` tool, `general-purpose`
    subagent, fresh context
-   **Milestone:** M4
-   **Prompt purpose:** Independent verdict on the M4 tests and the
    conditions they were meant to close.
-   **Exact prompt sent:** Long reviewer brief; substance: read the
    policy, the plan (§7, §9, §10 M4), `BUILD_LOG.md` as claims, and the
    M2/M3 reviews for the conditions M4 had to close; inspect the
    uncommitted pfMCP diff and the new tests; run the prototype suite
    repeatedly watching for flakiness in the threaded tests, plus the
    pfMCP regression against the 20/37 baseline; then probe (A) both
    halves of the claimed defect-and-fix, including reverting the
    pre-flight guard in a scratch copy to confirm the danger was real,
    (B) **the concurrency claim hardest** --- reproduce the mutation,
    judge whether `commit_delay_seconds` is a legitimate test seam or an
    artificial one, and examine the reservation for deadlocks, lost
    wakeups, a raising owner, `reset()` with waiters pending, waiter
    timeouts and fingerprint mismatch, (C) general test quality via
    further mutations, (D) the plan's ~13 required M4 cases one by one
    against actual test names, (E) whether the deliberate double-pay
    limitation is represented honestly or buried, (F) scope and safety,
    (G) BUILD_LOG accuracy including the 94-passed, 1-vs-6 and +47-line
    claims; write `reviews/M4-review.md`; edit nothing else; restore any
    scratch mutation byte-identically; do not soften the verdict; end
    with one `VERDICT:` line.
-   **Agent response / summary:** Pending at time of writing.
-   **Files created or modified:** `reviews/M4-review.md` (by reviewer).
-   **Observed results:** See `reviews/M4-review.md`.
-   **Problems / deviations:** Same independence limitation as earlier
    reviews.
-   **Human review decision:** Pending
-   **Acceptance criteria met:** See `reviews/M4-review.md`
-   **Follow-up prompt reference:** Gate decision in `BUILD_LOG.md`.

------------------------------------------------------------------------

## Milestone prompt checklist

Use this checklist as a reminder. It is not evidence that a prompt has
been sent.

-   [x] M0 --- Inspect repository, current code path, API contract, and
    tests; make no changes.
-   [x] M1 --- Build isolated baseline timeout/retry reproduction.
-   [x] M2 --- Build local fault-injection mock and tests.
-   [x] M3 --- Implement minimal verified Xero payment tool changes.
-   [x] M4 --- Add integration and regression tests.
-   [ ] M5 --- Run before/after demonstration and save actual results.
-   [ ] M6 --- Run controlled LLM-agent retry evaluation, if approved.
-   [ ] M7 --- Complete README and demo materials.
-   [ ] M8 --- Perform final engineering review.

## Required end-of-milestone record

At the end of each milestone, ensure `BUILD_LOG.md` records: 1. What was
attempted. 2. Which files changed. 3. Commands executed. 4. Tests
executed and their actual results. 5. Acceptance criteria met/not met.
6. Known limitations and unresolved questions. 7. The user's review
decision. 8. The next milestone proposed, without starting it
automatically.

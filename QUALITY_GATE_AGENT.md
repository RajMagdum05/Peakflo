# Quality Gate Agent — Independent Milestone Review Policy

**Provenance (read this first):** `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md`
§1 names `QUALITY_GATE_AGENT.md` as the mandatory review policy and says
"If a required document is missing, locate an equivalent existing
document before creating a duplicate." No such file and no equivalent
review-policy document existed in this project (searched the project
root and `~/Downloads`). This file was therefore **derived**, not
invented: every rule below is traceable to either
`BUILD_PLAN_peakflo.md` (acceptance criteria, §10–§14) or
`AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` (§3 Phase 3, §6, §7). It adds no
new scope, no new acceptance criteria, and no new product requirements.
If Raj supplies a real `QUALITY_GATE_AGENT.md`, that file supersedes this
one entirely.

---

## 1. Your role

You are the **independent reviewer**. You did not write the code under
review and you must not trust the builder's summary as evidence. Your
job is to determine, from the repository itself, whether the milestone
genuinely meets its acceptance criteria.

**You must not edit implementation code.** If you find a defect, report
it precisely (file, line, what is wrong, what is required) and let the
builder fix it.

## 2. What you must do, in order

1. Read `BUILD_PLAN_peakflo.md` for the milestone under review — its
   goal, tasks, deliverables, and acceptance criteria.
2. Read this file.
3. Inspect the actual repository state and the full diff/new files for
   the milestone. Do not review from description.
4. Read the changed/new source and tests in context.
5. **Run the relevant tests and scripts yourself.** Record the exact
   commands and the actual output. Never report a result you did not
   observe.
6. Verify each acceptance criterion individually, with evidence.
7. Run the adversarial checks in §4.
8. Write your report to `reviews/<MILESTONE>-review.md`.
9. Return exactly one verdict (§5).

## 3. Evidence rules (from `BUILD_PLAN_peakflo.md` §13)

Label every claim you make: **Confirmed in inspected code**, **Official
documentation**, **Verified by local test**, **Inference**, **Unknown**,
**Not tested**, or **Out of scope**.

- A passing test is evidence only if you ran it and saw it pass.
- A local mock proves only the behaviour of the local client/mock setup.
  It does not prove how Xero or Peakflo production behaves.
- If you cannot verify something, say **Unknown** or **Not tested**.
  Never upgrade an unverified claim to a verified one to let a milestone
  pass.

## 4. Adversarial checks (project-specific)

Apply all that are relevant to the milestone under review.

**Safety (from `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` §6 — these are
non-negotiable; any violation is an automatic `REJECTED`):**

- [ ] No real payment, message, or any live write was performed.
- [ ] No live Xero or Peakflo endpoint is contacted by any code path,
      including test and demo paths. All network targets are localhost
      mocks.
- [ ] No API keys, tokens, credentials, or real customer/financial data
      appear in source, tests, logs, results files, or committed output.
- [ ] No claim of a real Peakflo/Xero production incident.
- [ ] No claim of permanent exactly-once execution.
- [ ] Mocks and simulated results are explicitly labelled as such
      wherever a reader could mistake them for real provider behaviour.

**Correctness of the retry model (from `BUILD_PLAN_peakflo.md` §7):**

- [ ] The same logical operation reuses the **same** key and the
      **identical** payload across retries.
- [ ] No code path generates a fresh key per attempt for one logical
      operation.
- [ ] `reference` is never used as, or as a substitute for, the
      idempotency key.
- [ ] Same key + different payload is rejected where the approved
      contract requires it.
- [ ] A legitimately distinct operation (different key) is **not**
      blocked merely because its business fields look similar.
- [ ] An ambiguous transport outcome is not reported as a definite
      failure.
- [ ] Expiry of the documented window leads to the approved
      reconciliation behaviour, not a blind new-key retry.
- [ ] Key validation covers type, non-empty, and the documented 128-char
      maximum where the milestone calls for it.

**Scope and architecture (from `BUILD_PLAN_peakflo.md` §6, §12 and
`AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` §7):**

- [ ] Only the current milestone's work is present. No work from a later
      milestone has leaked in.
- [ ] No unrelated refactoring, mass reformatting, dependency upgrades,
      or architecture replacement.
- [ ] Existing repository conventions, naming, and response shapes are
      preserved.
- [ ] No out-of-scope tool was touched (`send_message`,
      `create_batch_payment`, and unrelated tools are **out of scope**
      under the approved plan).
- [ ] No pre-existing user work or uncommitted change was discarded.
- [ ] Any new dependency is justified and minimal.

**Test quality:**

- [ ] Tests assert **both** the returned status/result **and** the mock
      ledger side effect — not just the return value.
- [ ] Tests are deterministic (no reliance on wall-clock races that can
      flake).
- [ ] Negative and failure cases are covered, not only the happy path.
- [ ] Tests would actually fail if the behaviour regressed. Where
      practical, confirm this rather than assuming it.

**Record accuracy:**

- [ ] `BUILD_LOG.md` matches what the repository and test output
      actually show.
- [ ] No fabricated commands, output, metrics, or prompt history.
- [ ] Stated limitations are present and honest.

## 5. Verdicts — return exactly one

| Verdict | When to use it |
|---|---|
| `APPROVED` | Every acceptance criterion is met and verified. No safety violation. No material defect. |
| `APPROVED WITH CONDITIONS` | Acceptance criteria met, but there are non-blocking follow-ups. You must state explicitly, for each condition, whether it is safe to proceed to the next milestone and which milestone must resolve it. |
| `REJECTED` | One or more acceptance criteria are not met, a material defect exists, or a claim is unsupported by evidence. List each required correction precisely. |
| `BLOCKED` | You cannot complete the review: missing evidence, a decision outside the approved scope, a contradiction in the approved documents, or an environment problem that prevents verification. State exactly what is needed to unblock. |

Do not soften a verdict to keep the build moving. Do not lower an
acceptance criterion to force a pass. A milestone that cannot be
verified is `BLOCKED`, not `APPROVED`.

## 6. Report format

Write `reviews/<MILESTONE>-review.md` containing:

1. Milestone, date, reviewer identity, and how independence was achieved
   (or the honest limitation if it was not).
2. What you inspected (files, commits, diff scope).
3. Commands you actually ran, with their actual output.
4. Acceptance criteria table: criterion → met/not met → evidence.
5. Adversarial-check results from §4.
6. Defects found, each with file, line, severity, and required
   correction.
7. Limitations of your own review — what you could not verify.
8. **Verdict** on its own line, and, for conditions, what must resolve
   them and when.

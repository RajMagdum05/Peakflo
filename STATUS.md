# STATUS — Retry-Safe Xero Payment Execution for MCP Agents

**Last updated:** 2026-11-16
**Mode:** Autonomous build with independent reviewer gating
(`AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md`). Raj reviews the completed
project and final handover.

---

## Current state

| | |
|---|---|
| **Current milestone** | M4 — Automated integration & regression tests |
| **M4 build** | Complete — 20 new tests; C-2, C-4, C-5 closed; a real M3 defect found and fixed |
| **M4 review** | Dispatched to an independent reviewer agent; verdict pending |
| **Last verdict** | M3 — `APPROVED WITH CONDITIONS` (`reviews/M3-review.md`) |
| **Next action** | Apply the gate rule to the M4 verdict; on approval, begin M5 |
| **Blockers** | None |
| **Latest test status** | Prototype suite **94 passed** (run twice, no flake). pfMCP xero regression **20 passed / 37 failed — identical to the M0 baseline**, all from the pre-existing helper bug (BUILD_LOG M0 §7) |

## Milestone progress (authoritative plan: `BUILD_PLAN_peakflo.md`)

| Milestone | State | Verdict | Report |
|---|---|---|---|
| M0 — Repository & environment inspection | Complete | no gate existed yet (pre-autonomy) | `BUILD_LOG.md` §M0 |
| M1 — Baseline duplicate-effect reproduction | Complete | **APPROVED WITH CONDITIONS** | `reviews/M1-review.md` |
| M2 — Fault-injection mock Xero API | Complete | **APPROVED WITH CONDITIONS** | `reviews/M2-review.md` |
| M3 — Minimal Xero tool implementation | Complete | **APPROVED WITH CONDITIONS** | `reviews/M3-review.md` |
| M4 — Automated integration & regression tests | Built | **pending** | `reviews/M4-review.md` (being written) |
| M5 — Before/after demonstration | **Next** | — | — |
| M6 — AI-agent retry evaluation | Not started | — | — |
| M7 — Documentation & demo | Not started | — | — |
| M8 — Final engineering review | Not started | — | — |

## Open conditions carried forward (from the M1 gate)

| # | Condition | Due | State |
|---|---|---|---|
All seven were addressed during M2 and verified by the builder; the M2
reviewer has been asked to confirm each one independently.

| # | Condition | State | Evidence |
|---|---|---|---|
| D-1 | Stall-vs-timeout margin unchecked | **fixed** | `--delay 1` → exit 3; `--delay 6.5` → exit 0 |
| D-2 | Repro exits 0 when nothing reproduced | **fixed** | returns exit 1; D-1 intercepts the main cause first |
| D-3 | `*_latest.json` rewritten by every run | **fixed** | non-canonical run left the file byte-identical (md5) |
| D-4 | No loopback assertion before mutating `XERO_API_BASE` | **fixed** | `assert_loopback` refuses `https://api.xero.com` |
| D-5 | Raw `ConnectionAbortedError` tracebacks on stderr | **fixed** | canonical run stderr = 123 bytes, 0 tracebacks |
| D-6 | Timing range read as an invariant | **fixed** | corrected to ~5.02–5.15 s, marked non-invariant |
| D-7 | `attempt_index` computed outside the lock | **fixed** | now assigned under the lock in both mocks |

## Open conditions carried forward

| # | Condition | Due | State |
|---|---|---|---|
| ~~F-5~~ | M3 change uncommitted | — | **CLOSED** — committed as `eb4685f` on Raj's authorisation |
| F-8 | Success path returns the raw Xero payload rather than §8's `{"status":"SUCCESS"…}` shape | — | **declared decision**, Raj may overrule |
| ~~C-2~~ | Empty-string key — mock side | — | **CLOSED** in M4 |
| ~~C-4~~ | Non-atomic per-key reservation | — | **CLOSED** in M4 — race now demonstrated (1 vs 6 payments) and fixed |
| ~~C-5~~ | Unasserted timeout-vs-stall margins | — | **CLOSED** in M4 |

Closed: C-1, C-3, C-6, C-7, C-8 (during M3); F-1, F-2, F-3, F-6, F-7
(after the M3 gate). F-4 noted and now covered by a test.

## Latest measured result (local simulation only)

Driving pfMCP's real, unmodified `call_xero_api()` against a local mock
on 127.0.0.1 — reproduced independently by the reviewer:

| scenario | attempts | ledger committed | duplicates |
|---|---|---|---|
| control_ok | 1 | 1 | 0 |
| baseline_timeout_retry | 2 | **2** | **1** |

One intended payment became two ledger entries. **This is a local mock,
not Xero.** It is not evidence of any real duplicate payment and not
evidence of a Peakflo production incident.

`repro/results/m1_baseline_latest.json` holds the most recent
**canonical** run; non-canonical runs no longer overwrite it. Each
result file embeds its own `invocation` block (argv, real client read
timeout, stall margin), so read provenance from the file rather than
from any filename quoted in prose. An earlier version of this line named
a specific run and was wrong — the M2 reviewer proved it by hashing the
bytes. (M2 review C-6.)

## Open decisions Raj may want to reverse

1. **Which build plan is authoritative.** `BUILD_PLAN_peakflo.md`
   (project root, marked approved, more restrictive) was chosen over
   `~/Downloads/peakflo-v2-gap-and-build-plan-2026-11-16.md`. Under the
   chosen plan, `send_message` and `create_batch_payment` are **out of
   scope** and the idempotency key is **caller-supplied, not derived**.
   Reasoning: `BUILD_LOG.md` → "Governance change" → Conflict 2.
   *Cheap to reverse now; expensive after M3.*
2. **Autonomous vs. stop-after-each-milestone.** `PROJECT_GUIDE.md` says
   stop after every milestone; the orchestrator prompt says run
   autonomously under reviewer gating. The orchestrator prompt was
   followed, per Raj's direct instruction. Conflict 1, same section.
3. **PUT vs POST for payment creation.** Official Xero docs: `PUT
   /Payments` creates, `POST /Payments` deletes/reverses. Inspected
   pfMCP code uses `POST` to create. Resolution deferred to M3 by the
   approved plan. See `BUILD_LOG.md` M0 §6.

## Review independence — honest limitation

The reviewer is a separate agent with a fresh context that reads and
executes independently, but it runs inside the same session, machine and
checkout as the builder. That is the strongest separation available
here. It is **not** an independent environment, an independent party, or
a substitute for human review — relevant because this project concerns
payment-safety behaviour.

## Safety posture

- No live Xero or Peakflo endpoint contacted at any point.
- No real payment or message created.
- All traffic to 127.0.0.1 mocks with fake tokens.
- No credentials or secrets in this project folder (reviewer grepped
  `repro/results/` and confirmed).
- `pfMCP/` working tree: **clean** (generated from `git status`, not written by hand — this line has
  been wrong in both directions before).
- Branch `feat/retry-safe-create-payment` is **2 commits** ahead of
  `main`:
  - `dd8cc75 fix(xero): refuse ambiguous operationStartedAt; guard stale keys pre-flight`
  - `eb4685f feat(xero): make create_payment retry-safe with idempotency key`
- **Nothing has been pushed.** No branch here has an upstream, and no PR
  has been opened against `peakflo/pfMCP`.
- Parent repo, `Peakflo/` path: `?? Peakflo/`

## Record locations

`BUILD_LOG.md` (milestone detail) · `prompts_for_peakflo.md` (prompt
history) · `reviews/` (independent review reports) ·
`QUALITY_GATE_AGENT.md` (review policy) · `repro/results/`
(machine-readable run output).

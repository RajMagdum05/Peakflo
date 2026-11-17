# M4 — re-review after repair (round 2)

**Milestone:** M4 — Automated integration and regression tests
**Date:** 2026-11-17
**Reviewer:** independent quality-gate agent, round 2 (separate agent
from the builder and from the round-1 reviewer; wrote none of the code
under review)
**Previous verdict:** `REJECTED` — `reviews/M4-review.md` (preserved
unmodified; this is a new file)
**Policy applied:** `QUALITY_GATE_AGENT.md` §4 (adversarial checks), §5
(verdicts), §6 (report format), against `BUILD_PLAN_peakflo.md` §7, §10
M4, §12, §13.

**Scope of this review.** This is a re-review, not a review from
scratch. Round 1's ten findings are the checklist. I re-ran the suites,
re-derived every number myself, re-applied each mutation on scratch
copies, and added two mutations and two end-to-end probes of my own
design. I did not re-verify round 1's conclusions that nothing here
depended on (for example its deadlock/lost-wakeup reading of the
reservation, or the Xero documentation M3 established).

---

## 1. How independent this review was — honestly

- I did not write, and have not edited, any file under review. I read
  the repository, the committed diff, and the test sources; every number
  below came from a command I ran in this session.
- **Not an independent environment or an independent party.** Same
  machine, same Windows 11 checkout, same CPython/`pfMCP/.venv` as the
  builder and as round 1. The venv path, the two suite commands, the
  commit SHA to inspect, and round 1's finding list were handed to me.
  My own contribution is the execution, the mutations, the probes, and
  the judgement. This is no substitute for human review, which matters
  because the subject is payment-safety behaviour.
- **I did not take the builder's `BUILD_LOG.md` claims as evidence.**
  Each one in §8 was checked against the repository or re-measured.
- Everything that could change behaviour was done on a **scratch copy**
  at
  `<scratchpad>`
  (copies of `tests/`, `mocks/`, `pytest.ini`, `pfMCP/src/`). Every
  mutated file was restored from the project copy and verified
  byte-identical with `cmp`. The only project file this review writes is
  `reviews/M4-review-2.md`.
- **I did not run `repro/retry_dup_repro.py`.** `repro/results/` mtimes
  are all 2026-11-16 and unchanged, `m1_baseline_latest.json` included.
- No implementation or test file was edited, nothing was committed, no
  branch was changed. At the end of this review
  `git -C pfMCP status --short` is **empty** and the parent repo shows
  exactly the same working set as at the start (` M Composio`,
  ` M Emergent/README.md`, ` M Emergent/pyproject.toml`, and the four
  untracked `Emergent/*` paths plus `?? Peakflo/`).
- **Live Xero behaviour remains Unknown / Not tested.** Everything
  labelled *verified by local test* proves the behaviour of this
  client/mock pair only, per `BUILD_PLAN_peakflo.md` §13.

## 2. What I inspected

| Artifact | Scope |
|---|---|
| `git -C pfMCP diff eb4685f..HEAD` (commit `dd8cc75`) | read in full — 1 file, +113/−20 |
| `git -C pfMCP log -1 --format=%B dd8cc75` | commit message read in full, checked against the diff |
| `pfMCP/src/servers/xero/main.py` | `parse_operation_started_at` (:220-262), `idempotency_window_may_have_expired` (:265-276), schema (:1271-1283), handler (:3227-3290, :3311, :3333, :3367), outer handler (:4576-4578) |
| `tests/test_m4_integration.py` | 553 lines, read in full (34 collected cases) |
| `tests/test_create_payment_tool.py` | read in full; diffed against `2c52b05` |
| `tests/test_fault_server.py` | diffed against `2c52b05` (M4-4 repair) |
| `mocks/fault_server.py` | `INFLIGHT_WAIT_SECONDS`, `MockState`, `begin_operation` / `finish_operation`, `_mutating_payment`, `_process`; diffed against `2c52b05` |
| `mocks/MOCK_CONTRACT.md` | diffed against `2c52b05` |
| `BUILD_LOG.md` M4 (1133–1351), including the repair section (1259–1351) | every claim cross-checked |
| `STATUS.md` | safety posture, lines 116–142 |
| `reviews/M4-review.md` | read in full as the checklist |
| `BUILD_PLAN_peakflo.md` §7, §10 M4, §12, §13 | standards applied |

**Diff availability has improved only for pfMCP.** `dd8cc75` makes the
tool change reviewable from version control. The prototype's own M4
files are still **untracked**: `git ls-files Peakflo` in the parent repo
returns nothing, `git status` shows `?? Peakflo/`, and `2c52b05`
(branch `peakflo-retry-safe`) contains only the M3-era
`mocks/fault_server.py` (484 lines) and no `tests/test_m4_integration.py`
at all. I therefore reconstructed the prototype delta by diffing the
working tree against `2c52b05`, exactly as round 1 had to. See §7,
finding **R-1**.

## 3. Commands I actually ran, with actual output

### 3.1 Prototype suite — twice on the project, once on the scratch copy

```
$ cd R:\Internship_Outreach_prototype\Peakflo
$ pfMCP/.venv/Scripts/python.exe -m pytest tests/ -p no:cacheprovider -q
108 passed in 81.79s (0:01:21)        # run 1
108 passed in 80.32s (0:01:20)        # run 2

$ cd <scratchpad>\rev2\proto
$ ...python.exe -m pytest tests/ -p no:cacheprovider -q
108 passed in 79.35s (0:01:19)        # unmutated scratch copy, self-contained
```

Collected cases per file (sum = 108):

```
tests/test_m4_integration.py: 34
tests/test_create_payment_tool.py: 19
tests/test_fault_server.py: 27
tests/test_outcome_classifier.py: 28
```

### 3.2 pfMCP regression — exactly the M0 baseline

```
$ cd R:\Internship_Outreach_prototype\Peakflo\pfMCP
$ .venv/Scripts/python.exe -m pytest tests/servers/xero/test_accounting_expansion.py \
    tests/servers/xero/test_attachment_download.py tests/servers/xero/test_get_invoice_pdf.py \
    tests/servers/xero/test_update_invoice_status.py tests/servers/xero/test_imda_tools.py \
    -p no:cacheprovider -q
37 failed, 20 passed in 4.90s
```

**20 passed / 37 failed = the M0 baseline exactly.** *Verified by local
test.* I did not re-bisect the cause; round 1 read it from a traceback
(the pre-existing `_invoke()` credential-patch bug recorded in M0).

### 3.3 Git state

```
$ git -C pfMCP log --oneline -3
dd8cc75 fix(xero): refuse ambiguous operationStartedAt; guard stale keys pre-flight
eb4685f feat(xero): make create_payment retry-safe with idempotency key
78cda6e chore(stage): keep one warm pf-mcp instance with 1 vCPU (#226)

$ git -C pfMCP diff --stat eb4685f..HEAD
 src/servers/xero/main.py | 133 ++++++++++++++++++++++++++++++++++++++++-------
 1 file changed, 113 insertions(+), 20 deletions(-)

$ git -C pfMCP status --short      # (empty)
$ git -C pfMCP rev-list --count main..HEAD
2
```

## 4. (A) M4-1 — the High-severity timezone defect

### 4.1 In code

`parse_operation_started_at` (main.py:220-262) returns `None` only for an
absent value and otherwise **raises `ValueError`** unless the value is a
non-empty string that `datetime.fromisoformat` accepts *and* that carries
`tzinfo`. `idempotency_window_may_have_expired` (:265-276) now takes a
`datetime | None` and can no longer be reached with ambiguous input; its
docstring says so. The parse is called at :3232, **before** the payload
is built and before the pre-flight window check at :3252, and alongside
`validate_idempotency_key` under the comment "Definite, pre-flight
failures: nothing has been sent yet". *Confirmed in inspected code.*

### 4.2 By direct execution of the helper

My own probe (`probe_helper.py`, scratchpad), 21 inputs:

```
None (absent)                -> accepted parsed=None expired=False
naive ISO                    -> REJECTED ValueError: must include a UTC offset ...
naive space-sep              -> REJECTED ValueError: must include a UTC offset ...
bare date                    -> REJECTED ValueError: must include a UTC offset ...
junk                         -> REJECTED ValueError: not a valid ISO-8601 timestamp: 'junk'
empty                        -> REJECTED ValueError: must be a non-empty ISO-8601 ...
whitespace                   -> REJECTED ValueError: must be a non-empty ISO-8601 ...
int epoch                    -> REJECTED ValueError: must be a non-empty ISO-8601 ...
float                        -> REJECTED ValueError: must be a non-empty ISO-8601 ...
bool True                    -> REJECTED ValueError: must be a non-empty ISO-8601 ...
list                         -> REJECTED ValueError: must be a non-empty ISO-8601 ...
aware Z now                  -> accepted expired=False
aware +05:30 now             -> accepted expired=False
aware -08:00 now             -> accepted expired=False
aware -08:00 stale 2h        -> accepted expired=True
aware +05:30 stale 2h        -> accepted expired=True
aware future +1h             -> accepted expired=False
aware exactly 360s old       -> accepted expired=True
aware 359s old               -> accepted expired=False
lowercase z                  -> REJECTED ValueError: not a valid ISO-8601 timestamp
padded aware                 -> accepted expired=False
```

Every rejection round 1 demanded is present; both offset directions are
accepted; staleness is detected correctly in both directions; the 360 s
boundary is inclusive (`>=`). *Verified by local test.*

### 4.3 The two reproduced failure modes, end-to-end, read off the ledger

My own probe (`probe_e2e.py`) drives the **real tool** through
`server.dispatch(CallToolRequest(...))` against a fresh mock per case
and prints `state.snapshot()`, not the returned JSON:

```
--- (i) seconds-old FIRST payment, UTC-08:00 caller (must SEND)
    operationStartedAt = '2026-11-16T22:16:21.355681-08:00'
    returned: {"Payments": [{"PaymentID": "007d377a-...", ...
    LEDGER payment_count=1 attempt_count=1

--- (ii) genuinely stale key (2h), UTC+05:30 caller (must BLOCK)
    operationStartedAt = '2026-11-17T09:46:22.392834+05:30'
    returned: {"status": "RECONCILIATION_REQUIRED", ... "No request was sent. ..."
    LEDGER payment_count=0 attempt_count=0

--- (iii) naive local timestamp (must be DEFINITE failure, send nothing)
    returned: Error: operationStartedAt must include a UTC offset so its age is
              unambiguous; got '2026-11-17T11:46:22.906439'. Append 'Z' for UTC, ...
    LEDGER payment_count=0 attempt_count=0

--- (iv) int epoch       -> Error: Input validation error: 1763376000 is not of type 'string'
    LEDGER payment_count=0 attempt_count=0
--- (v) bare date        -> Error: operationStartedAt must include a UTC offset ...
    LEDGER payment_count=0 attempt_count=0
--- (vi) absent          -> sends (the documented gap)   payment_count=1 attempt_count=1
--- (vii) stale, UTC-08:00  -> RECONCILIATION_REQUIRED   payment_count=0 attempt_count=0
--- (viii) fresh, UTC+05:30 -> sends                     payment_count=1 attempt_count=1
--- (ix) future-dated +1h   -> sends                     payment_count=1 attempt_count=1
```

**Both failure modes round 1 reproduced are gone.** (i) a legitimate
seconds-old first payment from a UTC-negative zone is **not** refused
(`payment_count=1`); (ii) a genuinely stale key from a UTC-positive zone
is **still blocked** and transmits nothing (`attempt_count=0`).
*Verified by local test.*

**Rejection is a definite failure that transmits nothing.** `attempt_count`
is 0 on every rejected case — the mock never saw a request. The
`ValueError` surfaces through the tool's existing outer handler
(main.py:4576-4578) as `Error: <message>`, the same shape
`validate_idempotency_key` failures already used, and never as
`OUTCOME_UNKNOWN`. Non-string values are additionally stopped by MCP
schema validation before the handler runs; the helper rejects them too,
so the guard does not depend on the schema layer.

### 4.4 Mutation: restore the old "assume UTC" behaviour

Scratch copy, `parse_operation_started_at` replaced with the pre-repair
semantics mapped onto the new signature (lenient `None` for non-strings
and unparseable text, `replace(tzinfo=timezone.utc)` for naive):

```
$ ...python.exe -m pytest tests/ -p no:cacheprovider -q
FAILED tests/test_create_payment_tool.py::test_unparseable_start_time_is_rejected_outright
FAILED tests/test_m4_integration.py::test_ambiguous_start_time_is_rejected_and_sends_nothing[2026-11-17T09:30:00]
FAILED tests/test_m4_integration.py::test_ambiguous_start_time_is_rejected_and_sends_nothing[2026-11-17 09:30:00]
FAILED tests/test_m4_integration.py::test_ambiguous_start_time_is_rejected_and_sends_nothing[junk]
FAILED tests/test_m4_integration.py::test_ambiguous_start_time_is_rejected_and_sends_nothing[]
FAILED tests/test_m4_integration.py::test_ambiguous_start_time_is_rejected_and_sends_nothing[   ]
6 failed, 102 passed in 85.70s (0:01:25)
```

**Killed, by six tests.** The fix is pinned, not merely present.
Scratch file restored and `cmp`-verified byte-identical.

**One precision gap in that parametrize, though.** Three of its eight
cases pass *under the mutation too*, so they discriminate nothing:

```
$ ...pytest "...[2026-11-17]" "...[1763376000]" "...[12.5]" -q      # mutated scratch
3 passed in 5.17s
```

`1763376000` and `12.5` are stopped by schema validation in both
versions. `"2026-11-17"` passes spuriously because the old assume-UTC
reading makes midnight UTC look stale, so the tool returns
`RECONCILIATION_REQUIRED` — whose `retryGuidance` happens to contain the
substring `"operationStartedAt"`, satisfying
`assert ("operationStartedAt" in text) or ...`, while `attempt_count` is
0 either way. Hard-blocking a bare date is the *wrong* behaviour that
round 1 named, and this test cannot tell it from the right one. Recorded
as **R-4** (Low).

### 4.5 Gaps in the test set round 1 asked for

Round 1's required correction for M4-1 included tests for "naive,
date-only, future-dated and non-string values, plus the case where the
window is crossed while the request is in flight". Naive, date-only and
non-string are covered. **Future-dated and window-crossed-in-flight are
not** — no test in the suite exercises either.

I probed both myself:

- **future-dated** (case ix above): accepted, `expired=False`, the
  payment is sent. Defensible (clock skew should not block a payment)
  but undeclared and untested; a bogus far-future stamp disables the
  guard as effectively as omitting the field.
- **window crossed in flight** (`probe_inflight.py`): 357 s-old stamp,
  `MODE_COMMIT_THEN_SLOW` 7.0 s, so the tool's implicit 5 s client
  timeout fires after the window has elapsed.

```
returned: {"status": "RECONCILIATION_REQUIRED",
           "operationId": "k-boundary-inflight",
           "message": "The request did not return a definite outcome and the
                       idempotency window may have expired. ..."
LEDGER payment_count= 1 attempt_count= 1
```

The post-failure branch at main.py:3311 handles it correctly, with
`requestSent: true`. **Behaviour correct; still unpinned by any test.**
Recorded as **R-3** (Low).

## 5. (B) The three previously-surviving mutations

Each re-applied by me on the scratch copy, then restored and
`cmp`-verified.

### M-C6 — in-flight fingerprint mismatch downgraded to a silent `wait`

`mocks/fault_server.py` `begin_operation`: the
`if pending.fingerprint != fingerprint: return "conflict", None` branch
deleted so an in-flight mismatch returns `"wait", pending`.

```
$ ...pytest tests/ -p no:cacheprovider -q
FAILED tests/test_m4_integration.py::test_concurrent_same_key_different_payload_is_rejected
1 failed, 107 passed in 82.71s (0:01:22)

$ ...pytest ...::test_concurrent_same_key_different_payload_is_rejected -q   (3x)
>       assert statuses == [200, 400], f"expected one 200 and one 400, got {statuses}"
E       assert [200, 200] == [200, 400]      # run 1
E       assert [200, 200] == [200, 400]      # run 2
E       assert [200, 200] == [200, 400]      # run 3
```

**KILLED, 3/3.** *Verified by local test.*

**The builder's reasoning about `commit_delay_seconds` is sound, and the
failure mode proves it.** The observed statuses are `[200, 200]`, not
`[200, 400]` — the conflicting caller was handed the owner's cached
`200`. That can only happen if the second request found the key **in
flight** rather than already cached: had it taken the cached-conflict
path, `begin_operation` would still have returned `"conflict"` (that
branch is untouched by the mutation) and the test would have passed
regardless. So the test genuinely targets the in-flight branch, and
`commit_delay_seconds = 0.5` is what holds it there. The seam remains
legitimate on the grounds round 1 established: default `0.0`
(fault_server.py:159), guarded at the single use site (`if
self.state.commit_delay_seconds:`), set only inside
`tests/test_m4_integration.py`, documented in the code and in
`MOCK_CONTRACT.md`, and applied identically to mutated and unmutated
code so it discriminates the property under test and nothing else.

Residual flake risk is small but real: the test depends on the second
request arriving inside a 0.5 s window. Two threads released from a
`threading.Barrier(2)` arrive within milliseconds, and 3/3 plus two full
unmutated suite runs showed no flake.

### M-C3 — publish the outcome after the artificial stall

`_process`, `MODE_COMMIT_THEN_SLOW`: `finish_operation` moved to after
`time.sleep(self.delay_seconds)`.

```
$ ...pytest tests/test_m4_integration.py -k "waiters_are_released or slow_commit or double_pay" -q
>       assert len(quick) == len(results) - 1, (
E       assert 0 == (4 - 1)
FAILED ...::test_concurrent_waiters_are_released_without_serving_the_full_stall
FAILED ...::test_expired_window_without_start_time_can_double_pay
```

```
$ ...pytest ...::test_concurrent_waiters_are_released_without_serving_the_full_stall -q   (3x)
E       assert 0 == (4 - 1)   1 failed in 6.51s
E       assert 0 == (4 - 1)   1 failed in 6.69s
E       assert 0 == (4 - 1)   1 failed in 6.90s
```

**KILLED, 3/3, by the test named for the property**, not incidentally.
The test now records each response's `elapsed` and requires
`len(results) - 1` of them to come back under `stall * 0.6`; under the
mutation zero do. *Verified by local test.* The incidental kill by
`test_expired_window_without_start_time_can_double_pay` still happens,
which is fine — it is no longer the only one.

### M-C7 — shrink the real mock-level margin

`tests/test_fault_server.py:36` `MOCK_STALL_SECONDS = 2.0` → `0.6`
(client timeout left at `0.5`):

```
$ ...pytest tests/test_fault_server.py::test_commit_then_slow_times_out_client_but_commits \
            tests/test_m4_integration.py::test_mock_level_margins_hold -q
>       assert MOCK_STALL_SECONDS - MOCK_CLIENT_TIMEOUT_SECONDS >= 1.0, (
E       assert (0.6 - 0.5) >= 1.0
FAILED tests/test_m4_integration.py::test_mock_level_margins_hold
1 failed, 1 passed in 4.27s
```

**KILLED.** The repair is exactly right in kind: the two values are now
module constants in `test_fault_server.py`, used by the behaviour tests
(`delay_seconds=MOCK_STALL_SECONDS`, `timeout=MOCK_CLIENT_TIMEOUT_SECONDS`)
and imported by the guard, so the guard reads the real numbers. The diff
against `2c52b05` is 18 lines and touches nothing else. *Verified by
local test.*

### My own mutation M-D1 — the other half of M4-4 is still vacuous

Round 1's M4-4 named **two** vacuous guards:
`test_mock_level_margins_hold` *and*
`test_tool_level_stall_exceeds_the_client_timeout`, which "hard-codes
`tool_stall = 7.0` the same way", with the required correction "Hoist
the stall/timeout values into module-level constants used by **both** the
behaviour tests and the guard". Only the mock-level half was done. The
tool-level stall is still the bare literal `delay_seconds=7.0` at eight
call sites (`test_m4_integration.py:316, 334, 358`;
`test_create_payment_tool.py:162, 189, 237, 253, 272`), while
`test_m4_integration.py:475` retypes `tool_stall = 7.0` and `:501`
retypes `INFLIGHT_WAIT_SECONDS > 7.0`.

So I shrank the real value and left the guards alone:

```
$ sed -i 's/delay_seconds=7\.0/delay_seconds=5.2/g' \
      tests/test_m4_integration.py tests/test_create_payment_tool.py   # 3 + 5 sites
$ ...pytest tests/ -p no:cacheprovider -q
108 passed in 79.34s (0:01:19)
```

**SURVIVED the entire suite.** The real tool-level margin can be cut
from 2.0 s to 0.2 s over httpx's 5.0 s default and neither C-5 guard
notices. The residual risk is flakiness rather than silent
false-passing — shrink it further and the ambiguity tests fail loudly
because no timeout occurs — but it is the same defect round 1 described,
in the same finding, and `BUILD_LOG.md:1207-1212` now claims these tests
"now read the actual constants". Two of the four do. Recorded as **R-2**.

## 6. (C) Did the repairs break or weaken anything?

**No regression found.** 108 passed twice on the project and once on an
independent scratch copy; the pfMCP regression is byte-for-byte at the
M0 baseline; the `git diff eb4685f..HEAD` hunk list lands only in
`parse_operation_started_at`,
`idempotency_window_may_have_expired`, the `create_payment` schema, and
the `create_payment` handler branch; `grep -niE
"send_message|create_batch_payment"` over the diff is empty.

**The two updated pre-existing tests were strengthened, not weakened.**
Diffed against `2c52b05`:

- `test_expired_window_returns_reconciliation_required` — kept
  `status == "RECONCILIATION_REQUIRED"` and the `list_payments`
  guidance, **added** `requestSent is False` and
  `attempt_count == 0, "nothing may be sent"`. The one replaced
  assertion (`"Do NOT send another create request"` →
  `"Do NOT retry"`) tracks the new message's wording; both strings are
  present in the respective versions, so this is not a loosened
  assertion. Net: strictly stronger, and it now pins the pre-flight
  property the milestone is about.
- `test_unparseable_start_time_does_not_invent_expiry` →
  `test_unparseable_start_time_is_rejected_outright` — the old body
  asserted `status == "OUTCOME_UNKNOWN"` for `"junk"`, i.e. that the bad
  value was silently discarded. The new body asserts
  `"OUTCOME_UNKNOWN" not in text`, `"operationStartedAt" in text`, and
  `attempt_count == 0`. The old assertion was **not** weakened to
  accommodate a bug; it was inverted because the behaviour genuinely
  improved, and my mutation in §4.4 kills the new version. The docstring
  records the reason.

Both updates are the right direction under §7 ("an ambiguous transport
outcome is not reported as a definite failure" is unaffected — nothing
was sent, so this *is* a definite failure).

**Nothing else in the suite was relaxed.** No assertion was deleted
anywhere in the `2c52b05`→working-tree diff of `test_create_payment_tool.py`
or `test_fault_server.py` other than the two described above.

## 7. (D)+(E) Remaining round-1 findings, and new ones

### M4-5 — `INFLIGHT_WAIT_SECONDS`

`mocks/fault_server.py:73` is now `20.0`, with a comment citing M4-5 and
stating both bounds. 20.0 > the 7.0 longest stall and < the test
client's 30.0 (`test_m4_integration.py:52`), so the `503` and the client
`ReadTimeout` no longer race. *Confirmed in inspected code.* **Resolved.**
Two caveats: `test_inflight_wait_covers_the_longest_stall_used` asserts
only `> 7.0` against a retyped literal (part of **R-2**), and nothing
asserts the upper bound at all.

### M4-6 — committed, commit message, diff scope

The commit exists (`dd8cc75`, branch `feat/retry-safe-create-payment`,
+113/−20) and the pfMCP tree is clean. **The message is accurate**: I
checked each of its two numbered claims against the diff, and both
describe what the code does, in the right direction, with the honest
closing paragraph ("Verified against a local fault-injection mock only…
not evidence of any real duplicate payment… not a permanent exactly-once
guarantee"). **The diff is scoped to `create_payment`** plus the two
module-level helpers it calls — every hunk is in those regions, and no
out-of-scope tool is named. Nothing was pushed (2 unpushed commits, no
upstream, no PR).

**But M4-6 is only half closed.** Its required correction was "Commit the
pfMCP change **and the prototype M4 files**, record **both SHAs** in
`BUILD_LOG.md` M4, and correct `STATUS.md:122`."

- The prototype M4 files (`tests/test_m4_integration.py`, the 233-line
  `mocks/fault_server.py` delta, the `MOCK_CONTRACT.md` and
  `test_fault_server.py` deltas) are **still untracked**, so a reviewer
  still cannot diff the tests from version control. I accept that
  committing into the parent repository needs Raj's authorisation — that
  is how `2c52b05` was handled — but `BUILD_LOG.md` does not say so for
  M4; it says the finding is closed by `dd8cc75` alone. **R-1.**
- `STATUS.md:122` no longer falsely claims the tree is clean. It now
  falsely claims the opposite: "`pfMCP/` working tree is **NOT clean**:
  M4 added further uncommitted changes to `src/servers/xero/main.py` on
  top of the committed `eb4685f`". The tree is clean, those changes are
  `dd8cc75`, which `STATUS.md` never mentions, and the same bullet says
  "1 unpushed commit" where `git rev-list --count main..HEAD` is **2**.
  This is the third appearance of the same false-cleanliness class
  (M3 F-6, M4-6, now inverted). **R-1.**
- `BUILD_LOG.md:1257` still lists as a known limitation "The +47 lines
  are **uncommitted** on top of `eb4685f`", contradicting the repair
  section 90 lines later. **R-1.**

### M4-9 — dead code

`MockState.lookup()` and `MockState.store()` are gone. `grep -rn
"\.lookup(\|\.store(\|def lookup\|def store"` across `mocks/`, `tests/`,
`repro/` returns no hit in this project (the only match in the tree is an
unrelated `mime.lookup` docstring in `pfMCP/src/servers/peakflo/main.py`).
A comment at the replacement site records why they were removed and
cites M4-9. **Resolved.** The second half of the correction — "mention
the dropped attempt field in `MOCK_CONTRACT.md`" — was not done; there
is no mention of `key_expired` in the contract. Trivial; folded into
**R-5**.

### M4-7, M4-8, M4-10 — record corrections

- **M4-7 resolved.** `BUILD_LOG.md:1194` and the repair section both now
  say "**6–8**, varying by run (observed 7, 6, 7, 8, 8 by the reviewer;
  6 by the builder)". Accurate to round 1's observations.
- **M4-8 resolved.** `BUILD_LOG.md:1163-1166` now reads "Both ambiguous
  outcomes (`OUTCOME_UNKNOWN` and `RECONCILIATION_REQUIRED`) now carry
  `requestSent`… The success path deliberately still returns Xero's raw
  payload unchanged — the declared F-8 decision — so it carries no such
  field." I confirmed `requestSent` is present on all three structured
  outcomes (main.py:3287, 3333, 3367) and absent from the success return
  (:3425). Accurate.
- **M4-10 partially resolved.** The M4 "Commands run" block
  (`BUILD_LOG.md:1221-1225`) now carries the literal five-file command,
  and I ran it verbatim (§3.2). The *same placeholder* round 1 explicitly
  named — "(and the same shape at `:860`)" — is still there:
  `BUILD_LOG.md:860` reads `pytest tests/servers/xero/{5 mock files} -q`.
  Folded into **R-5**.
- **The repair section misnumbers two findings.** It labels the ordering
  claim "M4-8" (round 1's M4-8 was the `requestSent` sentence) and the
  `STATUS.md` cleanliness statement "M4-10" (round 1's M4-10 was the
  `{5 mock files}` placeholder; the `STATUS.md` statement was part of
  M4-6). Both underlying corrections were made, so nothing is missing —
  but the audit trail now disagrees with the review it answers. Folded
  into **R-5**.

### (E) Fresh eyes on the repaired payment path — new findings

I looked specifically for defects the repairs could have introduced.

| Check | Result |
|---|---|
| Parse ordering | Called at :3232, before the payload is built and before the window check at :3252, after the required-field and key checks. No partially-built state, nothing sent. Correct. |
| Error path | `ValueError` → outer `except Exception` (:4576) → `Error: <message>` text. Same convention as `validate_idempotency_key`; definite, nothing transmitted, message is actionable and names the field and an example. It is **not** a structured outcome (no `status` / `requestSent`), unlike the three ambiguous outcomes. Defensible under the declared F-8 shape; noted as **R-6** because M6 will judge an LLM's reaction to these strings. |
| Can strictness refuse a legitimate caller? | Yes, by design: a caller that previously sent `datetime.now().isoformat()` now gets a hard failure instead of a payment. The direction is safe (nothing sent, correctable, clear message) and I confirmed by `grep` that no `repro/`, demo or pfMCP code path passes `operationStartedAt`, so nothing in-repo breaks. But this **is** a second breaking input-contract change, taken unilaterally in the same session in which making the field *required* was deferred as "a breaking interface change… raised rather than taken". `BUILD_LOG.md` describes the change but does not flag it as one. **R-6.** |
| Future-dated stamp | Accepted, treated as fresh, payment sent (probe case ix). Untested, undeclared. **R-3.** |
| `lowercase z` | Rejected as unparseable. Safe direction, mildly surprising; `"…T09:30:00z"` is accepted by some ISO-8601 parsers. Not material. |
| Whitespace padding | `.strip()` before parsing, so `"  …Z  "` is accepted. Fine. |
| `.replace("Z", "+00:00")` | Replaces every `Z`; no realistic ISO-8601 instant contains another. Fine. |
| Window crossed in flight | Still handled at :3311 with `requestSent: true` (probe verified). Correct, untested. **R-3.** |
| 360 s boundary | `>=` — inclusive, matching `test_key_exactly_at_ttl_boundary_has_expired` and the conservative direction. Correct. |
| `operationStartedAt` still optional | Confirmed absent from the schema's `required` list (which holds `invoiceId`, `accountId`, `amount`, `date`, `idempotencyKey`). Deferred with reasons in `BUILD_LOG.md`, as round 1 asked if it stayed optional. The accompanying ask — a comment in `test_expired_window_without_start_time_can_double_pay` noting it asserts a known-bad outcome deliberately — is met in substance by the docstring ("the documented gap, demonstrated rather than asserted") and the assertion message, though it does not say the test must be rewritten if the field is hardened. Acceptable. |

## 8. (G) Accuracy of the builder's repair claims

| Claim | Verdict |
|---|---|
| "Prototype suite: **108 passed**" | **Accurate.** Observed 3×: 108 passed (81.79 s, 80.32 s, and 79.35 s on an independent scratch copy) |
| "pfMCP regression: 37 failed / 20 passed — still the M0 baseline" | **Accurate.** Observed 37 failed / 20 passed in 4.90 s |
| "Committed as **`dd8cc75`** … (+113/−20)" | **Accurate** to the line: `git diff --stat eb4685f..HEAD` = 1 file, 113 insertions, 20 deletions |
| "`pfMCP` working tree clean" | **Accurate** in `BUILD_LOG.md`; **contradicted by `STATUS.md:122`**, which still says NOT clean (**R-1**) |
| Corrected figure "**6–8**, varying" | **Accurate**, and attributed to round 1's five runs |
| M4-1 "Seventeen new tests cover the ambiguous inputs, both offset directions, and that nothing is transmitted when rejected" | **Overstated.** 108 − 94 = **14** new collected cases (8 + 4 parametrized plus 2 single tests), with one pre-existing test renamed and two strengthened. The coverage described is real; the count is not (**R-5**) |
| M4-2 "uses `commit_delay_seconds` to hold the key genuinely in flight, because otherwise the second request finds it already cached and exercises the wrong branch" | **Accurate and sound** — independently confirmed by the `[200, 200]` failure signature under M-C6 (§5) |
| M4-3 "The test now times each waiter" | **Accurate**; killed 3/3 directly |
| M4-4 "The margin constants are now exported from `test_fault_server.py` and read by the check" | **Accurate for the mock-level pair only.** The tool-level pair is still retyped literals and survives M-D1 (**R-2**) |
| M4-4 "C-5 … Four tests pin the relationships… They now read the actual constants" (`BUILD_LOG.md:1207-1212`) | **Not supported.** Two of the four read retyped literals; I disproved the claim by mutation (**R-2**) |
| M4-5 "Now 20.0 s, comfortably above the 7.0 s longest stall and below the client's" | **Accurate** in code; `MOCK_CONTRACT.md` still documents it as **30 s** (**R-5**) |
| M4-9 "Removed" | **Accurate.** No caller remains |
| M4-10 "a `{5 mock files}` placeholder that was not a runnable command. Corrected" | **Partly accurate.** Fixed at `:1218`; the identical placeholder round 1 named at `:860` remains (**R-5**) |
| "`tests/test_m4_integration.py` (new, 20 tests)" / "one assertion updated" (`BUILD_LOG.md:1213-1219`) | **Now stale.** 34 collected cases; two tests updated, one of them renamed. Chronologically defensible, but the Files block is the part a reader checks (**R-5**) |

## 9. (F) Scope and safety — unchanged, all pass

| §4 safety absolute | Result |
|---|---|
| No real payment, message or live write | **Pass.** All traffic to `127.0.0.1`; `call_tool` asserts loopback (`test_create_payment_tool.py:47`); mock binds `("127.0.0.1", port)` |
| No live Xero/Peakflo endpoint on any path | **Pass.** `grep -rnE "https?://" tests/ mocks/ --include=*.py` filtered for non-loopback returns **nothing** |
| No keys, tokens, credentials or real financial data | **Pass.** The credential scan over `tests/` and `mocks/` returns only the parameter name `api_key=None` and the self-labelling fakes `fake-local-token-not-a-secret` / `fake-local-tenant`. The diff adds none |
| No claim of a real production incident | **Pass.** Stated in the mock docstring, `MOCK_CONTRACT.md:3-7`, and the new commit message |
| No claim of permanent exactly-once execution | **Pass.** Denied explicitly in `MOCK_CONTRACT.md` and in the `dd8cc75` message |
| Mocks labelled as simulation | **Pass.** `__mock__` on every response (7 sites), module docstring, contract header, test-module docstring "LOCAL SIMULATION ONLY" |

| Scope check | Result |
|---|---|
| Only `create_payment` touched in pfMCP | **Pass.** 1 file; all 11 hunks in the two helpers, the `create_payment` schema, and the `create_payment` handler |
| `send_message` / `create_batch_payment` untouched | **Pass.** No match in the diff; `test_out_of_scope_tools_still_exist` and `test_other_tools_keep_their_optional_idempotency_key` pin it from the tool list |
| No unrelated refactor | **Pass.** The repair deltas are the parse helper, the margin constants (18 lines), the in-flight/timing assertions, and the dead-code removal |
| No new dependency | **Pass.** No import added by `dd8cc75` |
| `commit_delay_seconds` still inert by default | **Pass.** Default `0.0`, one guarded use site, set only in `test_m4_integration.py` (2 places) |
| No pre-existing user work discarded | **Pass.** `Composio` / `Emergent/*` modifications and untracked paths identical before and after |
| `repro/results/` untouched | **Pass.** All mtimes 2026-11-16, `m1_baseline_latest.json` included |

## 10. Acceptance criteria (`BUILD_PLAN_peakflo.md` §10 M4)

| Criterion | Met? | Evidence |
|---|---|---|
| Tests assert both returned status **and** ledger side effects | **Met, and improved** | The new timezone tests assert `payment_count` and `attempt_count`; M-C6 and M-C3 now also force status/timing assertions. Mutation-confirmed |
| Tests are deterministic | **Met** | 108 passed 3× (two project runs, one standalone scratch copy); no flake. Caveats: within-file order never shuffled (no randomising plugin installed); the M4-2 test depends on a 0.5 s in-flight window (3/3 stable); the M4-5 coin flip is gone |
| All relevant tests pass, or failures clearly explained | **Met** | 108/108 prototype; pfMCP 20/37 = M0 baseline, cause documented in M0 |
| Automated tests + reproducible command(s) | **Met** | §3 commands all ran as written; the M4 `BUILD_LOG` block is now literal (the `:860` M3 block is not) |
| 13 required test cases | **Met.** Case 6's concurrent half and case 10's malformed-timestamp half — round 1's two substantive holes — are now genuinely asserted and mutation-confirmed | §5; §4.2–4.4 |

## 11. Adversarial checks (§4) — delta from round 1

Retry-model checks: same key + identical payload — pass. No per-attempt
key generation — pass. `reference` never the key — pass. Same key +
different payload rejected — **now pass for the concurrent case too**
(M-C6 killed). Distinct legitimate operation not blocked — pass, and
reinforced: `test_a_fresh_payment_in_a_negative_offset_zone_is_not_refused`
plus my probe (i). Ambiguous outcome not reported as definite — pass.
Expiry leads to reconciliation, not a blind new-key retry — **now pass
for ambiguous input too**: it is refused pre-send rather than guessed.
Key validation covers type, non-empty, 128 — pass.

Test quality: ledger asserted — pass; deterministic — pass; negative
cases — pass; **tests would fail on regression — 4 of my 5 mutations
killed** (old-UTC parse, M-C6, M-C3, M-C7), **M-D1 survives** (tool-level
margin, **R-2**), and 3 of 8 parametrized cases in the new timezone test
discriminate nothing (**R-4**).

Record accuracy: one false statement (`STATUS.md:122`, inverted), one
unsupported claim (C-5 "four tests"), one stale constant in
`MOCK_CONTRACT.md`, one stale limitation bullet, one wrong count, two
misnumbered findings, one surviving placeholder.

## 12. Findings in this round

| # | Severity | File:line | Finding | Required correction |
|---|---|---|---|---|
| **R-1** | Medium | `STATUS.md:122-129`; `BUILD_LOG.md:1257`, `:1318-1320`; parent `git status` | The record of where M4 lives is wrong in three places. `STATUS.md` says the pfMCP tree is "NOT clean … further uncommitted changes" (it is clean; those changes are `dd8cc75`, which `STATUS.md` never names) and "1 unpushed commit" (there are 2). `BUILD_LOG.md:1257` still lists "+47 lines are **uncommitted**" as a limitation. The prototype M4 files are still untracked, so the tests remain un-diffable from version control, while `BUILD_LOG` presents M4-6 as closed by `dd8cc75` alone | Derive the `STATUS.md` bullet from `git status` / `git rev-list --count main..HEAD` again, name `dd8cc75`, delete or correct the stale limitation bullet, and state plainly that the prototype M4 files remain untracked pending Raj's authorisation (the `2c52b05` precedent) rather than implying M4-6 is fully closed |
| **R-2** | Medium | `tests/test_m4_integration.py:473-480`, `:499-501` and the eight `delay_seconds=7.0` literals (`test_m4_integration.py:316, 334, 358`; `test_create_payment_tool.py:162, 189, 237, 253, 272`); claim at `BUILD_LOG.md:1207-1212` | M4-4's tool-level half is unrepaired. My mutation M-D1 cut the real stall 7.0 → 5.2 at all eight sites and the **whole suite stayed green (108 passed)**, because the guard retypes `tool_stall = 7.0` and the in-flight guard retypes `> 7.0`. `BUILD_LOG` says all four C-5 tests "now read the actual constants"; two do | Hoist the tool-level stall (and, if wanted, the implicit client timeout) into a module constant used by the behaviour tests *and* by both guards — the same fix already applied to `MOCK_CLIENT_TIMEOUT_SECONDS` / `MOCK_STALL_SECONDS`. Until then, correct the `BUILD_LOG` sentence to say two of the four are substantive |
| **R-3** | Low | `tests/test_m4_integration.py` (absent); behaviour at `main.py:3252`, `:3311` | Two of the five cases round 1 required tests for are still uncovered: a **future-dated** `operationStartedAt` (accepted, treated as fresh, payment sent — I verified) and the **window crossed while the request is in flight** (handled correctly at `:3311` with `requestSent: true` — I verified). Behaviour is right in both; neither is pinned | Add the two tests. If future-dating is deliberately tolerated, say so in a comment or docstring |
| **R-4** | Low | `tests/test_m4_integration.py:376-406` | 3 of the 8 parametrized cases discriminate nothing: `1763376000` and `12.5` are stopped by schema validation either way, and `"2026-11-17"` passes under the old assume-UTC behaviour too, because the `RECONCILIATION_REQUIRED` guidance text happens to contain `"operationStartedAt"`. Verified: those three pass against the mutated helper | Assert the rejection itself for these cases (e.g. `text.startswith("Error:")` plus `"RECONCILIATION_REQUIRED" not in text`), so a hard-block cannot masquerade as a rejection |
| **R-5** | Low | `mocks/MOCK_CONTRACT.md:79`; `BUILD_LOG.md:860`, `:1213-1219`, `:1303`, `:1318-1335` | Record detail: the contract still documents `INFLIGHT_WAIT_SECONDS` as **30 s** (code is 20.0); `BUILD_LOG.md:860`'s `{5 mock files}` placeholder — named by round 1 in the same finding — is still there; "Seventeen new tests" is **14**; "new, 20 tests" / "one assertion updated" are stale (34 collected, two tests updated, one renamed); the repair section labels the ordering claim "M4-8" and the `STATUS.md` claim "M4-10" where round 1 numbered them M4-8 = `requestSent` wording and M4-10 = the placeholder; `MOCK_CONTRACT.md` still does not mention the dropped `key_expired` attempt field | Correct each; keep round 1's numbering so the two reports can be read against each other |
| **R-6** | Low | `main.py:220-262` + `:4576-4578`; `BUILD_LOG.md` repair section | Two presentational/contract points on the new gate: (a) a rejected `operationStartedAt` returns an unstructured `Error: …` string, not a structured outcome with `status` / `requestSent: false` like the other three outcomes — fine under the declared F-8 shape, but M6 judges an agent's reaction to exactly these strings; (b) rejecting values the previous schema accepted ("Optional ISO-8601 timestamp") is itself a breaking input-contract change, taken unilaterally in the same session in which making the field *required* was deferred as too breaking to decide alone | Either return a structured `status: "INVALID_INPUT"`-style outcome, or record in `BUILD_LOG.md` that the plain-`Error:` shape is deliberate for pre-send validation failures; and list the new strictness alongside the other declared, Raj-overrulable interface decisions |

## 13. Per-finding resolution table

| Round-1 finding | Status | Evidence |
|---|---|---|
| **M4-1** (High, timezone) | **Resolved** (code); **partially** on the test set | Helper probe (21 inputs), end-to-end probe (9 cases, ledger-verified): both reproduced failure modes gone, rejection sends nothing, both offset directions work. Mutation restoring assume-UTC **killed by 6 tests**. Missing tests: future-dated, window-crossed-in-flight (**R-3**); 3 of 8 params non-discriminating (**R-4**) |
| **M4-2** (concurrent conflict unasserted) | **Resolved** | M-C6 re-applied → `assert [200, 200] == [200, 400]`, killed 3/3. The `[200, 200]` signature proves the **in-flight** branch is the one under test; the builder's `commit_delay_seconds` reasoning is sound |
| **M4-3** (waiter-release timing unasserted) | **Resolved** | M-C3 re-applied → `assert 0 == (4 - 1)` in the test named for the property, killed 3/3, no longer incidental |
| **M4-4** (vacuous C-5 guards) | **Partially resolved** | Mock-level half fixed with shared constants; M-C7 now killed. Tool-level half untouched: my M-D1 shrank the real 7.0 s stall to 5.2 s and **108 passed**. `BUILD_LOG`'s "four tests … now read the actual constants" is unsupported (**R-2**) |
| **M4-5** (`INFLIGHT_WAIT_SECONDS` == client timeout) | **Resolved** | `fault_server.py:73` = 20.0, bounds documented; 7.0 < 20.0 < 30.0. Contract doc still says 30 s (**R-5**) |
| **M4-6** (uncommitted; `STATUS.md` false "clean") | **Partially resolved** | `dd8cc75` exists, message accurate, diff scoped to `create_payment`, tree clean. Prototype M4 files still untracked; "both SHAs" not recorded; `STATUS.md:122` now carries the inverted false statement and a wrong commit count (**R-1**) |
| **M4-7** ("1 vs 6" figure) | **Resolved** | Now "6–8, varying by run (observed 7, 6, 7, 8, 8 …)" |
| **M4-8** ("all outcomes carry `requestSent`") | **Resolved** | Reworded to name the two ambiguous outcomes and the deliberate success-path exception; verified against `:3287`, `:3333`, `:3367`, `:3425` |
| **M4-9** (dead `lookup`/`store`) | **Resolved** | Removed, with a comment citing M4-9; no caller remains anywhere. Contract mention of the dropped `key_expired` field not done (**R-5**) |
| **M4-10** (`{5 mock files}` placeholder) | **Partially resolved** | Fixed at `:1218` and the literal command runs; the identical placeholder round 1 named at `:860` remains (**R-5**) |
| Recommendation: make `operationStartedAt` required | **Deferred, acceptably** | Still optional (confirmed absent from `required`). Deferred in `BUILD_LOG` with reasons and raised for Raj, which is what round 1 asked for if it stayed optional. The double-pay test documents the gap in its docstring and assertion message |

## 14. Limitations of this review

1. **Live Xero behaviour: Unknown / Not tested.** I contacted nothing
   and re-verified no documentation. Every result describes this
   client/mock pair.
2. **Not an independent environment or party.** Same session, machine,
   interpreter, venv and checkout as the builder; the venv path, the
   commands, the SHA and the finding list were handed to me.
3. **This is a re-review.** I did not re-derive round 1's reservation
   analysis (deadlock, lost wakeup, raising owner, `reset()` with
   waiters, expired-entry race) or its 13-case coverage table from
   scratch; I accepted them where the repairs did not touch them.
4. **Five mutations, not exhaustive.** Four kills and one survivor.
   Other unpinned behaviours may remain.
5. **Within-file test order was never shuffled** — no randomising plugin
   is installed. Order independence is verified at file granularity only
   (and by a standalone scratch run).
6. **Concurrency results are Windows 11 / CPython thread scheduling on
   one machine.** The M4-2 test's reliance on a 0.5 s in-flight window
   was exercised 3/3 plus three full suite runs, not under load or on
   another platform.
7. **The 37 pfMCP failures were not bisected.** I observed the count and
   accepted round 1's traceback-level diagnosis.
8. **The prototype test delta could not be reviewed from version
   control.** I reconstructed it against `2c52b05`, so a working-tree
   change made by some path other than M4 would be attributed to M4.
9. **I did not run** `repro/retry_dup_repro.py`, pfMCP's live-client
   path, or any linter/type checker (M8's job).

## 15. Verdict

**The rejection is resolved where it mattered.** The High-severity
timezone defect is genuinely fixed, not papered over: I drove the real
tool against the mock and read the ledger, and both failure modes round 1
reproduced are gone — a seconds-old first payment from a UTC-negative
caller commits (`payment_count=1`), a two-hour-old key from a
UTC-positive caller is refused with `attempt_count=0`, and every
ambiguous input (naive, space-separated, bare date, empty, whitespace,
unparseable, non-string) is a definite pre-send failure that transmits
nothing. Restoring the old assume-UTC behaviour in a scratch copy is
killed by six tests, so the fix is pinned rather than asserted. The three
previously-surviving mutations are each killed, 3/3, by the tests named
for them — and the `[200, 200]` failure signature under M-C6
independently confirms the builder's account of why
`commit_delay_seconds` was needed to reach the in-flight branch. The two
pre-existing tests that were rewritten were **strengthened**: the old
`"junk" → OUTCOME_UNKNOWN` assertion was inverted because the behaviour
improved, and the expiry test gained `requestSent is False` and
`attempt_count == 0`. 108 passed three times, the pfMCP baseline is
untouched, the commit message is accurate and the diff is scoped to
`create_payment`. No safety absolute is violated.

**What is not resolved is narrower, and I will not call it closed.** Two
items from round 1's "required before re-submission" list are only half
done. M4-4's tool-level half was left alone, and I proved it: cutting the
real 7.0 s stall to 5.2 s — a 0.2 s margin over httpx's 5.0 s default —
leaves all 108 tests green, because the guard retypes the literal it is
supposed to be guarding. `BUILD_LOG.md` nonetheless states that the four
C-5 tests "now read the actual constants"; two do. And M4-6's record half
did not land: `STATUS.md:122` has traded its false "clean" for a false
"NOT clean", never names `dd8cc75`, and miscounts the unpushed commits,
while the prototype M4 tests remain untracked and therefore still
un-diffable from version control. That is the third round of the same
false-cleanliness statement.

I weighed rejecting again on M4-4/R-2, because a disproved claim is
exactly what §5 calls unsupported. I am not doing so, and here is the
reasoning so it can be overruled: the residual guard protects a test
*margin*, not payment behaviour. Shrink the stall too far and the
ambiguity tests fail loudly rather than silently passing, so the exposure
is flakiness, not a false green on a payment property — unlike M4-1,
M4-2 and M4-3, which were about behaviour and are now genuinely pinned.
Every §10 M4 acceptance criterion is met and better evidenced than it was.
So the remaining work is conditions, not a gate failure — but the
`BUILD_LOG`/`STATUS` sentences that overstate it must be corrected now,
not carried.

### Conditions

| # | Condition | Safe to proceed to M5? | Must be resolved by |
|---|---|---|---|
| **C-M4-1** (R-1) | Correct `STATUS.md:122-129` from `git status` (tree is clean, name `dd8cc75`, 2 unpushed commits), delete the stale "uncommitted" limitation at `BUILD_LOG.md:1257`, and state plainly that the prototype M4 files are still untracked pending Raj's authorisation rather than implying M4-6 is closed | **No** — fix before M5 | **Before M5.** This is the third recurrence of the same false statement (M3 F-6, M4-6, now inverted), and M5 is the demonstration milestone, where a reader will rely on these records |
| **C-M4-2** (R-2) | Correct the C-5 claim in `BUILD_LOG.md:1207-1212` to say two of the four guards are substantive; then hoist the tool-level stall into a shared constant read by the behaviour tests and both guards | Wording: **No**, correct before M5. Code: **Yes** | Wording **before M5**; the constant hoist in **M8** (test/CI hardening), or sooner if M5 touches these stalls |
| **C-M4-3** (R-5) | Record detail: `MOCK_CONTRACT.md` 30 s → 20 s, `BUILD_LOG.md:860` placeholder, "Seventeen new tests" → 14, the stale Files block, round-1 finding numbering, the dropped `key_expired` field | **Yes** | **M5's record pass.** The 30 s figure is the one a reader could act on, so do that one first |
| **C-M4-4** (R-3, R-4) | Add the future-dated and window-crossed-in-flight tests; make the three non-discriminating parametrized cases assert the rejection itself | **Yes** — behaviour verified correct in this review | **M8**, or M5 if the demo exercises expiry |
| **C-M4-5** (R-6) | Decide and record whether a rejected `operationStartedAt` should return a structured outcome, and list the new input strictness among the declared, Raj-overrulable interface changes | **Yes** | **M6**, which evaluates how an agent reads these outcomes |

VERDICT: APPROVED WITH CONDITIONS

# M4 — Automated integration and regression tests: independent review

**Milestone:** M4 — Automated integration and regression tests
**Date:** 2026-11-17
**Reviewer:** independent quality-gate agent (Claude Code session, separate
agent from the builder; did not write any of the code under review)
**Policy applied:** `QUALITY_GATE_AGENT.md` §4 (adversarial checks), §5
(verdicts), §6 (report format), against `BUILD_PLAN_peakflo.md` §7, §9,
§10 M4, §12, §13.

## 1. How independent this review was — honestly

- I did not write, and have not previously edited, any file under review.
  I read the artifacts from the repository, not from the builder's
  summary, and every number below came from a command I ran.
- **Not an independent environment.** Same machine, same Windows 11
  checkout, same interpreter and same `pfMCP/.venv` as the builder. The
  venv path and two suggested commands were handed to me. I added my own
  commands and seven mutations of my own design.
- Everything that could change behaviour was done on a **scratch copy**
  at `<scratchpad>`
  (copies of `tests/`, `mocks/`, `pytest.ini` and `pfMCP/src/`). Every
  mutated file was restored and verified with `cmp` as byte-identical to
  the project copy. The only project file this review writes is
  `reviews/M4-review.md`.
- **I did not run `repro/retry_dup_repro.py`** (it rewrites results
  files). `Peakflo/repro/results/` file timestamps are all 2026-11-16 and
  unchanged.
- `git -C pfMCP status --short` is unchanged at the end of the review
  (` M src/servers/xero/main.py`, 47 insertions). No branch was changed,
  nothing was committed.
- **Live Xero behaviour remains Unknown / Not tested.** Everything below
  labelled *verified by local test* proves the behaviour of this
  client/mock pair only, exactly as `BUILD_PLAN_peakflo.md` §13 requires.

## 2. What I inspected

| Artifact | Scope inspected |
|---|---|
| `tests/test_m4_integration.py` | new, 416 lines, 20 tests — read in full |
| `mocks/fault_server.py` | 637 lines, read in full; M4 delta = **217 changed lines** vs `2c52b05` |
| `mocks/MOCK_CONTRACT.md` | 104 lines, read in full; M4 delta = +19 lines |
| `tests/test_create_payment_tool.py` | M4 delta = 16 changed lines (one assertion replaced, two added, docstring) |
| `pfMCP/src/servers/xero/main.py` | **uncommitted** `git diff` on top of `eb4685f`, branch `feat/retry-safe-create-payment` — +47 lines, 0 deletions, all inside the `create_payment` handler |
| `BUILD_LOG.md` M4 (lines 1133–1232), M2/M3 verdict sections | claims cross-checked against the repository |
| `reviews/M2-review.md`, `reviews/M3-review.md` | conditions C-2, C-4, C-5 and M3's F-1…F-8 |
| `STATUS.md` | safety posture and condition table |

Note on diff availability: the prototype's own files are **not in version
control on the checked-out branch** (`git status` in the parent repo shows
`?? ./` for `Peakflo/`). I reconstructed the M4 delta by diffing the
working tree against the M3-era commit `2c52b05` on branch
`peakflo-retry-safe`. See defect **M4-6**.

## 3. Commands I actually ran, with actual output

### 3.1 Prototype suite — four full runs, all green

```
$ cd R:\Internship_Outreach_prototype\Peakflo
$ pfMCP/.venv/Scripts/python.exe -m pytest tests/ -p no:cacheprovider -q
94 passed in 85.18s (0:01:25)          # run 1
94 passed in 78.08s (0:01:18)          # run 2
```

Ordering probe (the suite contains threaded concurrency tests, so I did
not take two identical-order runs as evidence of order independence):

```
$ pfMCP/.venv/Scripts/python.exe -m pytest tests/test_outcome_classifier.py \
    tests/test_m4_integration.py tests/test_fault_server.py \
    tests/test_create_payment_tool.py -p no:cacheprovider -q
94 passed in 77.14s (0:01:17)

$ pfMCP/.venv/Scripts/python.exe -m pytest tests/test_m4_integration.py -p no:cacheprovider -q
20 passed in 30.23s
```

A fifth green run (94 passed in 77.51 s) came from the unmutated scratch
copy, which confirms the suite is self-contained.

`pytest 9.2.0`; no `pytest-randomly` / `pytest-random-order` / `xdist`
installed, so **within-file order shuffling was not possible**. Order
independence is verified at file granularity only.

### 3.2 pfMCP regression — exactly the M0 baseline

```
$ cd R:\Internship_Outreach_prototype\Peakflo\pfMCP
$ .venv/Scripts/python.exe -m pytest tests/servers/xero/test_accounting_expansion.py \
    tests/servers/xero/test_attachment_download.py tests/servers/xero/test_get_invoice_pdf.py \
    tests/servers/xero/test_update_invoice_status.py tests/servers/xero/test_imda_tools.py \
    -p no:cacheprovider -q
37 failed, 20 passed in 4.59s
```

I confirmed the cause is the documented pre-existing helper bug, not M4:

```
$ .venv/Scripts/python.exe -m pytest tests/servers/xero/test_imda_tools.py::test_list_accounts_no_filter -q
>       call_kwargs = api_mock.call_args_list[0]
E       IndexError: list index out of range
ERROR    xero:main.py:4531 Error executing tool list_accounts:
         [credentials_missing] Xero credentials are missing for this connection.
```

**20 passed / 37 failed = the M0 baseline exactly. M4 did not make it
worse.** *Verified by local test.*

## 4. (A) The defect the builder claims to have found and fixed

Both halves verified independently, on the scratch copy, by driving the
real tool and reading the **mock's ledger and attempt log**, not the
returned JSON.

**(ii) The underlying danger was real.** I reverted the whole guard with
`patch -p1 -R` (back to `eb4685f`) in the scratch copy and ran my own
probe (`probe_a.py`): first attempt against `commit_then_slow`, then
advance the mock clock past the 360 s TTL, then retry with the same key
and `operationStartedAt="2020-01-01T00:00:00Z"`.

```
first  : {"status": "OUTCOME_UNKNOWN", "operationId": "probe-a", ...
ledger after first      : 1 attempts: 1
second : {"Payments": [{"PaymentID": "3dbfd546-...", "http_method": "PUT", ...
ledger after stale retry: 2 attempts: 2
RESULT: payment_count = 2
```

**Confirmed: without the guard a stale-key retry commits a SECOND
payment.** The builder's claim is true, and the defect was material.

**(i) The guard genuinely sends nothing.** Scratch copy restored to the
M4 file (`cmp` byte-identical to the project copy), same probe:

```
second : {"status": "RECONCILIATION_REQUIRED", "operationId": "probe-a",
          "message": "No request was sent. This idempotencyKey is older than
          Xero's 6-minute retention window, ...
ledger after stale retry: 1 attempts: 1
RESULT: payment_count = 1
```

`attempt_count` stays at **1**, so nothing reached the server — the guard
is genuinely pre-flight, not a relabelled failure. The test
`test_expired_window_with_start_time_refuses_to_send`
(tests/test_m4_integration.py:316) asserts the same `attempt_count`
invariant, which is the right assertion. Both expiry tests are killed by
the reverted guard (2 failed).

### But the fix is not complete — a well-formed input still goes wrong

`idempotency_window_may_have_expired`
(pfMCP/src/servers/xero/main.py:220-235) silently assumes a
timezone-less timestamp is UTC (`if started.tzinfo is None:
started = started.replace(tzinfo=timezone.utc)`). Until M4 that helper
only chose a *label* on a request that had already failed. M4 promoted it
to a **send / do-not-send gate**, so its input handling now decides
whether a payment happens at all. Direct probe of the helper:

```
False  <- expired? | aware UTC now                                   ('...T05:33:46+00:00')
True   <- expired? | naive local clock of a UTC-5 caller, FIRST attempt ('2026-11-17T00:33:46')
False  <- expired? | naive local clock of a UTC+8 caller, key truly 10 min old ('2026-11-17T13:23:46')
True   <- expired? | aware, genuinely 10 min old                     ('...T05:23:46+00:00')
False  <- expired? | epoch seconds as int (non-string)               (1794793626)
True   <- expired? | date only                                       ('2026-11-17')
```

End-to-end, through the real tool against the mock (`probe_naive.py`), a
**first** attempt whose `operationStartedAt` is a naive local timestamp
from a UTC-negative caller:

```
operationStartedAt = 2026-11-17T00:48:43.085282
returned: {"status": "RECONCILIATION_REQUIRED", "operationId": "naive-probe",
           "message": "No request was sent. ..."
ledger payment_count = 0  attempt_count = 0
```

A legitimate, seconds-old payment is **refused outright and never made**.
The mirror image is worse in the other direction: a UTC-positive caller's
naive timestamp makes a genuinely stale key look fresh, so the tool
**sends with a stale key** — the exact path this milestone exists to
close. `"2026-11-17"` (date only) hard-blocks; an integer epoch sends.

No M4 test exercises any of these: `test_recent_start_time_still_returns_outcome_unknown`
(tests/test_create_payment_tool.py:249) uses `datetime.now(timezone.utc)`,
i.e. always tz-aware, and `test_unparseable_start_time_does_not_invent_expiry`
(:262) uses `"junk"`, which `fromisoformat` rejects outright. This is
defect **M4-1**.

## 5. (B) The concurrency claim (C-4), scrutinised hardest

### 5.1 The honest negative result is accurate

Mutation **M-B1** on the scratch mock: reservation removed from
`begin_operation` (mocks/fault_server.py:243-251 replaced by
`return "own", InFlightOperation(fingerprint)`), i.e. back to the
pre-C-4 `lookup → commit → store`.

```
$ pytest tests/test_m4_integration.py -k concurrent -q      (5 consecutive runs)
E  assert 7 == 1     1 failed, 5 passed   <= run 1
E  assert 6 == 1     1 failed, 5 passed   <= run 2
E  assert 7 == 1     1 failed, 5 passed   <= run 3
E  assert 8 == 1     1 failed, 5 passed   <= run 4
E  assert 8 == 1     1 failed, 5 passed   <= run 5
```

**Confirmed, exactly as the builder reported:** five of the six
concurrency tests pass with the reservation deleted, and only
`test_concurrent_same_key_with_a_forced_race_window` catches it. The kill
is reliable 5/5. The ledger count is **6–8**, not a stable 6 (defect
**M4-7**).

### 5.2 Is `commit_delay_seconds` a legitimate seam?

**Yes.** Judgement, with reasons:

- It widens a window that genuinely exists in the code
  (`begin_operation`-less check-then-act), it does not invent a new code
  path. The mutated and unmutated code differ only in whether the key is
  claimed; the delay is applied identically to both. So the test
  discriminates the property under test and nothing else.
- Default `0.0` (mocks/fault_server.py:159), guarded by
  `if self.state.commit_delay_seconds:` (:541), set in exactly one place
  in the whole repository — `tests/test_m4_integration.py:119`. It cannot
  engage in normal operation. *Confirmed in inspected code* by grep
  across `mocks/`, `tests/` and `repro/`.
- It is documented in both the code (:150-158) and
  `MOCK_CONTRACT.md:84-89` as test support only.
- The alternative — claiming a fix for a race no test can fail on — is
  worse. The builder's choice to report the negative result first and
  then build the seam is the right order of work and is to their credit.

The honest caveat, which BUILD_LOG already states, is that the test
proves *"the reservation is what keeps this at one payment when the
window is wide"*, not *"this interleaving occurs at production
timings"*. That is the correct claim and it is correctly scoped.

### 5.3 Does the reservation logic itself look correct?

Reviewed against each failure mode named in the brief. *Confirmed in
inspected code*:

| Concern | Finding |
|---|---|
| Deadlock | `_lock` is an `RLock`; `finish_operation` calls `event.set()` inside it, which never blocks. `_get_payments` takes the same RLock. No lock is held across `time.sleep` or socket I/O. No cycle. |
| Lost wakeup | `threading.Event` is sticky, and `begin_operation` returns the holder under the lock, so an owner that finishes between `begin_operation` and `event.wait()` leaves the event already set. Correct. |
| Owner that raises | `_mutating_payment` wraps `_process` in `except BaseException: finish_operation(key, None); raise` (:466-470). `finish_operation` pops the in-flight entry and sets the event; `if result is not None` means a `None` result cannot clobber an outcome already cached. Waiters get `holder.result is None` → `503`. Correct, and the publish-before-respond ordering in every mode means no path can respond without publishing. |
| `reset()` with waiters pending | `reset()` sets every pending event before clearing (:180-183), so a reset cannot hang a live request. Waiters then see `result is None` → `503`. Correct. |
| Waiter timeout | Bounded, see **M4-5**. |
| Fingerprint mismatch against an in-flight key | Handled (`"conflict"`, :245-246) — but **not asserted by any test**; see **M4-2**. |
| Expired cache entry racing a new claim | `begin_operation` deletes the expired entry and falls through to the in-flight check under the same lock. Correct. |

Side observation: `MockState.lookup()` and `MockState.store()` are now
unreachable — no caller in `mocks/`, `tests/` or `repro/` — and the
attempt-log field `key_expired` was silently dropped from the attempt
record. See **M4-9**.

### 5.4 Is `INFLIGHT_WAIT_SECONDS = 30` safe?

Tested, not reasoned. Mutation **M-C8**: owner never publishes in
`MODE_OK` (`finish_operation` removed from the OK path).

```
$ pytest tests/test_m4_integration.py::test_concurrent_same_key_commits_exactly_once -q --durations=3
31.43s call  test_concurrent_same_key_commits_exactly_once
1 failed in 35.70s
```

**It cannot hang a run** — a stuck owner costs ~30 s and then a clean
failure. But `INFLIGHT_WAIT_SECONDS = 30.0` (mocks/fault_server.py:73)
is *exactly* the test client's `timeout: float = 30.0`
(tests/test_m4_integration.py:51), so at the boundary the mock's `503`
and the client's `ReadTimeout` race, and which one the test sees is a
coin flip. That is the very thing condition C-5 exists to forbid. See
**M4-5**.

## 6. (C) Test quality, by mutation

Do the M4 tests assert ledger side effects rather than status alone?
**Mostly yes, and this is genuinely well done.** 11 of the 20 M4 tests
assert `state.snapshot()["payment_count"]`, two assert `attempt_count`,
and `test_empty_key_is_treated_as_absent_and_recorded` asserts the
attempt log and the cached-key list. The two expiry tests assert the
ledger *and* that nothing was transmitted.

Seven mutations, all on scratch copies, all restored byte-identical:

| # | Mutation | Result |
|---|---|---|
| M-A1 | Revert the pre-flight guard entirely (`patch -R`) | **killed** — 2 failed; and my probe showed `payment_count` 1 → 2 |
| M-B1 | Reservation removed from `begin_operation` | **killed** — by exactly 1 of 6 concurrency tests, 5/5 reliably |
| M-C1 | `key_is_usable` → `return key is not None` (regress C-2) | **killed** — 2 failed, 92 passed |
| M-C3 | Publish the outcome **after** the artificial stall | **survives the two tests named for it** — see below |
| M-C5 | Do not cache the internal error in `fail_before_commit` | **killed** — 2 failed, 92 passed |
| M-C6 | In-flight fingerprint mismatch → `"wait"` instead of `"conflict"` | **SURVIVED — 94 passed** |
| M-C7 | Shrink the real mock-level margin 2.0/0.5 → 0.6/0.5 | **SURVIVED** |

**M-C6 survived the entire suite.** `test_concurrent_same_key_different_payload_is_rejected`
(tests/test_m4_integration.py:187-209) is titled *"One wins; the
conflicting one is refused, not committed"* but asserts only
`payment_count == 1`. With the mutation the conflicting caller simply
waits and is handed the first caller's cached **200**, so the ledger is
still 1 and the suite is green. The documented
`400 "used with a different request"` for the concurrent case is
asserted nowhere. Defect **M4-2**.

**M-C3 survived the two tests that claim to pin it.** Moving
`finish_operation` to after `time.sleep(self.delay_seconds)` in
`MODE_COMMIT_THEN_SLOW` (mocks/fault_server.py:552-556) leaves
`test_concurrent_waiters_are_released_without_serving_the_full_stall`
and `test_concurrent_same_key_under_a_slow_commit` both passing, with
essentially identical durations:

```
mutated : 2.36s  test_concurrent_waiters_are_released_without_serving_the_full_stall
baseline: 2.29s  test_concurrent_waiters_are_released_without_serving_the_full_stall
3 passed in 8.45s  /  3 passed in 8.37s
```

The property is asserted in `MOCK_CONTRACT.md:79-80` and in the
`_process` docstring, and no test can observe it. In the full suite M-C3
was killed only *incidentally*, by
`test_expired_window_without_start_time_can_double_pay` — which reveals
that the headline double-pay demonstration quietly depends on
publish-before-stall ordering. Defect **M4-3**.

**M-C7 survived**, which is the substance of defect **M4-4**:

```
applied M-C7: margin shrunk 2.0/0.5 -> 0.6/0.5 (tests/test_fault_server.py:96)
$ pytest tests/test_fault_server.py::test_commit_then_slow_times_out_client_but_commits \
         tests/test_m4_integration.py::test_mock_level_margins_hold -q
2 passed in 4.53s
```

`test_mock_level_margins_hold` is `assert 2.0 - 0.5 >= 1.0` — arithmetic
on literals retyped in a different file from the ones the suite actually
uses. `test_tool_level_stall_exceeds_the_client_timeout` hard-codes
`tool_stall = 7.0` the same way. Neither can observe the values being
guarded. Only `test_default_client_timeout_is_what_the_suites_assume`
(which reads `httpx.AsyncClient().timeout.read`) is a real assertion
about the environment.

## 7. (D) Coverage against `BUILD_PLAN_peakflo.md` §10 M4's 13 cases

All 13 are genuinely covered, with the caveats named. *Verified by local
test* (all named tests were observed passing).

| # | Required case | Covering test(s) | Genuinely covered? |
|---|---|---|---|
| 1 | Normal payment success | `test_sends_put_with_idempotency_key_header`, `test_business_fields_are_preserved`, `test_ok_mode_commits_once` | Yes — ledger asserted |
| 2 | Missing/empty/invalid key | `test_invalid_key_is_a_definite_failure_and_sends_nothing` (params `None, "", "   ", 123, "k"*129`), `test_missing_key_is_rejected_by_the_schema` | Yes — asserts `attempt_count == 0` |
| 3 | Key exceeding documented length | same parametrize + `test_over_long_key_is_rejected`, `test_key_at_documented_maximum_is_accepted` | Yes — both sides of 128 |
| 4 | Timeout after mock commit | `test_timeout_returns_outcome_unknown_not_error` | Yes — asserts ledger 1 while the caller saw a failure |
| 5 | Retry, same key and payload | `test_retry_after_outcome_unknown_does_not_double_pay`, `test_retry_after_ambiguous_timeout_with_same_key_commits_once` | Yes |
| 6 | Same key, changed payload | `test_changing_payload_on_retry_is_rejected_by_xero_contract`, `test_same_key_different_payload_is_rejected` | **Sequential: yes. Concurrent: claimed by `test_concurrent_same_key_different_payload_is_rejected` but not asserted — M4-2** |
| 7 | Different key, legitimate distinct payment | `test_distinct_keys_still_create_distinct_payments`, `test_concurrent_different_keys_all_commit`, `test_reference_is_not_used_as_the_idempotency_key` | Yes |
| 8 | Failure before commit | `test_tool_reports_fail_before_commit_conservatively`, `test_retry_after_failure_before_commit_replays_cached_error`, `test_fail_before_commit_writes_nothing` | Yes — ledger 0, and the conservative direction is asserted |
| 9 | Commit followed by gateway error | `test_gateway_error_after_commit_is_outcome_unknown`, `test_commit_then_502_is_ambiguous_not_failure` | Yes |
| 10 | Expired key requires reconciliation | `test_expired_window_with_start_time_refuses_to_send`, `test_expired_window_returns_reconciliation_required`, `test_expired_window_without_start_time_can_double_pay`, `test_key_exactly_at_ttl_boundary_has_expired`, `test_expired_key_is_treated_as_new_and_can_double_commit` | Yes for the tz-aware path. **No coverage of naive / date-only / non-string / boundary-crossed-in-flight timestamps — M4-1** |
| 11 | Correct payment HTTP method and request body | `test_sends_put_with_idempotency_key_header` (asserts `http_method == "PUT"`), `test_business_fields_are_preserved`, `test_create_payment_still_accepts_all_original_fields` | Yes — method and `{"Payments": [...]}` envelope both read off the wire |
| 12 | Idempotency header reaches the mock endpoint | `test_sends_put_with_idempotency_key_header` (`attempt["idempotency_key"] == KEY`) | Yes — read from the server's attempt log, not the client |
| 13 | Existing relevant Xero tests remain passing | my §3.2 run | **At the M0 baseline (20/37), not passing.** Cause independently confirmed as the pre-existing `_invoke()` bug, and §10 M4's acceptance allows "failures are clearly explained". Honest. |

Nothing is claimed-but-absent. Cases 1–5 and 7–9, 11–12 are carried by
M3-era tests rather than new M4 tests, which is legitimate — the plan
asks for the behaviour to be proven, not for duplicate tests. The three
new regression guards (`test_other_tools_keep_their_optional_idempotency_key`,
`test_out_of_scope_tools_still_exist`,
`test_create_payment_still_accepts_all_original_fields`) are a good
addition that the plan did not ask for.

## 8. (E) The honesty of the expiry story

**Represented honestly, not buried.** The limitation appears in three
places: `BUILD_LOG.md:1161`-area narrative, the Known-limitations bullet
at the end of the M4 section ("the double-pay path remains reachable for
a caller that omits it, which `test_expired_window_without_start_time_can_double_pay`
documents honestly rather than hiding"), and in the tool's own
`OUTCOME_UNKNOWN` guidance, which now ends "Pass `operationStartedAt` on
your attempts so this tool can make that determination for you" — M3's
F-1 is genuinely closed. `MOCK_CONTRACT.md:63-72` explains the mock side
and explicitly refuses to claim permanent exactly-once execution.

Two gaps in the record rather than in the honesty:
`MOCK_CONTRACT.md` does not mention the tool's dependence on
`operationStartedAt`, and `STATUS.md` does not carry the limitation at
all while it does carry "C-4 CLOSED".

**Is the tool's behaviour defensible under §7?** Narrowly, yes. §7's
responsibility boundaries put key persistence and reconciliation on the
agent/orchestrator; a stateless tool that is given no start time cannot
know the key's age, and `idempotency_window_may_have_expired`'s refusal
to "invent an expiry it cannot establish" is the right instinct.

**But it should refuse more aggressively, and the project's own
precedent says so.** §10 M3 task 5 made the caller-supplied key
*required* for this prototype precisely so protection cannot be silently
lost; `operationStartedAt` is the second half of the same protection and
is still `"Optional"` (pfMCP main.py:1226-1235). The consequence is
concrete and ahead of us: M6 evaluates whether an LLM agent follows the
tool's outcomes, and an agent that omits one optional field double-pays
with no warning. Requiring it (or returning a distinct status such as
`KEY_AGE_UNKNOWN` instead of a bare `OUTCOME_UNKNOWN` when it is absent)
closes the hole at no cost to the approved scope. Raised as a condition,
not a defect — the current behaviour is within §7, but it leaves the
milestone's headline safety property contingent on caller goodwill.

Noted for whoever hardens it: `test_expired_window_without_start_time_can_double_pay`
asserts that a double payment **happens**, so it will have to be rewritten
when the tool is hardened. That is worth a comment in the test now.

## 9. (F) Scope and safety

| §4 safety absolute | Result |
|---|---|
| No real payment, message or live write | **Pass.** All traffic to `127.0.0.1`; `call_tool` asserts loopback (tests/test_create_payment_tool.py:47); mock binds `("127.0.0.1", port)` |
| No live Xero/Peakflo endpoint on any path | **Pass.** `grep -rn "https\?://" tests/ mocks/` returns only a stale `.pyc`; no source line targets a non-loopback host |
| No keys, tokens, credentials or real financial data | **Pass.** Only `"fake-local-token-not-a-secret"` / `"fake-local-tenant"` (tests/test_create_payment_tool.py:50) |
| No claim of a real production incident | **Pass.** `MOCK_CONTRACT.md:3-7` and the mock's module docstring both state it |
| No claim of permanent exactly-once execution | **Pass.** `MOCK_CONTRACT.md:71-72` states the opposite explicitly |
| Mocks labelled as simulation | **Pass.** Module docstring, contract header, `"__mock__": True` on every response, and the CLI banner prints "LOCAL SIMULATION (not Xero)" |

| Scope check | Result |
|---|---|
| Only `create_payment` touched in pfMCP | **Pass.** `git diff --stat` = 1 file, +47/−0; every hunk is inside the `create_payment` branch (main.py:3196-3238, 3287, 3321) |
| `send_message` / `create_batch_payment` untouched | **Pass.** `git diff \| grep -niE "send_message\|create_batch_payment"` → no matches. `test_out_of_scope_tools_still_exist` and `test_other_tools_keep_their_optional_idempotency_key` additionally pin this from the tool list |
| No unrelated refactor | **Pass with a note.** The mock's 217-line delta is all C-2/C-4 plus the extraction of `_process`, which the reservation genuinely requires. `lookup`/`store` were left behind dead (**M4-9**) |
| No new dependency | **Pass.** `threading` only, already imported |
| `commit_delay_seconds` defaults to 0.0 and never engages normally | **Pass.** Default `0.0` (:159), guarded at :541, set only at tests/test_m4_integration.py:119 |
| No pre-existing user work discarded | **Pass.** `Composio` / `Emergent/*` changes still present in `git status` |

## 10. (G) Record accuracy

| BUILD_LOG M4 claim | Verdict |
|---|---|
| "Prototype suite: 94 passed" | **Accurate.** I observed 94 passed five times |
| "Run twice (79.45 s, 82.22 s) — no flake, no ordering dependence" | **Partly supported.** 94-passed is reproducible (my times 77–85 s). But two runs in the *same* order cannot evidence order independence, and no shuffling plugin is installed. I probed reversed file order and the M4 file alone; **within-file order was not shuffled by either of us** |
| "pfMCP regression: 37 failed / 20 passed — still exactly the M0 baseline" | **Accurate**, and I confirmed the cause is the pre-existing helper bug |
| "+47 lines in `src/servers/xero/main.py`, on top of the committed `eb4685f`" | **Accurate** to the line |
| "With the reservation 1 / Reservation removed 6 — `assert 6 == 1`" (BUILD_LOG:1188-1191, STATUS.md:60) | **Overstated as a figure.** My five runs gave 7, 6, 7, 8, 8. The direction is solid, the number is not (**M4-7**) |
| "C-2 closed" | **Accurate.** `key_is_usable` + `key_treated_as_absent` + two tests; mutation M-C1 kills them |
| "C-4 closed" | **Accurate for the single-payment property**, which I reproduced by mutation. **Not accurate for the conflict half** — M-C6 survives (**M4-2**) |
| "C-5 closed. Four tests pin the relationships" | **Not supported.** Two of the four are arithmetic on literals and survive M-C7 (**M4-4**) |
| "All structured outcomes now carry `requestSent`" (BUILD_LOG:1161) | **Not accurate.** Three of four do; the success path (main.py:3333) returns the raw provider payload with no `status`, `operationId` or `requestSent`. The shape itself is the declared F-8 decision, so the code is fine — the sentence is not (**M4-8**) |
| "`tests/test_m4_integration.py` (new, 20 tests)" | **Accurate.** 20 passed |
| "`tests/test_create_payment_tool.py` (one assertion updated)" | **Near enough** — one replaced, two added, plus the docstring; the reason is recorded in the test, as claimed |
| Commands block (BUILD_LOG:1218) | **Not runnable as written** — `tests/servers/xero/{5 mock files}` is a placeholder (**M4-10**) |
| `STATUS.md:122` "pfMCP/ working tree is **clean**" | **False.** ` M src/servers/xero/main.py`. Same false-cleanliness statement as M3's F-6, recurred (**M4-6**) |

## 11. Acceptance criteria (§10 M4)

| Criterion | Met? | Evidence |
|---|---|---|
| Tests assert both returned status **and** ledger side effects | **Met** | 11 of 20 M4 tests assert `payment_count`, 2 assert `attempt_count`, 1 asserts the attempt log and cached-key list; mutation M-A1 confirmed the ledger assertions bite |
| Tests are deterministic | **Met** | 94 passed in 5 runs including reversed file order and the M4 file alone; no flake. Caveat: within-file order never shuffled (no plugin available); `INFLIGHT_WAIT_SECONDS == `the client timeout is a latent coin flip (**M4-5**) |
| All relevant tests pass, or failures clearly explained | **Met** | 94/94 prototype; pfMCP 20/37 = M0 baseline, cause independently confirmed |
| Automated tests + reproducible commands (deliverable) | **Met** | commands in §3 all ran as written, except the BUILD_LOG placeholder (**M4-10**) |
| 13 required test cases | **Met on paper, with two substantive holes** | §7 table; case 6's concurrent half is unasserted (**M4-2**) and case 10 has no coverage of malformed-but-parseable timestamps (**M4-1**) |

## 12. Adversarial checks (§4)

Retry-model checks: same key + identical payload across retries — **pass**
(`test_retry_after_outcome_unknown_does_not_double_pay`). No per-attempt
key generation — **pass**, no generator exists in the file. `reference`
never used as the key — **pass** (`test_reference_is_not_used_as_the_idempotency_key`).
Same key + different payload rejected — **pass sequentially, unverified
concurrently (M4-2)**. Distinct legitimate operation not blocked —
**pass**. Ambiguous outcome not reported as definite failure — **pass**.
Expiry leads to the approved reconciliation behaviour, not a blind
new-key retry — **pass for tz-aware input, defective for naive input
(M4-1)**. Key validation covers type, non-empty, 128 — **pass**.

Test-quality checks: ledger side effects asserted — **pass**;
deterministic — **pass**; negative and failure cases covered — **pass**;
tests would fail on regression — **partly: 5 of 7 mutations killed, M-C6
and M-C7 survived**.

Record accuracy: **three inaccuracies and one false statement** (§10).

## 13. Defects

| # | Severity | File:line | Defect | Required correction |
|---|---|---|---|---|
| **M4-1** | **High** | `pfMCP/src/servers/xero/main.py:220-235`, used pre-flight at `:3202` | A timezone-less `operationStartedAt` is silently assumed UTC. Because M4 turned this helper into a send/do-not-send gate, a UTC-negative caller's naive local timestamp **refuses a legitimate first payment outright** (reproduced: `payment_count = 0`, `attempt_count = 0`), a UTC-positive caller's naive timestamp makes a genuinely stale key look fresh and **the tool sends with it**, a date-only string hard-blocks, and a non-string epoch sends. No test covers any of these | Treat a naive timestamp as unusable rather than as UTC (return `False` *and* say in the outcome that the key's age could not be established), or require an explicit offset in the schema. Add tests for naive, date-only, future-dated and non-string values, plus the case where the window is crossed while the request is in flight |
| **M4-2** | **Medium** | `tests/test_m4_integration.py:187-209`; behaviour at `mocks/fault_server.py:243-247` | The concurrent same-key/different-payload rejection is asserted nowhere. Mutation M-C6 (`"wait"` instead of `"conflict"`) leaves the whole suite green (94 passed), because the test asserts only `payment_count == 1`. §4's "same key + different payload is rejected" is therefore unverified for the concurrent case that M4 added | Assert that the conflicting caller received `400` with `"used with a different request"`, and that exactly one caller received `200` |
| **M4-3** | **Medium** | `tests/test_m4_integration.py:149-161`; property claimed at `mocks/MOCK_CONTRACT.md:79-80` and `fault_server.py:528-535` | `test_concurrent_waiters_are_released_without_serving_the_full_stall` makes no timing assertion. Mutation M-C3 (publish after the stall) leaves it passing with an unchanged duration (2.36 s vs 2.29 s). It was killed in the full suite only incidentally, by `test_expired_window_without_start_time_can_double_pay` — which means that double-pay demonstration silently depends on the publish ordering | Record each waiter's elapsed time and assert it is well under the owner's stall; add a comment to the expiry test noting its dependence on publish-before-stall |
| **M4-4** | **Medium** | `tests/test_m4_integration.py:348-354`, `:357-359` | Condition C-5 is reported closed by four tests, but two are arithmetic on literals retyped from another file and cannot observe the values they guard. Mutation M-C7 shrinking the real margin at `tests/test_fault_server.py:96` from 2.0/0.5 to 0.6/0.5 left both the behaviour test and `test_mock_level_margins_hold` passing | Hoist the stall/timeout values into module-level constants used by both the behaviour tests and the guard, so the guard observes the real numbers; or delete the two vacuous tests and stop counting them as C-5 evidence. Correct the "four tests pin the relationships" claim either way |
| **M4-5** | Low–Med | `mocks/fault_server.py:73` vs `tests/test_m4_integration.py:51` | `INFLIGHT_WAIT_SECONDS = 30.0` is exactly the test client's `timeout = 30.0`, so at the boundary the mock's `503` and the client's `ReadTimeout` race. Verified bounded, not hanging (M-C8: 31.43 s then a clean failure), but it violates C-5's own margin principle | Give them a real margin — e.g. waiter timeout 10 s against a 30 s client — and assert the relationship the way M4-4's fix asserts the others |
| **M4-6** | Low–Med | `STATUS.md:122`; `git -C pfMCP status`; parent-repo `git status` | The whole M4 deliverable is uncommitted. The pfMCP change is a working-tree modification, and `tests/test_m4_integration.py` plus the 217 changed lines of `mocks/fault_server.py` are not in `2c52b05` and sit in an untracked `Peakflo/`. Meanwhile `STATUS.md:122` asserts the pfMCP tree is "clean" — the same false statement M3's F-6 required to be fixed | Commit the pfMCP change and the prototype M4 files, record both SHAs in `BUILD_LOG.md` M4, and correct `STATUS.md:122`. **Do this before M5**, per M3's F-5 precedent |
| **M4-7** | Low | `BUILD_LOG.md:1188-1191`, `STATUS.md:60` | "6 payments" / "1 vs 6" is one observation, not a figure. Five runs gave 7, 6, 7, 8, 8 | State "6–8 observed across five runs" or "more than one"; the test's `== 1` assertion is the durable claim |
| **M4-8** | Low | `BUILD_LOG.md:1161` vs `main.py:3333` | "All structured outcomes now carry `requestSent`" — the success path carries none of `status`, `operationId`, `requestSent` (the declared F-8 shape) | Reword to name the three ambiguous/reconciliation outcomes, and note that a caller cannot key off `requestSent` on success |
| **M4-9** | Low | `mocks/fault_server.py` ~`:207-228` | `MockState.lookup()` and `MockState.store()` are unreachable after the C-4 rewrite (no caller in `mocks/`, `tests/`, `repro/`), and the attempt-log field `key_expired` was dropped without note | Delete them, or keep them with a comment saying why; mention the dropped attempt field in `MOCK_CONTRACT.md` |
| **M4-10** | Low | `BUILD_LOG.md:1218` (and the same shape at `:860`) | `tests/servers/xero/{5 mock files}` is a placeholder, not a runnable command, in a section headed "Commands run" | Paste the literal command |

## 14. Limitations of this review

1. **Live Xero behaviour: Unknown / Not tested.** I did not contact Xero
   and did not re-verify the documentation this milestone depends on
   (M3's review did that first-hand). Every result here describes this
   client/mock pair.
2. **Not an independent environment or party.** Same session, machine,
   interpreter, venv and checkout as the builder; I was handed the venv
   path and two commands. No substitute for human review.
3. **Mutation coverage is seven mutations, not exhaustive.** Two
   survivors prove two gaps; five kills prove five behaviours are pinned.
   Other unpinned behaviours may remain.
4. **Within-file test ordering was never shuffled** by the builder or by
   me — no randomising plugin is installed. Order independence is
   verified at file granularity only (reversed file order, and the M4
   file in isolation).
5. **Concurrency conclusions are from Windows 11 / CPython 3.14 thread
   scheduling** on one machine. The reservation logic was reviewed by
   reading plus seven mutations; I did not model-check it, and I did not
   run the concurrency tests under load or on another platform.
6. **I did not run** `repro/retry_dup_repro.py` (protects
   `m1_baseline_latest.json`), pfMCP's live-client path, or any
   linter/type checker (M8's job).
7. **The 37 pfMCP failures were not bisected to a pre-M4 commit.** I
   confirmed the cause by reading one failure's traceback (the
   `_invoke()` credential-patch bug, already recorded in M0), not by
   checking out `78cda6e` and re-running.
8. **No diff review was possible for the prototype files from version
   control**; I reconstructed the M4 delta against `2c52b05` on another
   branch, so if anything was changed in the working tree between that
   commit and now by a path other than M4, I would have attributed it to
   M4.

## 15. Verdict

The core of this milestone is good, honest work and I want that on the
record: the builder found a **real** payment-safety defect in their own
M3 code, and I reproduced both halves of it independently — reverting the
guard takes the mock ledger from 1 to 2 payments, and with the guard
`attempt_count` never moves. The C-4 reservation is correct against every
failure mode I probed (deadlock, lost wakeup, raising owner, `reset()`
with waiters, waiter timeout, expired-entry race). Reporting the negative
mutation result *before* building `commit_delay_seconds` is exactly the
discipline this project asks for, and the seam itself is legitimate:
default `0.0`, one caller in the whole repository, documented in two
places, and it discriminates the property under test and nothing else.
All 13 required test cases are covered, the ledger really is asserted,
the suite is green five times over, and the pfMCP baseline is untouched.

It still cannot pass, for two reasons that both sit on the payment path.

**First, the fix is incomplete in a way the milestone's own tests cannot
see (M4-1).** M4 promoted `idempotency_window_may_have_expired` from
choosing a label to deciding whether a payment is sent at all, without
hardening its input. A naive `operationStartedAt` — what
`datetime.now().isoformat()` produces — is silently read as UTC. I
reproduced a legitimate, seconds-old first payment being **refused and
never made** (`payment_count = 0`), and the mirror case in which a
genuinely stale key reads as fresh and the tool **sends anyway**, which
is precisely the duplicate this guard exists to prevent. A date-only
string hard-blocks; an integer epoch sends. Every M4 expiry test uses
either a tz-aware timestamp or `"junk"`, so none of it is visible.

**Second, three of the behaviours this milestone reports as verified are
not (M4-2, M4-3, M4-4).** Mutation M-C6 makes a concurrent conflicting
payload wait and receive the first caller's `200` instead of the
documented `400`, and the entire suite stays green — the test named
"is rejected, not committed" asserts only the ledger. M-C3 moves the
outcome publication to after the stall and the two tests named for that
ordering both pass with unchanged durations. M-C7 shrinks the real
timeout margin to 0.1 s and `test_mock_level_margins_hold` — one of the
four tests cited as closing C-5 — passes, because it is `assert 2.0 - 0.5
>= 1.0` on literals retyped from another file. C-5 is nominally closed,
not substantively closed, and `BUILD_LOG`/`STATUS` say otherwise.

Add that the entire deliverable is uncommitted while `STATUS.md:122`
states the pfMCP tree is clean — the same false statement M3's F-6
already required to be fixed (**M4-6**) — and the gate cannot be passed
on the strength of a claim I just disproved by mutation.

None of this is hard to fix: M4-2, M4-3 and M4-4 are assertions the
existing tests nearly make already, and M4-1 is a few lines in one
helper plus the tests to pin it. I would expect a short, focused
re-submission rather than rework.

**Required before re-submission:** M4-1, M4-2, M4-3, M4-4 and M4-6, plus
the record corrections M4-7, M4-8 and M4-10. M4-5 and M4-9 may be
deferred to M8 if stated as such.

**Recommended, and the reason I would not wave it through to M6:** make
`operationStartedAt` required, or return a distinct status when it is
absent. M6 evaluates whether an LLM agent follows this tool's outcomes,
and today an agent that omits one optional field double-pays with no
warning. If it stays optional, that decision belongs in `BUILD_LOG` as a
declared, Raj-overrulable choice in the way F-8 was, and
`test_expired_window_without_start_time_can_double_pay` needs a comment
saying it asserts a known-bad outcome deliberately.

VERDICT: REJECTED

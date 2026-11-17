# M2 — Fault-injection mock Xero API — Independent review

**Milestone:** M2 (`BUILD_PLAN_peakflo.md` §9, §10 M2)
**Review date:** 2026-11-16
**Reviewer:** Independent quality-gate agent, operating under
`QUALITY_GATE_AGENT.md`. I did not write any file under `mocks/`,
`tests/`, or `repro/`.

---

## 1. Independence — stated honestly, not overclaimed

- **What is genuinely independent:** my context began with the four
  documents named in my instructions. I had not seen `mocks/`, `tests/`
  or the M2 changes to `repro/` before this review. I read every M2
  source file in full, ran the suite myself three times, wrote my own
  probe scripts that drive the mock *without* using the project's test
  suite or its fixtures, and performed mutation testing on a scratch copy.
- **What is not independent, stated plainly:** I am a subagent in the
  **same overall session** as the builder, launched by the same
  orchestrator, on the **same machine, Python interpreter, venv and
  checkout**, and I was handed the venv path and suggested commands.
  This is context-level independence with independent execution and
  independent code reading. It is **not** an independent environment,
  **not** an independent party, and **not** a substitute for human
  review. A defect invisible on this machine (an OS- or
  httpx-version-specific timing assumption, say) is invisible to me too.
- Single platform: Windows 11 10.0.26220, Python 3.14.6, httpx 0.28.1.
  **Not tested** on any other platform or dependency version.
- I read `BUILD_LOG.md` only as a set of claims and verified each M2
  claim I could against code I read and commands I ran.

## 2. What I inspected

| Path | How |
|---|---|
| `R:\Internship_Outreach_prototype\Peakflo\QUALITY_GATE_AGENT.md` | read in full |
| `R:\Internship_Outreach_prototype\Peakflo\BUILD_PLAN_peakflo.md` | read in full (§7, §9, §10 M2, §12, §13 closely) |
| `R:\Internship_Outreach_prototype\Peakflo\BUILD_LOG.md` | read in full, as claims (M0 §6 and the M2 section closely) |
| `R:\Internship_Outreach_prototype\Peakflo\reviews\M1-review.md` | read in full (D-1..D-7) |
| `R:\Internship_Outreach_prototype\Peakflo\mocks\fault_server.py` | read in full (480 lines) |
| `R:\Internship_Outreach_prototype\Peakflo\mocks\MOCK_CONTRACT.md` | read in full |
| `R:\Internship_Outreach_prototype\Peakflo\tests\test_fault_server.py` | read in full (384 lines, 25 tests) |
| `R:\Internship_Outreach_prototype\Peakflo\tests\conftest.py` | read in full |
| `R:\Internship_Outreach_prototype\Peakflo\repro\retry_dup_repro.py` | read in full (401 lines) |
| `R:\Internship_Outreach_prototype\Peakflo\repro\baseline_mock.py` | read in full (271 lines) |
| `R:\Internship_Outreach_prototype\Peakflo\STATUS.md` | read in full |
| `R:\Internship_Outreach_prototype\Peakflo\prompts_for_peakflo.md` | section headings + M2 entry |
| `R:\Internship_Outreach_prototype\Peakflo\repro\results\*.json` | 13 files, hashed and parsed |

**Diff scope.** The project folder is untracked inside its parent
repository, so there is no per-file git diff for M2. I reviewed `mocks/`,
`tests/` as new files and `repro/*.py` as modified files against the
behaviour `reviews/M1-review.md` recorded. Full file inventory outside
`pfMCP/`: `mocks/` (2 files), `tests/` (2 files), `repro/` (2 scripts +
13 result JSONs), `reviews/`, and the five record documents. **No
`eval/` directory, no M3 implementation, nothing under `pfMCP/`.**

## 3. Commands I actually ran, with actual output

### 3.1 The suite, three times (flakiness check)

```
$ cd R:\Internship_Outreach_prototype\Peakflo
$ pfMCP/.venv/Scripts/python.exe -m pytest tests/ -p no:cacheprovider -q
.........................                                                [100%]
25 passed in 15.20s
```
Two further runs: `25 passed in 14.78s`, `25 passed in 14.88s`.
**Verified by local test:** 25 tests, 3/3 runs green, no flake observed.
(Each run emits one `PytestDeprecationWarning` about
`asyncio_default_fixture_loop_scope` from pytest-asyncio — pre-existing
environment noise, not an M2 defect.)

### 3.2 `pfMCP` still unmodified

```
$ git -C R:\Internship_Outreach_prototype\Peakflo\pfMCP status --short
(no output)   EXIT=0
$ git -C ... diff --stat
(no output)
$ git -C ... log -1 --format="%H %ci %s"
78cda6ec779cbb704292500f8f8bd5dfafe9b2f1 2026-11-13 13:35:00 +0700 chore(stage): keep one warm pf-mcp instance with 1 vCPU (#226)
```
**Verified by local test:** clean tree, no staged or unstaged diff, HEAD
is still the SHA recorded in `BUILD_LOG.md` M0 §2.

### 3.3 Independent contract probe — NOT using the project's tests

Script: `<scratchpad>`
(imports `mocks.fault_server` directly, starts its own servers, drives
raw httpx, reads `state.snapshot()` itself).

```
$ pfMCP/.venv/Scripts/python.exe -I probe_contract.py
documented default TTL constant : 360.0
documented max key length       : 128

1 same key/same body  : status 200 200 | ledger 1 | replay flag True | same PaymentID True
2 same key/diff body  : status 400 | ledger 1 | Idempotency Key: K1 is used with a different request.
3 key len 129         : status 400 | ledger-after 1
  key len 128         : status 200 | ledger 1
4 advance  359.0s      : status 200 | ledger 1 | replay True
4 advance  360.0s      : status 200 | ledger 2 | replay None
4 advance  361.0s      : status 200 | ledger 2 | replay None
5 cached error replay : status 500 500 | ledger 0
6 GET with key        : status 200 200 | cached keys [] | ledger 0
7 diff keys/same body : status 200 200 | ledger 2 | distinct PaymentIDs True
8 empty-string key    : status 200 200 | ledger 2 | cached keys []
9 commit_then_502     : status 502 | ledger 1 (expected 1)
9 fail_before_commit  : status 500 | ledger 0 (expected 0)
10 PATCH create       : status 200 | ledger 1 | other path PUT -> 404
```

### 3.4 Mutation testing (my own scratch copy; the real files were not touched)

Harness: `mocks/fault_server.py`, `tests/conftest.py` and
`tests/test_fault_server.py` copied to
`<scratchpad>`.
`conftest.py` puts its own parent directory on `sys.path[0]`, so the
suite imports the **scratch** mock. Unmutated control run there:
`25 passed in 14.96s` — the harness is faithful. Each mutation was
applied, run, then reverted before the next.

| # | Mutation | Result |
|---|---|---|
| A | In the cache-hit branch, replay the cached response **and commit again** (`_mutating_payment`, before `attempt["outcome"] = "REPLAY"`) | **KILLED — 4 failed, 21 passed** |
| B | `if cached.fingerprint != fingerprint:` → `if False:` (stop rejecting conflicting payloads) | **KILLED — 2 failed, 23 passed** |
| C | Expiry comparison `>=` → `>` (`MockState.lookup`) | **SURVIVED — 25 passed** |
| D | `XERO_IDEMPOTENCY_TTL_SECONDS = 360.0` → `3600.0` | **SURVIVED — 25 passed** |
| E | `XERO_MAX_KEY_LENGTH = 128` → `256` | **SURVIVED — 25 passed** |
| F | Drop the `method.upper() in MUTATING_METHODS` guard | **SURVIVED — 25 passed** (vacuous mutation; see M2-3) |
| G | `GET /Payments` marks its response as an idempotency replay when a key is present | **KILLED — 1 failed, 24 passed** |
| H | Naive payload-hash dedupe: reject any body already in the ledger, whatever the key (the false-blocking bug the plan forbids) | **KILLED — 6 failed, 19 passed** |

Mutation A output (the decisive one — note that **every HTTP-status
assertion still passed**; only the ledger assertions caught it):

```
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json().get("__replayed_from_idempotency_cache__") is True
        assert (first.json()["Payments"][0]["PaymentID"]
>       assert state.snapshot()["payment_count"] == 1
E       assert 2 == 1
...
>       assert state.snapshot()["payment_count"] == 1, "retry must not double-pay"
E       assert 2 == 1
FAILED tests/test_fault_server.py::test_same_key_same_payload_replays_and_commits_once
FAILED tests/test_fault_server.py::test_retry_after_ambiguous_timeout_with_same_key_commits_once
FAILED tests/test_fault_server.py::test_cached_internal_error_is_replayed_as_error
FAILED tests/test_fault_server.py::test_key_just_inside_window_still_replays
4 failed, 21 passed in 14.97s
```

Mutation H output (false blocking):
```
FAILED tests/test_fault_server.py::test_same_key_same_payload_replays_and_commits_once
FAILED tests/test_fault_server.py::test_retry_after_ambiguous_timeout_with_same_key_commits_once
FAILED tests/test_fault_server.py::test_identical_payload_with_different_keys_still_creates_two
FAILED tests/test_fault_server.py::test_no_key_means_no_protection
FAILED tests/test_fault_server.py::test_expired_key_is_treated_as_new_and_can_double_commit
FAILED tests/test_fault_server.py::test_key_just_inside_window_still_replays
6 failed, 19 passed in 14.95s
```

### 3.5 Concurrency probe (my own, not in the suite)

`probe_concurrent_key.py`: 24 threads released from a barrier, all issuing
`PUT /api.xro/2.0/Payments` with the **same** key and body, mode
`commit_then_slow`, 20 trials (480 requests).

```
ledger=1 in 20 of 20 trials
```
**Verified by local test:** no double commit observed. The code-level
race described in M2-5 was **not reproduced**; I report it as latent, not
demonstrated.

### 3.6 M1 conditions D-1, D-2, D-3, D-4, D-5

```
$ cd repro && ../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py --delay 1
client read timeout : 5.0s (httpx default, not set by us)
mock stall          : 1.0s   (margin -4.0s)
ERROR: the mock stall must exceed the client read timeout by at
       least 1.0s, but the margin is -4.0s. ...
---- EXIT CODE: 3 ----
```
No scenario ran and no results file was written. **D-1 verified.**

```
$ pfMCP/.venv/Scripts/python.exe -I probe_loopback.py
  REFUSED : https://api.xero.com -> REFUSING TO RUN: base_url 'https://api.xero.com' is not loopback. ...
  REFUSED : http://api.xero.com:8080 -> ...
  REFUSED : https://app.peakflo.co -> ...
  REFUSED : http://169.254.169.254 -> ...
  ALLOWED : http://127.0.0.1:8788
  ALLOWED : http://localhost:8788
```
**D-4 verified.** (`assert_loopback` is called at
`repro/retry_dup_repro.py:141` before the `XERO_API_BASE` mutation on the
pfmcp path, and at `:177` on the isolated path — confirmed in inspected
code, and both paths are the only two entries in `CLIENTS`.)

```
latest MD5 BEFORE           : 6A3BAE6587E63463E6336B76FD24C3D8
latest reproduced BEFORE    : True

$ ../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py --client isolated
Duplicate effect reproduced in this local setup: True
Saved: ...\m1_baseline_20261116T143204Z.json
NOT updating m1_baseline_latest.json: this was a non-canonical
---- EXIT: 0 ----
latest MD5 after isolated   : 6A3BAE6587E63463E6336B76FD24C3D8  (unchanged: True)

$ ../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py --attempts 1
    DUPLICATE ENTRIES       : 0
Duplicate effect reproduced in this local setup: False
Saved: ...\m1_baseline_20261116T143214Z.json
NOT updating m1_baseline_latest.json: this was a non-canonical
EXIT 1: the duplicate effect was NOT reproduced in this run.
---- EXIT: 1 ----
latest MD5 after attempts=1 : 6A3BAE6587E63463E6336B76FD24C3D8  (unchanged: True)
```
**D-3 verified** (byte-identical across two non-canonical runs) and
**D-2 verified** (exit 1 on non-reproduction — I triggered it via
`--attempts 1`, a path D-1 does not intercept).

```
$ (full canonical run, stdout and stderr redirected to separate files)
exit code      : 0
stderr bytes   : 123
--- STDERR verbatim ---
2026-11-16 20:02:31,202 - httpx - INFO - HTTP Request: POST http://127.0.0.1:57369/api.xro/2.0/Payments "HTTP/1.1 200 OK"
--- end stderr ---
traceback lines in stderr : 0
...
scenario                   attempts  committed  duplicates
control_ok                        1          1           0
baseline_timeout_retry            2          2           1
Duplicate effect reproduced in this local setup: True
Saved: ...\m1_baseline_latest.json  (canonical run)
```
**D-5 verified:** 123 bytes of stderr, zero `Traceback`/`WinError`/
`ConnectionAborted` matches — exactly the builder's claim. The M1
baseline still reproduces (2 attempts, 2 committed, 1 duplicate).

### 3.7 `m1_baseline_latest.json` provenance, reconstructed

`BUILD_LOG.md:661-662` claims `latest` was the builder's
`m1_baseline_20261116T142045Z.json`; `STATUS.md:68` claims it was the M1
reviewer's `...140859Z`. These contradict each other, so I settled it.
The script writes the timestamped file **before** adding `canonical_run`
and `latest` **after**, so each candidate is reconstructible. Hashing raw
on-disk bytes (`probe_latest_provenance2.py`):

```
current latest RAW md5 : e55eb3f445c4a2b0a99fee6b3a182c37   (= Get-FileHash E55EB3F4...)
current latest run     : 2026-11-16T14:32:41.868576+00:00   (my canonical run)

m1_baseline_20261116T142045Z.json  reconstructed-RAW-md5=6a3bae6587e63463e6336b76fd24c3d8  MATCHES_OLD_LATEST=True
(all 12 other candidates: False)
```
**Verified by local test:** before my runs, `latest` *was* the builder's
`...142045Z` canonical run — `BUILD_LOG.md:661-662` is correct and
`STATUS.md:68` is stale. **Disclosure:** my own canonical run in §3.6 has
now replaced `latest` with `m1_baseline_20261116T143241Z.json`
(same client, same settings, same result: reproduced `true`), so
`BUILD_LOG.md:661-662` is stale again. See M2-7.

### 3.8 Safety scans

```
$ URL literals across mocks/, tests/, repro/ (*.py, *.md, *.json)
repro\baseline_mock.py:238:    http://127.0.0.1
tests\test_fault_server.py:383: http://127.0.0.1
mocks\fault_server.py:445:      http://127.0.0.1
   -> three literals, all loopback. No other http(s) URL anywhere.
   -> zero URL matches in repro\results\*.json

$ secret scan: token|secret|bearer|password|api\.xero\.com|peakflo\.com|client_id|sk-
repro\retry_dup_repro.py:149: access_token="fake-local-token-not-a-secret",
repro\retry_dup_repro.py:180: "Authorization": "Bearer fake-local-token-not-a-secret",
   -> self-labelling fakes only; nothing in mocks/, tests/, or results/.

$ out-of-scope / M3 leakage scan in mocks/, tests/
MOCK_CONTRACT.md:63  (prose) ... reason `RECONCILIATION_REQUIRED` exists ...
test_fault_server.py:249 (assertion message) ... requires RECONCILIATION_REQUIRED ...
   -> documentation references only. No send_message, no
      create_batch_payment, no idempotencyKey tool parameter, no
      OUTCOME_UNKNOWN or RECONCILIATION_REQUIRED implementation.
```

## 4. (A) Idempotency correctness vs the official contract in `BUILD_LOG` M0 §6

Checked against the code, not test names. Line references are
`mocks/fault_server.py`.

| Official contract (M0 §6) | Mock behaviour | Code | Evidence |
|---|---|---|---|
| Same key + same request → cached response, **not reprocessed** | Yes. Cache hit returns `cached.status`/`cached.body` plus `__replayed_from_idempotency_cache__`, and `return`s **before** `commit_payment` at `:382` | `:343-364` | §3.3 line 1 (ledger 1, same `PaymentID`); mutation A killed |
| Same key + different request → HTTP 400 | Yes, with the documented message text | `:346-355` | §3.3 line 2; mutation B killed |
| "Different request" = URL, body **or method** changed | Yes — `sha256(METHOD\|path\|canonical-JSON-body)` | `:70-79`, `:321` | §3.3 line 2; `test_put_and_post_are_distinct_requests_for_one_key` |
| Key > 128 chars → HTTP 400 | Yes, documented message, checked **before** the cache lookup, nothing committed | `:332-341` | §3.3 line 3 (129 → 400, 128 → 200) |
| **Expired key = a brand-new key, not an error** | Yes. `lookup` deletes the entry and returns `(None, True)`; the handler falls through to commit | `:147-161`, `:343-345` | §3.3 line 4 (ledger 2, no replay flag) |
| Cached **errors** replayed as errors | Yes. `fail_before_commit` stores `(500, payload)` under the key; replay returns 500 even after the mode changes to `ok` | `:374-378` | §3.3 line 5 (500, 500, ledger 0) |
| Header ignored on GET | Yes, structurally: `do_GET` routes to `_get_payments`, which never touches `idempotency_cache` | `:234-242`, `:280-310` | §3.3 line 6 (no key cached, two plain 200s) |
| No format validation on key values | Matches for non-empty strings; **diverges for the empty string** | `:374`, `:392`, `:403`, `:413` use `if key:` | §3.3 line 8 — see defect M2-2 |
| Retention window 360 s (6 min) | Default constant is `360.0` | `:64` | §3.3 header line; **not asserted by any test** — see M2-1 |

**Conclusion:** the modelled contract is correct on every point I could
check, with one small divergence (M2-2).

## 5. (B) Does the suite prove "one ledger entry"? — the most important question

**Yes, and I proved it rather than assuming it.** The ledger assertion is
not decorative:

- `tests/test_fault_server.py:105-119` asserts both statuses, the replay
  marker, the identical `PaymentID`, **and**
  `state.snapshot()["payment_count"] == 1`.
- `:122-138` replays the M1 scenario (ambiguous timeout, then retry with
  the same key and payload) and asserts
  `payment_count == 1, "retry must not double-pay"`.
- `state` is the **in-process `MockState` object**, obtained from the
  fixture, not a value the HTTP response reports — so the assertion reads
  the real side effect, not the server's self-description.
- Mutation A (§3.4) implemented the exact catastrophic false negative
  described in my instructions — cached response returned **while
  committing twice**. Four tests failed, and the failures were on
  `assert state.snapshot()["payment_count"] == 1`; every HTTP-status and
  replay-marker assertion still passed. Without the ledger assertions
  the suite would have been fully green on a mock that double-pays.

That is the single most important thing M2 had to get right, and it is
right.

## 6. (C) Do the tests fail when the behaviour breaks?

Partly yes, with real gaps. Eight mutations, five killed, three genuine
survivors (plus one vacuous mutation). Full table in §3.4.

- **Killed:** idempotent replay with a second commit (A), conflicting-
  payload acceptance (B), GET honouring the key (G), naive payload-hash
  false blocking (H), and B also killed the method-identity test.
- **Survived, and each is a real test-quality gap:**
  - **C** — flipping the expiry comparison from `>=` to `>` changes
    behaviour at exactly `t == ttl` and **no test notices**. The suite
    probes 359 s and 361 s only.
  - **D** — changing the default TTL from `360.0` to `3600.0` is **not
    caught**. Every test either passes `ttl_seconds` explicitly or relies
    on `conftest.py:32`'s own hard-coded `360.0`. The documented
    six-minute window is therefore asserted nowhere.
  - **E** — changing `XERO_MAX_KEY_LENGTH` from `128` to `256` is **not
    caught**, because the tests build their keys *from the constant*
    (`"k" * (XERO_MAX_KEY_LENGTH + 1)` at `:192`, `"k" * XERO_MAX_KEY_LENGTH`
    at `:204`). The tests verify the mock is self-consistent, not that it
    matches Xero's documented 128.
- **F** was a vacuous mutation on dead code, not a test gap (see M2-3).

## 7. (D) Expiry

- **Injectable clock:** `MockState.now()` is `time.monotonic() +
  self._clock_offset` (`:108-109`); `advance_clock` adds to the offset
  under the lock (`:111-114`); `reset` zeroes it (`:122`). No test sleeps
  for expiry. Deterministic. **Confirmed in inspected code and verified
  by local test.**
- **Default TTL is the documented 360 s** — `XERO_IDEMPOTENCY_TTL_SECONDS
  = 360.0` at `:64`, printed as `360.0` by my probe. **Correct, but not
  test-protected** (mutation D).
- **Boundary:** `lookup` expires at `self.now() - cached.stored_at >=
  self.ttl_seconds` (`:158`), i.e. the key is dead **at** `t == ttl`.
  That is a defensible reading of "stored for 6 minutes, then they
  expire" and is the safer direction (it never over-promises protection).
  My probe confirms: 359 s → replay, **360 s → new key, ledger 2**,
  361 s → new key.
- **Test coverage of the window:** just-inside (359 s,
  `test_key_just_inside_window_still_replays`) and just-outside (361 s,
  `test_expired_key_is_treated_as_new_and_can_double_commit`) are both
  covered, and the latter asserts the ledger grows to 2. **The exact
  boundary `t == ttl` is not covered** — mutation C survives. Low
  severity, but it means the `>=` choice is a code detail no test pins.

## 8. (E) False blocking

**Confirmed, by two routes.**

- My probe (§3.3 line 7): two different keys, **byte-identical**
  payloads → `200`, `200`, ledger **2**, distinct `PaymentID`s. A real
  instalment pair would not be blocked.
- The cache is keyed by the header value, and the payload fingerprint is
  only ever compared *within* an existing key's entry (`:343-346`). There
  is no payload-indexed structure anywhere, so payload-based blocking is
  structurally impossible.
- Mutation H introduced exactly the naive payload-hash implementation the
  plan forbids (§7, §12 rule 11). `test_identical_payload_with_different_keys_still_creates_two`
  (`:168-176`) and `test_no_key_means_no_protection` (`:179-187`) both
  failed. The guard is live, not decorative.

## 9. (F) Safety

- **No non-localhost target on any code path.** Three URL literals exist
  across `mocks/`, `tests/`, `repro/`, all `http://127.0.0.1` (§3.8).
  `make_server` binds `("127.0.0.1", port)` (`:444`); there is no
  outbound client in `mocks/` at all. `repro/` gates both client paths
  through `assert_loopback`, which I confirmed refuses
  `https://api.xero.com`, `http://api.xero.com:8080`,
  `https://app.peakflo.co` and `http://169.254.169.254`.
- **No secrets.** Only `fake-local-token-not-a-secret` /
  `fake-local-tenant` in `repro/`, self-labelling, and not written into
  the results JSONs. Nothing credential-shaped in `mocks/`, `tests/`, or
  `repro/results/`.
- **Labelling is thorough.** `fault_server.py:1-39` opens with "LOCAL
  SIMULATION ONLY. This is NOT Xero", states the evidence boundary
  explicitly, and lists the deliberate simplifications;
  `MOCK_CONTRACT.md:3-7` repeats it in bold and denies any
  production-incident reading; `test_fault_server.py:1-11` says the tests
  prove how the mock behaves, not how Xero behaves; the `--mode` CLI
  banner prints "LOCAL SIMULATION (not Xero)" (`:463`); every response
  body carries `"__mock__": True` (`:310`, `:339`, `:353`, `:372`,
  `:384`, `:397`).
- **No exactly-once claim.** `MOCK_CONTRACT.md:69-70` states in bold that
  the mock "does not provide, and must not be described as providing,
  permanent exactly-once execution", and `fault_server.py:23-26` explains
  why reconciliation is still required.
- **No live write, no real payment, no production-incident claim**
  anywhere in the M2 artifacts.

## 10. (G) Scope

- **`pfMCP` untouched** — §3.2: clean `status --short`, empty
  `diff --stat`, HEAD unchanged.
- **No M3 work has leaked.** There is no `idempotencyKey` tool parameter,
  no `extra_headers` change, no `OUTCOME_UNKNOWN` and no
  `RECONCILIATION_REQUIRED` implementation anywhere in the project. The
  only two matches for those status names are prose in
  `MOCK_CONTRACT.md:63` and an assertion message at
  `test_fault_server.py:249` (§3.8).
- **No out-of-scope tool touched.** Zero matches for `send_message` or
  `create_batch_payment` in `mocks/` or `tests/`.
- **Both PUT and POST accepted for creation** (`:271`, `:274`), with
  method still part of request identity — the correct call: it leaves the
  unresolved PUT-vs-POST contract question to M3 instead of pre-deciding
  it, and `MOCK_CONTRACT.md:26-29` says so.
- **No new dependency.** `httpx` and `pytest` were already in the venv
  from M0. No `requirements` file was added or changed.
- **No unrelated refactoring.** The `repro/` changes are confined to the
  seven M1 conditions (loopback gate, timeout/margin check, canonical-run
  guard, exit codes, abort swallowing, locked `attempt_index`). The
  deliberate decision *not* to extract the shared abort handling into a
  common module is disclosed in `BUILD_LOG.md` M2 "Known limitations" and
  is the right minimal-diff call.
- **No pre-existing user work discarded.** The unrelated dirty paths in
  the parent repository (`../Composio`, `../Emergent/...`) are untouched
  and still dirty.

## 11. Acceptance criteria — `BUILD_PLAN_peakflo.md` §10 M2

Acceptance text: *"All scenarios tested; same key/same body creates one
ledger entry; conflicting body is rejected; distinct keys can create
distinct payments; expiry is testable quickly; mock is clearly
labelled."*

| # | Criterion | Status | Evidence |
|---|---|---|---|
| A1 | All §9 scenarios tested | **Met** | **Verified by local test.** All eight §9 rows present and tested: `ok` (`:62`), `commit_then_slow` (`:92`), `commit_then_502` (`:82`), `fail_before_commit` (`:72`), same key+same payload (`:105`), same key+different payload (`:141`), different key (`:154`), expired key (`:228`). My §3.3 probe reproduced each independently. |
| A2 | Same key + same body → **one** ledger entry | **Met** | §5. Asserted on the in-process ledger, and mutation A proves the assertion bites. |
| A3 | Conflicting body rejected | **Met** | `400` with the documented message, ledger unchanged (§3.3 line 2); mutation B killed. |
| A4 | Distinct keys create distinct payments | **Met** | §8 — including byte-identical payloads. Mutation H killed. |
| A5 | Expiry testable quickly | **Met** | Injectable clock; the full 360 s window is exercised in a test that runs in milliseconds; whole suite 15 s (§7). |
| A6 | Mock clearly labelled | **Met** | §9 — docstring, contract doc, CLI banner, `__mock__` on every response, explicit non-exactly-once statement. |

### Tasks (plan §10 M2, 1-10)

| Task | Status | Evidence |
|---|---|---|
| 1. Mock API, ledger, state reset | Met | `MockState` `:96-176`; `POST /__reset` `:246-251`; `test_reset_clears_ledger_cache_and_clock` |
| 2. Success and failure-before-commit | Met | `:411-417`, `:367-380`; §3.3 line 9 |
| 3. Commit-then-timeout and commit-then-502 | Met | `:400-409`, `:387-398`; ledger 1 in both, verified |
| 4. Idempotency-key cache | Met | `:105`, `:147-165` |
| 5. Same-key/same-payload replay | Met | `:356-364` |
| 6. Same-key/different-payload rejection | Met | `:346-355` |
| 7. Distinct operations with different keys | Met | §8 |
| 8. Configurable TTL/expiry | Met | `make_server(ttl_seconds=...)` `:435`; `POST /__reset {"ttl_seconds": n}` `:248`; `POST /__advance_clock` `:252-256` |
| 9. Deterministic read/reconciliation endpoint | Met | `_get_payments` `:280-310`, exact-match `InvoiceID`/`Reference`; three tests (`:272`, `:288`, `:300`) |
| 10. Isolated tests for every behaviour | **Met with reservations** | 25 tests, fresh server+state per test (`conftest.py:21-50`). Reservations: the three surviving mutants in §6. |

### §9 mock requirements

| Requirement | Status | Evidence |
|---|---|---|
| Local test ledger | Met | `MockState.payments` |
| Cache results by key | Met | `idempotency_cache` |
| Store request-body identity | Met | `fingerprint_request` `:70-79` |
| TTL configurable, models 6 min | Met | default `360.0`; overridable |
| Expose ledger counts | Met | `snapshot()` `:167-176`, `GET /__ledger` |
| Reset between tests | Met | fresh server per test **and** `/__reset` |
| Never call real Xero | Met | §9 — no outbound client exists in `mocks/` |
| Fault injection separate from application code | Met | lives in `mocks/`; `pfMCP/` untouched |

## 12. (H) M1 conditions D-1..D-7, verified individually

| # | Claim | My verdict | Evidence |
|---|---|---|---|
| D-1 | Margin check; `--delay 1` refuses with exit 3 | **Fixed — verified** | §3.6: exit code **3**, explanatory stderr, no scenario run, no results file. `client_read_timeout_seconds()` (`retry_dup_repro.py:97-106`) reads httpx's actual default rather than assuming 5.0; the margin is enforced at `:296-305`. |
| D-2 | Non-zero exit when nothing is reproduced | **Fixed — verified** | §3.6: `--attempts 1` → `EXIT 1: the duplicate effect was NOT reproduced`, exit code **1** (`:378-381`). I deliberately used a path D-1 does not intercept, so this is independently confirmed, not merely "unreachable". |
| D-3 | `*_latest.json` written only on a canonical run | **Fixed — verified, with a structural residual** | §3.6: two non-canonical runs left the file **byte-identical** (MD5 `6A3BAE65…` before and after both). Canonical gate at `:364-375`; every result now embeds `invocation.argv`, the real read timeout and the margin (`:343-347`). Residual: any *canonical* run still clobbers `latest`, and mine did (§3.7, M2-7). |
| D-4 | `assert_loopback` refuses non-loopback | **Fixed — verified** | §3.6: four non-loopback URLs refused, two loopback allowed. Called before the `XERO_API_BASE` mutation (`:141`) and on the isolated path (`:177`). |
| D-5 | No `ConnectionAbortedError` tracebacks | **Fixed — verified** | §3.6: canonical run stderr = **123 bytes**, one httpx INFO line, **zero** traceback/WinError matches. Guards at `fault_server.py:192-196` + `:423-430` and `baseline_mock.py:112-120` + `:212-218`. |
| D-6 | BUILD_LOG timing phrasing corrected | **Partially fixed** | The correction exists (`BUILD_LOG.md:546-549`, "~5.02–5.15 s … not an invariant"), but the original sentence at **`BUILD_LOG.md:468`** still reads "Each timed-out attempt failed after ~5.02–5.05 s" and was not amended in place. A reader of the M1 section alone still meets the uncorrected figure ~80 lines before the correction. See M2-7. |
| D-7 | `attempt_index` assigned inside the lock | **Fixed — confirmed in inspected code** | `mocks/fault_server.py:127-131` and `repro/baseline_mock.py:68-74`: the index is assigned after `with self._lock:`. `test_ledger_exposes_counts_and_keys_for_assertions` (`:346-354`) asserts the index value but **does not** test concurrency — the lock placement is verified by reading, not by test. |

Six of seven are fully fixed and verified by my own execution. D-6 is
partially fixed (record accuracy only). D-3's code fix is real but leaves
a structural residual.

## 13. (I) `BUILD_LOG.md` M2 accuracy

| Claim | Verdict |
|---|---|
| "`tests/test_fault_server.py` — 25 tests" | **Accurate** — 25 collected, 25 passed |
| "`25 passed in 14.94s` (run twice, same result)" | **Accurate** — I observed 15.20 s / 14.78 s / 14.88 s across three runs |
| "git -C pfMCP status --short # empty" | **Accurate** (§3.2) |
| Coverage bullet list (`:632-648`) — 25 described behaviours | **Accurate**, each maps to a real test; I spot-checked every claim against the code and reproduced the contract-level ones in §3.3 |
| "each asserting **both** the HTTP result and the ledger side effect" | **Substantially accurate, with four exceptions.** `test_ttl_is_configurable_for_fast_tests` (`:265`), `test_fingerprint_is_stable_and_order_insensitive` (`:369`) and `test_mock_never_targets_a_non_loopback_host` (`:381`) make no HTTP request at all, and `test_reconciliation_read_returns_nothing_when_nothing_committed` (`:288`) asserts only the read result. All four are legitimately non-ledger tests; the blanket "every test" phrasing overstates it slightly. |
| "Request identity is `sha256(METHOD \| path \| canonical-JSON-body)`" | **Accurate** (`:70-79`) |
| "The default TTL is the documented **360 s**" | **Accurate in code** (`:64`) but **not asserted by any test** (mutation D, §6) |
| "Both PUT and POST accepted … Method still participates in request identity" | **Accurate** |
| "Errors are cached, per Xero's documented behaviour" | **Accurate** (§3.3 line 5) |
| D-1 evidence: "`--delay 1` → **exit 3**" | **Accurate — reproduced** |
| D-1 evidence: "`--delay 6.5` → exit 0" | **Not re-verified by me.** I did not run it, because at `--delay 6.5` the run is *canonical* and would have overwritten `m1_baseline_latest.json` again. The arithmetic (margin 1.5 s ≥ 1.0 s) follows from code I read and the 5.0 s timeout I observed — **inference**, not verified by local test. |
| D-3 evidence: "non-canonical run left the file byte-identical (md5 compared before/after)" | **Accurate — reproduced** |
| D-5 evidence: "stderr … is now 123 bytes, containing a single httpx INFO line and zero tracebacks" | **Accurate — reproduced exactly, 123 bytes** |
| "`m1_baseline_latest.json` is now the canonical run `m1_baseline_20261116T142045Z.json`" (`:661-662`) | **Was accurate when written — proved by hash reconstruction (§3.7) — and is now stale because of my own canonical run.** Not the builder's error. |
| "Known limitations" (server-wide idempotency scope; no OAuth/tenant/rate-limit/field validation; clock tests logic not real elapsed time; duplicated abort handling) | **Accurate and honest**; all four confirmed in code |
| "What this proves / does not prove" | **Accurate and appropriately bounded** |

One contradiction between record files, not caused by me: **`STATUS.md:68`
claims `m1_baseline_latest.json` points at the M1 reviewer's `...140859Z`
run**, which was already false when written — §3.7 proves it was
`...142045Z`.

## 14. Adversarial checks (`QUALITY_GATE_AGENT.md` §4)

**Safety** — all clear.
- [x] No real payment, message, or live write.
- [x] No live Xero/Peakflo endpoint on any path; all three URL literals are loopback; `assert_loopback` enforces it on the repro paths (§9).
- [x] No keys, tokens, credentials or customer data in source, tests, logs or results (§3.8).
- [x] No production-incident claim.
- [x] No permanent exactly-once claim — explicitly denied in `MOCK_CONTRACT.md:69-70`.
- [x] Mocks and simulated results labelled wherever a reader could be misled (§9).

**Retry model (§7)**
- [x] Same logical operation reuses the same key and identical payload — the mock's whole contract, verified.
- [x] No code path generates a fresh key per attempt; the mock never generates keys at all.
- [x] `reference` is never used as, or as a substitute for, the key. It is only a business field inside the payload and a reconciliation read filter.
- [x] Same key + different payload rejected (§3.3 line 2).
- [x] A legitimately distinct operation is **not** blocked for similar business fields (§8) — mutation H proves the guard is live.
- [x] Ambiguous transport outcomes are not reported as definite failures: `commit_then_502` and `commit_then_slow` both commit and the tests assert the divergence between what the caller sees and what happened.
- [x] Expiry leads to the approved behaviour — the mock models the honest, dangerous reality (expired key = new key, second commit) and documents it as the reason `RECONCILIATION_REQUIRED` exists. The state itself is M3's job, correctly absent.
- [x] Key validation covers the documented 128-char maximum. Type/non-empty validation is explicitly caller-side work (plan §7, M3); the mock's handling of the empty string is M2-2.

**Scope and architecture** — all clear (§10).

**Test quality**
- [x] Tests assert both the returned status and the ledger side effect (§5), with the four legitimate exceptions noted in §13.
- [x] Deterministic — 3/3 identical runs; expiry uses an injected clock, not sleeps. Reservation: two tests still rest on an unasserted timing threshold (M2-6).
- [x] Negative and failure cases covered: `fail_before_commit`, over-long key, conflicting payload, cached error, no-key baseline, 404 routing.
- [~] **Would fail if the behaviour regressed — partly confirmed, partly not.** Five of eight mutants killed; three survived (§6). This is the main substantive finding of this review.

**Record accuracy** — §13. Materially accurate; three discrepancies (M2-7), none of which changes a reported result.

## 15. Defects found

**M2-1 — The suite cannot detect a change to Xero's two documented
constants.** Severity: **medium** (test quality / evidence value).
`tests/test_fault_server.py:192` and `:204` build their keys *from*
`XERO_MAX_KEY_LENGTH`, and no test asserts
`XERO_IDEMPOTENCY_TTL_SECONDS == 360.0`. Mutations D (360 → 3600) and E
(128 → 256) both left the suite fully green (§3.4). The two numbers that
come straight from Xero's documentation — the ones that make this a model
*of Xero* rather than a model of itself — are the two the suite does not
pin. **Required correction (M4, or M2 if the builder prefers):** add
assertions on the literal documented values, e.g.
`assert XERO_MAX_KEY_LENGTH == 128` and
`assert XERO_IDEMPOTENCY_TTL_SECONDS == 360.0`, and build the over-long
key from the literal `129` rather than from the constant.

**M2-2 — An empty-string `Idempotency-Key` is silently treated as no
key.** Severity: **low** for M2, **relevant to M3**.
`mocks/fault_server.py:374`, `:392`, `:403`, `:413` all gate the cache
write on `if key:`, so `Idempotency-Key: ""` is accepted, commits, and
caches nothing. My probe (§3.3 line 8) sent it twice and got **two ledger
entries** with `idempotency_keys_cached == []`. Xero's documented
position (BUILD_LOG M0 §6) is that no format validation is applied and
"any string will be accepted", so a real caller sending an empty key
would get a stable (if useless) cache slot, not silent
non-protection. **Required correction (M3/M4, not blocking M2):** either
treat `""` as a key like any other string, or return `400` for it, and
cover it with a test. Either way, M3's tool-side validation must reject
an empty key before the request is built (plan §7 requires non-empty
validation), and that is the more important half.

**M2-3 — Dead condition at `mocks/fault_server.py:332`.** Severity:
**very low** (clarity). `if key is not None and method.upper() in
MUTATING_METHODS:` — `_mutating_payment` is only ever called from
`do_POST`, `do_PUT` and `do_PATCH` (`:271`, `:274`, `:277`), so the
second clause is always true. Mutation F removed it with no test failure
(§3.4), which is correct rather than a gap: the GET path ignores the
header *structurally*, because `_get_payments` never consults the cache.
`test_get_ignores_idempotency_key` therefore passes trivially. It is
still a real test (mutation G killed it), but it does not exercise the
`MUTATING_METHODS` guard. **Required correction:** none required; either
drop the vacuous clause or add a comment saying it documents intent for
future methods.

**M2-4 — The expiry boundary at exactly `t == ttl` is untested.**
Severity: **low**. `mocks/fault_server.py:158` uses `>=`; the suite
probes 359 s and 361 s only, so mutation C (`>=` → `>`) survived. The
`>=` choice is the safer one and my probe confirms it behaves as written
(360 s → new key, second commit). **Required correction (M4):** add a
case at exactly the TTL.

**M2-5 — `lookup` → `commit_payment` → `store` is not atomic per key.**
Severity: **latent / low**, **not reproduced**. Each of the three steps
takes `MockState._lock` separately (`:147-165`, `:133-144`), so two
concurrent requests with the same key could in principle both miss the
cache and both commit. I tried hard to trigger it: 24 barrier-released
threads, same key and body, 20 trials (480 requests) — **ledger = 1 in
20/20** (§3.5). The window is microseconds wide, so this is a code-level
observation, **not** a demonstrated defect. It is the same class of issue
as M1's D-7 and matters only if M5/M6 drive the mock concurrently.
**Required correction (before any concurrent M5/M6 use):** reserve the
key inside a single critical section, or document that the mock is for
sequential use.

**M2-6 — Two tests still rest on an unasserted timing threshold — the
same shape as M1's D-1.** Severity: **low**.
`tests/test_fault_server.py:92-100` and `:122-138` depend on a 0.5 s
client timeout being shorter than a 2.0 s server stall. The 4× margin is
comfortable and I saw no flake in 3 runs, but nothing compares the two
numbers, which is precisely the defect the builder fixed in `repro/` for
D-1. **Required correction (M4):** assert the margin, or derive the
client timeout from the configured stall.

**M2-7 — Three record-accuracy discrepancies.** Severity: **low**
(record accuracy); none changes a reported number.
1. `BUILD_LOG.md:468` still reads "~5.02–5.05 s" — the D-6 correction was
   appended at `:546-549` rather than applied in place, so the M1
   narrative still contains the uncorrected figure. **Required
   correction:** amend `:468` itself, or add an inline pointer to the
   correction.
2. `STATUS.md:68` says `m1_baseline_latest.json` "currently points at the
   reviewer's equivalent re-run (`...140859Z`)". That was already false
   when written: hash reconstruction (§3.7) proves it was the builder's
   `...142045Z`. **Required correction:** fix or drop the sentence.
3. `BUILD_LOG.md:661-662` names `...142045Z` as `latest`. True when
   written, **now stale because of my own canonical run** (`...143241Z`).
   My fault, not the builder's — and it is the structural residual of
   D-3: the canonical-run guard stops *non-canonical* clobbering but any
   canonical re-run still moves the pointer, so prose naming a specific
   file goes stale on every re-run. **Required correction (M5 at the
   latest):** cite the immutable timestamped filename, or have the script
   also write a small provenance file so the record never needs to name
   a run by hand.

**M2-8 — `BUILD_LOG.md:633-634`'s "each asserting **both** the HTTP
result and the ledger side effect" overstates slightly.** Severity:
**very low**. Four of the 25 tests are legitimately not ledger tests
(§13). **Required correction:** soften to "every behavioural test".

## 16. Limitations of this review

1. **Shared session, machine, interpreter and checkout** (§1).
   Independent reading and independent execution; not an independent
   environment or an independent party.
2. **Single platform.** Windows 11 10.0.26220 / Python 3.14.6 / httpx
   0.28.1 only. **Not tested** elsewhere.
3. **Nothing here verifies real Xero behaviour.** I checked the mock
   against the official-documentation claims *as recorded in*
   `BUILD_LOG.md` M0 §6. I did **not** re-fetch
   `developer.xero.com`, so M0's transcription of the contract is an
   input I accepted, not something I re-verified. If M0 misread the
   guide, M2 faithfully models the misreading and my review would not
   catch it. **Unknown.**
4. **Mutation testing is a sample, not a proof.** Eight mutations on the
   paths my instructions named plus a few I chose. A mutant I did not
   write could still survive. I did not run a systematic mutation tool.
5. **The concurrency race (M2-5) is unresolved, not disproven.** 480
   concurrent same-key requests did not trigger it; the code path that
   permits it is still there.
6. **I did not re-run pfMCP's own test suite** (M0 scope; `BUILD_LOG`
   records 20 passed / 37 failed from a pre-existing helper bug).
   **Not tested** by me. I verified only that the checkout is unmodified.
7. **I did not verify `--delay 6.5` → exit 0** (§13), to avoid
   overwriting `latest` a second time. **Inference** from code read plus
   the observed 5.0 s timeout.
8. **Files I wrote outside `reviews/`.** Running the repro necessarily
   created three `repro/results/*.json`
   (`m1_baseline_20261116T143204Z.json`,
   `...143214Z.json`, `...143241Z.json`) and rewrote
   `m1_baseline_latest.json` to my canonical run (disclosed in §3.7 and
   M2-7). The builder may delete my three files; they are review
   artifacts, not a code defect. I edited **no** implementation file and
   fixed **no** defect. My scratch work lives in
   `<scratchpad>`
   (`mutate\` — the mutated copies; `probe_contract.py`,
   `probe_loopback.py`, `probe_concurrent_key.py`,
   `probe_latest_provenance.py`, `probe_latest_provenance2.py`,
   `canon_out.txt`, `canon_err.txt`) and can be discarded.
9. **The injectable clock verifies expiry *logic*, not real elapsed-time
   behaviour** — the builder states this himself, and I agree it is the
   right trade for determinism.

## 17. Verdict

Every M2 acceptance criterion in `BUILD_PLAN_peakflo.md` §10 is met, and
each one is backed by output I produced myself. The modelled idempotency
contract matches `BUILD_LOG` M0 §6 on every point I could check: replay
without a second commit, 400 on a conflicting body, 400 on an over-long
key, an expired key behaving as a brand-new key, cached errors replayed
as errors, and the header ignored on GET. The single most important
property — that the suite genuinely proves one ledger entry rather than
one cached HTTP response — holds, and I proved it by breaking the mock in
exactly that way and watching four tests fail on the ledger assertion
while every status assertion still passed. False blocking is
structurally impossible and actively guarded. No code path leaves
127.0.0.1, no secret appears anywhere, labelling is consistent and the
non-exactly-once boundary is stated in bold. `pfMCP` is untouched and no
M3 work has leaked in. All seven M1 conditions are addressed; five I
reproduced by execution, two by reading.

The defects are test-coverage and record-hygiene issues, not correctness
failures of the mock. The one I would not let drift is M2-1: the suite's
assertions are derived from the very constants that encode Xero's
documented contract, so the mock is currently verified to be
self-consistent rather than verified to match the documentation. That
matters more at M4, which is where the contract claims become the
project's headline evidence.

VERDICT: APPROVED WITH CONDITIONS

**Conditions.** None blocks the start of M3.

| # | Condition | Safe to proceed to M3? | Must be resolved by |
|---|---|---|---|
| C-1 (M2-1) | Assert the literal documented constants (`XERO_MAX_KEY_LENGTH == 128`, `XERO_IDEMPOTENCY_TTL_SECONDS == 360.0`) and build the over-long key from the literal `129`, so the two numbers taken from Xero's documentation are pinned by a test | Yes | **M4** (must not survive into M5, where these become headline evidence) |
| C-2 (M2-2) | Decide and test the empty-string key: treat it as a key or reject it with `400`. Independently, M3's tool-side validation **must** reject an empty key before building the request (plan §7) | Yes | mock side **M4**; tool side **M3** |
| C-3 (M2-4) | Add an expiry test at exactly `t == ttl`, pinning the `>=` boundary | Yes | M4 |
| C-4 (M2-5) | Reserve the key in one critical section, or document the mock as sequential-use only | Yes | **Before any concurrent M5/M6 run** |
| C-5 (M2-6) | Assert the client-timeout-vs-stall margin inside the test suite, as `repro/` now does for D-1 | Yes | M4 |
| C-6 (M2-7) | Amend `BUILD_LOG.md:468` in place; fix or drop `STATUS.md:68`; stop naming a specific run as `latest` in prose (cite the timestamped file, or emit a provenance file) | Yes | Next record update, and **M5** for the `latest` pointer |
| C-7 (M2-8) | Soften `BUILD_LOG.md:633-634` to "every behavioural test" | Yes | Next record update |
| C-8 (M2-3) | Optional: drop or comment the vacuous `MUTATING_METHODS` clause at `fault_server.py:332` | Yes | No deadline — cosmetic |

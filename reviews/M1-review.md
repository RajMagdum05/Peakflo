# M1 — Baseline duplicate-effect reproduction — Independent review

**Milestone:** M1 (`BUILD_PLAN_peakflo.md` §10 M1)
**Review date:** 2026-11-16
**Reviewer:** Independent quality-gate agent (separate agent, fresh
context, no part in authoring `repro/`), operating under
`QUALITY_GATE_AGENT.md`.

## 1. Independence — stated honestly

- I did not write, and had not seen, any file under `repro/` before this
  review. My context began with the three documents named in my
  instructions.
- **Limitation, stated rather than glossed over:** I am a subagent
  running inside the *same overall session* as the builder, launched by
  the same orchestrator, and I was given the environment hints (venv
  path, suggested commands) by that orchestrator. I share the builder's
  machine, Python interpreter, and checkout. So this is *context-level*
  independence with independent execution and independent code reading —
  **not** an independent environment, and not an independent party. A
  defect that is invisible on this machine (e.g. an OS- or
  httpx-version-specific timing assumption) would be invisible to me
  too.
- I read `BUILD_LOG.md` only as a set of claims, and verified each M1
  claim against code I read and commands I ran myself (§3, §7).

## 2. What I inspected

| Path | How |
|---|---|
| `R:\...\Peakflo\QUALITY_GATE_AGENT.md` | read in full |
| `R:\...\Peakflo\BUILD_PLAN_peakflo.md` | read in full |
| `R:\...\Peakflo\BUILD_LOG.md` | read in full (as claims) |
| `R:\...\Peakflo\STATUS.md` | read in full |
| `R:\...\Peakflo\repro\baseline_mock.py` | read in full (241 lines) |
| `R:\...\Peakflo\repro\retry_dup_repro.py` | read in full (318 lines) |
| `R:\...\Peakflo\repro\results\*.json` (6 files + `_latest`) | parsed, scanned |
| `R:\...\Peakflo\pfMCP\src\servers\xero\main.py` | lines 43-44, 140-234, 3030-3074, 4250-4262 |
| `R:\...\Peakflo\prompts_for_peakflo.md` | M1 entries |

Diff scope: the project folder `R:\Internship_Outreach_prototype\Peakflo`
is **untracked** inside its parent repository (`git status --short` in it
reports `?? ./`), so there is no per-file diff to review for M1. I
reviewed the artifacts as new files. Only `repro/` (plus `reviews/`,
`STATUS.md`, record files) exists; there is no `mocks/`, no `tests/`, and
no modification anywhere under `pfMCP/`.

## 3. Commands I actually ran, and actual output

### 3.1 pfMCP checkout unmodified (plan §10 M0/M1 constraint)

```
$ git -C R:\Internship_Outreach_prototype\Peakflo\pfMCP status --short
(no output)   EXIT=0
$ git -C ... diff --stat
(no output)
$ git -C ... log -1 --format='%H %ci %s'
78cda6ec779cbb704292500f8f8bd5dfafe9b2f1 2026-11-13 13:35:00 +0700 chore(stage): keep one warm pf-mcp instance with 1 vCPU (#226)
```
**Verified by local test:** working tree clean, no staged/unstaged diff,
HEAD is exactly the SHA recorded in `BUILD_LOG.md` M0 §2. No M1 change
leaked into the inspected repository.

### 3.2 Reproduction, default (`pfmcp`) client — run 1

```
$ cd repro && ../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py
```
Actual output (abridged only where identical lines repeat; the stderr
traceback shown first is reproduced verbatim and is discussed as D-3):

```
2026-11-16 19:36:20,461 - httpx - INFO - HTTP Request: POST http://127.0.0.1:57054/api.xro/2.0/Payments "HTTP/1.1 200 OK"
----------------------------------------
Exception occurred during processing of request from ('127.0.0.1', 57196)
Traceback (most recent call last):
  File "C:\Python314\Lib\socketserver.py", line 697, in process_request_thread
  ...
  File "C:\Python314\Lib\socket.py", line 729, in readinto
ConnectionAbortedError: [WinError 10053] An established connection was aborted by the software in your host machine
----------------------------------------
========================================================================
M1 BASELINE REPRODUCTION -- LOCAL SIMULATION ONLY, NOT XERO
No real Xero or Peakflo endpoint is contacted. No real payment.
========================================================================

=== scenario: control_ok ===
    mock mode   : ok (LOCAL SIMULATION, not Xero)
    mock url    : http://127.0.0.1:57054
    client      : pfmcp
    retry policy: new operation each attempt, NO stable key
    attempt 1: SUCCESS after 0.695s
      -> caller got a definite answer; stopping retries
    ATTEMPTS MADE           : 1
    INTENDED OPERATIONS     : 1
    LEDGER ENTRIES COMMITTED: 1
    DUPLICATE ENTRIES       : 0
    IDEMPOTENCY KEYS SEEN   : [None]

=== scenario: baseline_timeout_retry ===
    mock mode   : commit_then_slow (LOCAL SIMULATION, not Xero)
    mock url    : http://127.0.0.1:57195
    client      : pfmcp
    attempt 1: EXCEPTION after 5.145s (ReadTimeout: '')
      -> caller cannot tell if the payment happened; retrying
    attempt 2: EXCEPTION after 5.088s (ReadTimeout: '')
      -> caller cannot tell if the payment happened; retrying
    ATTEMPTS MADE           : 2
    INTENDED OPERATIONS     : 1
    LEDGER ENTRIES COMMITTED: 2
    DUPLICATE ENTRIES       : 1
    IDEMPOTENCY KEYS SEEN   : [None, None]

scenario                   attempts  committed  duplicates
control_ok                        1          1           0
baseline_timeout_retry            2          2           1

Duplicate effect reproduced in this local setup: True
Saved: R:\...\repro\results\m1_baseline_20261116T140631Z.json
```

### 3.3 Reproduction, `--client isolated`

```
$ ../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py --client isolated
```
```
control_ok              : attempt 1 SUCCESS after 0.448s; committed 1; duplicates 0
baseline_timeout_retry  : attempt 1 EXCEPTION 5.033s (ReadTimeout: ''),
                          attempt 2 EXCEPTION 5.11s  (ReadTimeout: '')
                          ATTEMPTS 2 | COMMITTED 2 | DUPLICATES 1
Duplicate effect reproduced in this local setup: True
Saved: .../m1_baseline_20261116T140708Z.json
```
(Same WinError 10053 stderr block appeared again.)

### 3.4 Determinism probe — stall shorter than the client timeout

```
$ ../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py --delay 1
    attempt 1: SUCCESS after 0.245s   -> control_ok,   committed 1, duplicates 0
    attempt 1: SUCCESS after 1.019s   -> timeout_retry, committed 1, duplicates 0
Duplicate effect reproduced in this local setup: False
```
This is the expected and *safe* direction of failure (no duplicate is
invented), but see D-1/D-2: the script accepted a self-defeating `--delay`
silently, and it overwrote `m1_baseline_latest.json` with
`duplicate_effect_reproduced: false`.

### 3.5 Independent spy check — does the default client really drive pfMCP's helper?

Script written to my scratchpad (not to the project):
`<scratchpad>`
— it wraps `xero_main.call_xero_api` with a spy, then calls
`retry_dup_repro._attempt_pfmcp` directly.

```
$ ../pfMCP/.venv/Scripts/python.exe -I <scratchpad>/spy_check.py
call_xero_api module: src.servers.xero.main
call_xero_api file  : R:\Internship_Outreach_prototype\Peakflo\pfMCP\src\servers\xero\main.py
XERO_API_BASE default: https://api.xero.com
spy saw: {'endpoint': '/api.xro/2.0/Payments',
          'base_at_call_time': 'http://127.0.0.1:60121',
          'kwargs': {'method': 'POST',
                     'data': {'Payments': [{'Invoice': {'InvoiceID': '1111...'},
                                            'Account': {'AccountID': '2222...'},
                                            'Amount': 1000.0,
                                            'Date': '2026-11-16',
                                            'Reference': 'INV-DEMO-001'}]}}}
attempt outcome: SUCCESS
XERO_API_BASE restored to: https://api.xero.com
ledger committed: 1
ledger payload: {'Payments': [{'Invoice': {...}, 'Account': {...}, 'Amount': 1000.0, 'Date': '2026-11-16', 'Reference': 'INV-DEMO-001'}]}
```

### 3.6 URL / secret scans

```
$ grep -rniE "https?://[a-zA-Z0-9.-]+" --include=*.py repro/
repro/baseline_mock.py:209:    base_url = f"http://127.0.0.1:{server.server_address[1]}"
   (the ONLY URL literal in M1 source)

$ grep -rniE "token|secret|bearer|api.xero.com|peakflo.com|password" repro/results/
   (only matches: "idempotency_key": null)
```

### 3.7 Builder's own result files, re-parsed by me

| file | client | delay | reproduced | timeout elapsed_s |
|---|---|---|---|---|
| `m1_baseline_20261116T140244Z.json` | pfmcp | 7.0 | true | 5.032, 5.023 |
| `m1_baseline_20261116T140311Z.json` | isolated | 7.0 | true | 5.046, 5.019 |
| `m1_baseline_20261116T140339Z.json` | pfmcp | 7.0 | true | 5.051, 5.046 |

All carry `"label": "LOCAL SIMULATION - mock server on 127.0.0.1, not Xero"`
and `environment.httpx_default_timeout: "Timeout(timeout=5.0)"`.

## 4. Acceptance criteria (plan §10 M1)

Plan acceptance text: *"Reproducible local test; attempts and committed
entries are visible; no Xero/Peakflo calls; no production-incident
claims."*

| # | Criterion | Status | Evidence |
|---|---|---|---|
| A1 | Reproducible local test | **Met** | **Verified by local test** — 3 of my own runs (§3.2, §3.3, plus the final restore run `...140859Z`) reproduced `duplicates = 1` identically; builder's 3 runs match. Caveat in D-1. |
| A2 | Attempts and committed entries visible | **Met** | Terminal shows `ATTEMPTS MADE` / `LEDGER ENTRIES COMMITTED` / `DUPLICATE ENTRIES` / `IDEMPOTENCY KEYS SEEN`; JSON carries `attempts_made`, `ledger_entries_committed`, `duplicate_entries` and the full per-attempt ledger (`baseline_mock.py:87-94`, `retry_dup_repro.py:226-237`). |
| A3 | No Xero/Peakflo calls | **Met** | **Verified by local test** — only URL literal in M1 source is `http://127.0.0.1:{port}` (`baseline_mock.py:209`); the pfmcp client points `XERO_API_BASE` at that mock before the call and the spy confirmed `base_at_call_time = http://127.0.0.1:60121` (§3.5). httpx's own request log line shows the target host. Residual hardening note in D-4. |
| A4 | No production-incident claims | **Met** | `baseline_mock.py:25-31`, `retry_dup_repro.py:34-41`, banner `retry_dup_repro.py:247-250`, closing text `:272-274`, JSON `label`, and `BUILD_LOG.md` "What this proves / does not prove" all state the opposite explicitly. |

### Tasks (plan §10 M1 tasks 1-6)

| Task | Status | Evidence |
|---|---|---|
| 1. Minimal local mock endpoint | Met | `baseline_mock.py:97-189`, stdlib `ThreadingHTTPServer`, `127.0.0.1`, ephemeral port |
| 2. `commit_then_slow` = record first, then delay past client timeout | **Met — mechanism confirmed in code, not just in the summary** | `baseline_mock.py:170-181`: `committed = self.state.commit_payment(...)` on **line 174** executes *before* `time.sleep(self.delay_seconds)` on **line 175**, and the 200 response is only attempted on line 177 after the sleep. The commit is therefore unconditionally durable in the ledger before the client can time out. The post-sleep write is wrapped against `BrokenPipeError/ConnectionResetError/OSError` (`:178-180`) because the client has already gone. |
| 3. Baseline client retrying as a new operation, no stable key | Met | `retry_dup_repro.py:195-199` + comment; no key is generated anywhere in M1 (`grep` shows the only `Idempotency-Key` touch is the mock *reading* it, `baseline_mock.py:158`). Observed `IDEMPOTENCY KEYS SEEN: [None, None]`. |
| 4. Record attempts and ledger entries | Met | `LedgerState.record_attempt` / `commit_payment` / `snapshot` (`baseline_mock.py:68-94`) |
| 5. Demonstrate two entries for one intended operation | Met | Observed in every 7 s-delay run: `intended_operations 1`, `ledger_entries_committed 2` |
| 6. Save actual output, labelled a local simulation | Met | `repro/results/*.json` with `label`, `milestone`, `generated_at_utc`, `environment` (`retry_dup_repro.py:276-299`) |

## 5. Adversarial checks (`QUALITY_GATE_AGENT.md` §4)

**Safety**

- [x] No real payment/message/live write. **Verified by local test.**
- [x] No live Xero/Peakflo endpoint on any code path, including the
      demo path. Only `127.0.0.1`. (D-4 is a hardening note, not a
      violation — no call was ever made to a non-local host.)
- [x] No keys/tokens/credentials/customer data in source, results, or
      output. The only credential-shaped strings are the literals
      `"fake-local-token-not-a-secret"` / `"fake-local-tenant"`
      (`retry_dup_repro.py:114-115, 144-145`), which are self-labelling
      and are **not** written into the results JSON (headers are not
      recorded).
- [x] No real-incident claim.
- [x] No exactly-once claim. M1 makes no idempotency claim at all.
- [x] Mocks and results explicitly labelled simulation — docstrings,
      banner, per-scenario line `mock mode : ... (LOCAL SIMULATION, not
      Xero)`, and the JSON `label` field.

**Retry model (§7)** — mostly *out of scope for M1 by design*: M1's whole
job is to show the **unprotected** baseline.

- [x] No code path generates a fresh key per attempt — because no key is
      generated at all. The baseline's defect is correctly modelled as
      *absence* of a key, which matches the inspected handler
      (`pfMCP main.py:3057-3063` passes no `extra_headers`). Confirmed in
      inspected code.
- [x] `reference` is **not** used as an idempotency key: it is carried
      only as the business field `Reference` (`retry_dup_repro.py:94-95`),
      exactly as `main.py:3054-3055` does.
- [x] Ambiguous outcome is not reported as definite failure *by the
      repro's own framing* ("caller cannot tell if the payment
      happened"). Note the repro also correctly records that the
      **current pfMCP code** would render it as the near-useless string
      `"Error: "` — see §6 note N-1, which I verified.
- n/a Same-key replay, conflicting-payload rejection, expiry,
      128-char validation — all M2/M3/M4 scope; correctly absent.

**Scope and architecture**

- [x] Only M1 work is present. **I specifically checked for M2/M3 leakage
      and found none:** `baseline_mock.py` has no idempotency cache, no
      TTL/expiry, no conflict detection, no reconciliation endpoint and
      no `fail_before_commit`/`commit_then_502` modes — `MODES = ("ok",
      "commit_then_slow")` (`:45-47`), and the omission is documented as
      deliberately M2's (`:16-23`, `:148-151`). No `mocks/` directory
      exists. No file under `pfMCP/` was modified (§3.1). No
      `OUTCOME_UNKNOWN`/`RECONCILIATION_REQUIRED` implementation exists
      yet (M3). No test suite was added (M4).
- [x] No unrelated refactoring, reformatting, or dependency upgrade. No
      new dependency at all: `httpx` was already in the venv for M0.
- [x] Existing conventions preserved — the payload builder is a verbatim
      copy of the handler's shape (verified field-by-field, §6 D-5 covers
      the copy-vs-import trade-off).
- [x] No out-of-scope tool touched (`send_message`,
      `create_batch_payment` untouched; nothing touched at all).
- [x] No pre-existing user work discarded. Unrelated dirty paths in the
      parent repo (`../Composio`, `../Emergent/...`) are untouched and
      still dirty.

**Test quality**

- [x] Both the returned status **and** the mock ledger side effect are
      asserted/reported — `attempt_records[*].outcome` *and*
      `ledger.payment_count`. This is the single most important thing M1
      had to get right, and it did.
- [~] Determinism: deterministic in practice on this machine across 6
      runs, but it rests on a **2-second margin between two numbers that
      are never compared** — see D-1. Not a flaky race in the
      *concurrency* sense (the commit strictly precedes the stall, so the
      side effect cannot be lost), but a timing-threshold dependency.
- [x] A negative/control case exists (`control_ok`), and my `--delay 1`
      probe shows the harness does not hard-code the duplicate result.
- [x] Would it fail if behaviour regressed? Partly confirmed: my
      `--delay 1` run flipped `duplicate_effect_reproduced` to `false`,
      so the metric is genuinely computed from the ledger, not asserted
      into existence. There is, however, **no assertion and no non-zero
      exit code** on failure — `main_async` returns 0 regardless
      (`retry_dup_repro.py:300`). See D-2.

**Record accuracy** — see §6 D-6/D-7 for the discrepancies I found;
otherwise every `BUILD_LOG.md` M1 claim I tested held. Specifically
verified true: file list; the four-row results table; `[None, None]`
keys; "pfMCP untouched"; "payload builder is a verbatim copy of
main.py:3047-3055"; "no idempotency cache (that is M2)"; and the
`"Error: "` inference.

## 6. Defects and notes

**D-1 — Determinism rests on an unchecked 2 s margin between two numbers
that are never compared.** Severity: **medium** (evidence robustness).
`retry_dup_repro.py:310-311` defaults `--delay 7.0` with help text "must
exceed client timeout", but nothing enforces it. The client-side 5.0 s is
**never set by this project** — it is httpx's implicit default, observed
as `Timeout(timeout=5.0)` and only *recorded after the fact* in the
`environment` block (`:290`). Neither client passes an explicit
`timeout=` (`retry_dup_repro.py:112-118`, `:150-155`;
`pfMCP main.py:189` constructs `httpx.AsyncClient()` with no timeout
either). Consequences: a slower machine is harmless (it only widens the
gap), but an httpx default change, an `HTTPX_*`/env influence, or a
careless `--delay` silently converts the milestone's headline result from
`true` to `false` with no error — I demonstrated exactly that in §3.4.
**Required correction (safe to defer to M2, must not survive past M5,
since M5 compares baseline against improved behaviour and a silent flip
there would corrupt the comparison):** read the client timeout
explicitly (e.g. a module constant passed to both clients), and refuse to
run — or at minimum emit a loud warning — when
`delay <= client_timeout`. Do not merely document it.

**D-2 — The repro always exits 0, even when it reproduces nothing.**
Severity: low-medium. `retry_dup_repro.py:267` computes `reproduced` and
prints it, but `main_async` returns `0` unconditionally (`:300`), so no
CI step or wrapper can detect a non-reproduction. Combined with D-1 this
is how a silent regression would reach a report. **Required correction
(M2 or M4):** return a non-zero exit code when
`baseline["duplicate_entries"] == 0` in the `commit_then_slow` scenario
(or move the assertion into the M4 test suite and have the script assert
its own precondition).

**D-3 — `m1_baseline_latest.json` is a mutable pointer that any run can
clobber, including a non-canonical one.** Severity: **medium**
(evidence integrity), and it bit this review. `retry_dup_repro.py:296-297`
rewrites `m1_baseline_latest.json` on *every* invocation, and `STATUS.md`
("Latest measured result ... From `repro/results/m1_baseline_latest.json`")
treats that file as the authoritative measured result. `BUILD_LOG.md` M1
already shows the symptom — the builder had to run the script a third
time "so latest = pfmcp". During §3.4 my `--delay 1` probe overwrote
`latest` with `duplicate_effect_reproduced: false, mock_delay_seconds: 1.0`.
**Disclosure:** I restored it by re-running the default command once
(output §3.2 pattern; new canonical file
`repro/results/m1_baseline_20261116T140859Z.json`, delay 7.0, client
pfmcp, reproduced `true`), so `latest` is again a representative pfmcp
run — but it is now **my** run, not the builder's `...140339Z` run that
`BUILD_LOG.md` M1 names as the source of its table. The three
builder-generated timestamped files are untouched and remain the
builder's evidence. **Required correction (M2):** either write `latest`
only for a canonical/default invocation, or have `STATUS.md`/`BUILD_LOG`
cite an immutable timestamped filename instead of `latest`. My three
added result files (`...140631Z`, `...140708Z`, `...140859Z`) plus
`...140738Z` (the `--delay 1` probe) are review artifacts; the builder
may delete them — they are not a defect in the code.

**D-4 — Safety on the pfmcp path depends on one global assignment, with no
assertion.** Severity: low for M1 as written; **worth fixing before any
concurrent use**. `retry_dup_repro.py:108-109` mutates the module global
`xero_main.XERO_API_BASE`, and `:137` restores it in `finally` — so
between attempts the module again holds the real
`https://api.xero.com` (I observed this in §3.5). Nothing asserts that
the URL actually used is loopback. M1 is sequential, so no real call can
occur, and none did. But M5/M6 may run scenarios concurrently or in
threads, where a restore racing an in-flight call could point a request
at the live host (with a fake token, so it would fail — still a violation
of "no live endpoint is contacted"). **Required correction (before M5, not
M1):** assert the resolved URL starts with `http://127.0.0.1:` immediately
before the call, or inject the base URL per call instead of mutating a
module global.

**D-5 — Unhandled Windows socket teardown prints a raw traceback to
stderr on every ambiguous attempt.** Severity: low (cosmetic, but it
pollutes captured evidence). Observed in both §3.2 and §3.3:
`ConnectionAbortedError: [WinError 10053]` raised from
`socketserver.process_request_thread` → `handle_one_request` →
`rfile.readline`. `baseline_mock.py:176-180` guards only the *response
write*, not the keep-alive read that follows once the client aborts
(`protocol_version = "HTTP/1.1"`, `:103`, keeps the connection alive).
`BUILD_LOG.md` M1 does not mention this output at all. It is harmless to
the result, but M5/M7 will capture terminal output into deliverables.
**Required correction (M2, when the mock is rewritten anyway):** override
`handle_one_request`/`handle` to swallow the expected client-abort
errors, or set `protocol_version = "HTTP/1.0"` for the stall mode.

**D-6 — `BUILD_LOG.md` M1 timing range is accurate for the builder's runs
but reads as an invariant.** Severity: very low (record accuracy).
`BUILD_LOG.md` M1: "Each timed-out attempt failed after ~5.02–5.05 s".
Builder's own JSONs give 5.019–5.051 — **accurate**. My runs on the same
machine gave 5.088, 5.145, 5.033, 5.11 — outside the stated range.
**Required correction:** phrase as "~5.0 s (observed 5.02–5.15 s across
runs)" or attribute the range to the specific recorded runs. No other
number in the M1 section was wrong.

**D-7 — Minor, `baseline_mock.py:162`.** `"attempt_index":
len(self.state.attempts) + 1` is computed *outside* the lock that
`record_attempt` then takes (`:69-72`), so under concurrent requests two
attempts could share an index. M1 is strictly sequential, so this is
latent only. **Required correction (M2):** compute the index inside the
lock (the method already returns the locked length — use that).

**N-1 (not a defect — a verified finding worth carrying forward).** I
independently confirmed the builder's inference about the agent-facing
error text. `httpx.ReadTimeout`'s `str()` is `''` (observed:
`ReadTimeout: ''`), and the inspected dispatcher catch-all is exactly
`except Exception as e:` / `return [TextContent(type="text", text=f"Error:
{str(e)}")]` at `pfMCP src/servers/xero/main.py:4258-4260`. So an agent
would receive the literal string `"Error: "` — no outcome information at
all. **Inference (code-level, dispatcher not executed)**, correctly
labelled as such in `BUILD_LOG.md`. This strengthens the M3 case and
should be quoted with its label intact.

**N-2.** Payload fidelity is **exact**, checked field by field:
`retry_dup_repro.py:88-96` vs `pfMCP main.py:3047-3055` — same four keys,
same nesting (`Invoice.InvoiceID`, `Account.AccountID`), same
`Amount`/`Date`, same conditional `Reference` under the same
`if arguments.get("reference")` guard, and the same `{"Payments": [payment]}`
envelope as `main.py:3062`. The spy in §3.5 shows the bytes that actually
reach the mock match. The copy-not-import decision is forced (the code is
inline in the dispatcher) and is disclosed in `BUILD_LOG.md` M1 notes and
in the function docstring; the drift risk is real but unavoidable at M1
and is mitigated when M3/M4 test the handler itself.

**N-3.** `requirements`/environment: Python 3.14.6, httpx 0.28.1,
Windows-11-10.0.26220. Recorded in every results file. No new dependency
introduced by M1.

## 7. Limitations of this review

1. **Shared session/machine** (§1). Independent reading and independent
   execution; not an independent environment or an independent party.
2. **Single platform.** Everything I observed is Windows 11 / Python
   3.14.6 / httpx 0.28.1. The 5 s client timeout is an httpx default I
   observed, not a contract I verified across versions. **Not tested** on
   any other platform, Python, or httpx version.
3. I did **not** execute the real MCP dispatcher, so the `"Error: "`
   agent-facing string remains **inference from code**, not **verified by
   local test** (the builder labels it the same way, correctly).
4. I did **not** re-run pfMCP's own test suite this milestone (M0 scope;
   `BUILD_LOG` records 20 passed / 37 failed from a pre-existing helper
   bug). **Not tested** by me.
5. I did not verify any claim about Xero's real behaviour. Nothing in M1
   depends on one, and nothing in M1 asserts one.
6. I ran the repro 4 times (3 default/isolated + 1 probe) + 1 spy script.
   That is enough to rule out obvious flakiness on this machine; it is
   **not** a stress test under CPU contention. **Not tested:** behaviour
   under heavy load, where only D-1's margin protects the result.
7. I wrote files outside `reviews/`: running the repro necessarily
   created 4 new `repro/results/*.json` and rewrote
   `m1_baseline_latest.json` (disclosed in D-3), and I wrote one
   throwaway script to my scratchpad. I edited **no** implementation
   file, and applied **no** fix for any defect above.

## 8. Verdict

Every M1 acceptance criterion in `BUILD_PLAN_peakflo.md` §10 is met and
independently verified. The duplicate arises from exactly the mechanism
claimed (commit at `baseline_mock.py:174`, stall at `:175`), the default
client genuinely drives pfMCP's own unmodified `call_xero_api()`, the
payload is byte-faithful to the inspected handler, no code path leaves
127.0.0.1, no secret appears anywhere, labelling is thorough, and no
M2/M3 work has leaked in. The defects are robustness and
evidence-hygiene issues, not correctness failures of the milestone's
claim.

VERDICT: APPROVED WITH CONDITIONS

**Conditions** (all safe to proceed to M2 immediately; none blocks M2's
start):

| # | Condition | Safe to proceed to M2? | Must be resolved by |
|---|---|---|---|
| C-1 (D-1) | Compare the client timeout and the mock delay explicitly; refuse or loudly warn when `delay <= timeout`, and set the client timeout explicitly rather than inheriting httpx's default | Yes | **M2** (the mock is rewritten there); must not survive into **M5** |
| C-2 (D-2) | Non-zero exit / hard assertion when the duplicate is not reproduced | Yes | M2 or M4 |
| C-3 (D-3) | Stop citing the clobberable `m1_baseline_latest.json` as authoritative evidence, or write it only on a canonical run; `STATUS.md` must point at an immutable timestamped file | Yes | **M2** |
| C-4 (D-4) | Assert loopback immediately before the request, or stop mutating the `XERO_API_BASE` global | Yes | **Before M5** (mandatory if any scenario runs concurrently) |
| C-5 (D-5, D-7) | Swallow the expected Windows client-abort teardown; move `attempt_index` inside the lock | Yes | M2 |
| C-6 (D-6) | Correct the `~5.02–5.05 s` phrasing in `BUILD_LOG.md` M1 to show it is a per-run observation (reviewer observed 5.03–5.15 s) | Yes | Next `BUILD_LOG` update |

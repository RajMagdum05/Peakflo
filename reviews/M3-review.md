# M3 — Minimal Xero tool implementation — Independent review

**Milestone:** M3 (`BUILD_PLAN_peakflo.md` §10 M3)
**Date:** 2026-11-16
**Reviewer:** independent reviewer agent, fresh context. I did not write
any of the code under review and had not seen the M3 diff or
`tests/test_create_payment_tool.py` before this review.
**Policy applied:** `QUALITY_GATE_AGENT.md` §3 (evidence labels), §4
(adversarial checks), §5 (verdicts), §6 (report format).

## 0. How independent this review actually was — stated honestly

**Stronger than M1 and M2 on the single most important axis.** The M2
reviewer explicitly disclosed that it did **not** re-fetch
`developer.xero.com` and therefore "faithfully models the misreading" if
M0 misread the guide, calling this "the single largest unverified
dependency in the project so far". **I re-fetched all three official
pages myself, from the live site, and verified the quotations
character-by-character** (§3.A). That dependency is now discharged.

**The same limitations as M1 and M2 otherwise, and they are real:**

- Same session, same machine, same Python 3.14.6 interpreter, same
  `pfMCP/.venv`, same checkout. Not an independent environment and not
  an independent party. Not a substitute for human review — which
  matters more here than in any previous milestone, because this diff
  changes code that creates payments.
- I was handed the venv path and the suggested commands. I ran them, and
  also ran things nobody suggested (the mutation campaign, the httpx
  hierarchy probe, the direct helper probes).
- Windows only. No Linux/macOS run, no Python 3.10 run (the version the
  repo's own `Dockerfile` targets).
- I did **not** run `repro/retry_dup_repro.py`, specifically to avoid
  rewriting `repro/results/m1_baseline_latest.json` a third time.
  Verified afterwards: every file in `repro/results/` still has its
  pre-review mtime (latest `2026-11-16T20:02`).
- I did not call any live Xero or Peakflo endpoint. I did open
  `developer.xero.com` documentation pages in a browser — public
  documentation only, no credentials, no API calls, no project or
  personal data sent.
- **I changed no project file except this one.** All experiments ran
  against a scratch copy outside the project.

## 1. What I inspected

| Item | Detail |
|---|---|
| Repo | `R:\Internship_Outreach_prototype\Peakflo\pfMCP` |
| Branch | `feat/retry-safe-create-payment` |
| HEAD | `78cda6ec779cbb704292500f8f8bd5dfafe9b2f1` (identical to `main`) |
| Diff under review | **uncommitted working tree**, `src/servers/xero/main.py`, 1 file, +218 / −12, 8 hunks |
| New tests | `tests/test_create_payment_tool.py` (290 lines, 19 test cases) |
| Documents | `QUALITY_GATE_AGENT.md`; `BUILD_PLAN_peakflo.md` §4.3, §5, §6, §7, §8, §10 M3, §12, §13; `BUILD_LOG.md` (M0 §6–§7, M2 verdict, M3 section); `reviews/M2-review.md`; `STATUS.md` |

I read every changed hunk in its surrounding context, plus
`call_xero_api()` in full (`main.py:229-311`), the dispatcher catch-all
(`main.py:4464-4466`), and the two untouched `format_xero_error` raise
sites (`main.py:412`, `main.py:451`).

**Finding, up front: nothing is committed.**

```
$ git -C pfMCP diff main...HEAD --stat
(empty)
$ git -C pfMCP branch -vv
* feat/retry-safe-create-payment 78cda6e chore(stage): keep one warm pf-mcp instance...
  main                           78cda6e [origin/main] chore(stage): keep one warm...
$ git -C pfMCP status --short
 M src/servers/xero/main.py
```

The branch exists but holds **zero commits**. The entire M3 deliverable
lives only in the working tree. `BUILD_LOG.md` M3 ("Branch:
`feat/retry-safe-create-payment` … Diff: 1 file, +218 / −12") and
`STATUS.md` ("Complete — on branch `feat/retry-safe-create-payment`")
both read as though the work is committed. It is not. See defect **F-5**.

## 2. Commands I actually ran, with actual output

### 2.1 Prototype suite

```
$ cd R:\Internship_Outreach_prototype\Peakflo
$ pfMCP/.venv/Scripts/python.exe -m pytest tests/ -p no:cacheprovider -q
..............................................                           [100%]
46 passed in 51.90s
```

**46 passed** — matches the builder's claim (27 mock + 19 new tool
tests). *Verified by local test.*

### 2.2 pfMCP regression vs the M0 baseline

```
$ cd R:\Internship_Outreach_prototype\Peakflo\pfMCP
$ .venv/Scripts/python.exe -m pytest tests/servers/xero/test_accounting_expansion.py \
    tests/servers/xero/test_attachment_download.py tests/servers/xero/test_get_invoice_pdf.py \
    tests/servers/xero/test_update_invoice_status.py tests/servers/xero/test_imda_tools.py \
    -p no:cacheprovider -q
37 failed, 20 passed in 2.99s
```

**20 passed / 37 failed — exactly the M0 baseline. Not made worse.**
*Verified by local test.*

Cause check (not taken on trust):

```
$ grep -c "credentials_missing" <run output>
48
$ grep -E "^E  " <run output> | grep -v credentials_missing | sort -u
AttributeError: 'NoneType' object has no attribute 'args'
AssertionError: Expected 'mock' to be called once. Called 0 times.
IndexError: list index out of range
AssertionError: assert 0 == 1
```

48 `credentials_missing` occurrences, and every other message is a
downstream symptom of the mocked `call_xero_api` never being invoked —
i.e. the pre-existing `_invoke()` patch-ordering bug documented in
`BUILD_LOG.md` M0 §7. **No new failure cause.** The builder's "all 48
credential-bug occurrences" is accurate. *Verified by local test.*

Structural corroboration: all 37 failures abort *before* reaching
`call_xero_api`, and the only shared-code change in the diff is inside
`call_xero_api`'s `>= 400` branch — so these tests are structurally
incapable of being affected by it.

### 2.3 httpx exception hierarchy — the ordering question

```
$ pfMCP/.venv/Scripts/python.exe -c "...__mro__..."
httpx 0.28.1
ConnectError   -> ['NetworkError', 'TransportError', 'RequestError', 'HTTPError']
ConnectTimeout -> ['TimeoutException', 'TransportError', 'RequestError', 'HTTPError']
PoolTimeout    -> ['TimeoutException', ...]
ReadError      -> ['NetworkError', ...]
ConnectError issubclass NetworkError: True
ConnectTimeout issubclass TimeoutException: True
```

**Both subclass relationships are real.** `ConnectError` *is* a
`NetworkError`; `ConnectTimeout` *is* a `TimeoutException`. Both are
matched by the second `isinstance` tuple. The code is therefore only
correct because the early return at `main.py:189-191` runs **first** —
the ordering is load-bearing, and it is correct. *Verified by local
test.*

### 2.4 Direct probe of all three new helpers

```
$ pfMCP/.venv/Scripts/python.exe -I -c "<probe>"
--- validate_idempotency_key ---
None      -> REJECT: ValueError idempotencyKey is required and must be a string...
''        -> REJECT: ValueError idempotencyKey must not be empty or whitespace.
'   '     -> REJECT: ValueError idempotencyKey must not be empty or whitespace.
123       -> REJECT: ValueError idempotencyKey is required and must be a string...
True      -> REJECT: ValueError idempotencyKey is required and must be a string...
b'x'      -> REJECT: ValueError idempotencyKey is required and must be a string...
'k'*128   -> OK
'k'*129   -> REJECT: ValueError idempotencyKey must be at most 128 characters (got 129).

--- is_ambiguous_transport_outcome ---
ConnectError           ambiguous=False      <- never delivered: DEFINITE. correct
ConnectTimeout         ambiguous=False      <- correct
ProxyError             ambiguous=False
ReadTimeout            ambiguous=True       <- correct
WriteTimeout           ambiguous=True
PoolTimeout            ambiguous=True       <- see F-4
ReadError/WriteError   ambiguous=True
CloseError             ambiguous=True
NetworkError           ambiguous=True
TimeoutException       ambiguous=True
RemoteProtocolError    ambiguous=True
LocalProtocolError     ambiguous=False
UnsupportedProtocol    ambiguous=False
status_code=400/404/409/429/499  ambiguous=False
status_code=500/502/503          ambiguous=True
status_code=None                 ambiguous=False
ValueError                       ambiguous=False
json.JSONDecodeError             ambiguous=False   <- see F-3

--- idempotency_window_may_have_expired ---
None  -> False     ''   -> False     'junk' -> False     12345 -> False
'2020-01-01T00:00:00Z' -> True       '2099-01-01T00:00:00Z' -> False
```

*Verified by local test.* The classifier does what its docstring claims
for every httpx transport exception and every status code I tried, and
the expiry helper refuses to invent an expiry from absent, non-string or
unparseable input.

## 3. The probes the brief asked for

### (A) The contract decision — verified against live official docs myself

`WebFetch` returned only page titles (the site is JavaScript-rendered,
as warned), so I loaded the pages in a browser and extracted the
rendered `<article>` text.

**`https://developer.xero.com/documentation/api/accounting/payments`:**

- Overview: `Methods Supported` → `GET, PUT, POST`
- `PUT Payments` → "Use this method to apply payments to approved AR and
  AP invoices, refund AR or AP credit notes, refund spend or receive
  overpayments, or refund spend or receive prepayments."
- `POST Payments` → "Use this method to delete (reverse) payments to
  invoices, credit notes, prepayments & overpayments. … **Payments
  cannot be modified, only created and deleted.**" Required parameter:
  `PaymentID`. "In order to delete a payment, you must POST to the
  resource ID for the payment. e.g `POST /Payments/b05466c8-…`" with
  body `{"Status": "DELETED"}`.

**`https://developer.xero.com/documentation/api/accounting/invoices`:**

- `POST Invoices` → "Use this method to create or update an invoice."
- `PUT Invoices` → "The PUT method is similar to the POST Invoices
  method, however **you can only create new invoices with this
  method.**"

**Verdict on (A): "PUT creates / POST deletes" is exactly what Xero
currently documents for Payments, and the Invoices comparison is
accurate verbatim.** Both of the builder's quoted table cells are
correct, and M0 §6's transcription is correct. *Official documentation,
re-fetched live by me on 2026-11-16.*

**The payload is also verified, not just the method.** The documented
`PUT Payments` multi-payment example is:

```json
{"Payments": [{"Invoice": {"InvoiceID": "…"}, "Account": {"AccountID": "…"},
               "Date": "2009-07-13", "Amount": 3375.00}]}
```

This is byte-for-byte the shape the handler builds at `main.py:3177-3185`
and sends at `main.py:3195-3202`, with the documented optional
`Reference` field added conditionally. The payload was correctly left
unchanged.

**Idempotency guide**
(`…/guides/idempotent-requests/idempotency`), re-fetched: "Xero will
only process idempotency for requests that mutate data, I.e. POST, PUT
and PATCH" · "keys are stored for 6 minutes from the time of the first
call, after which they expire. Repeating the same key after expiry won't
produce this error and will instead be processed as a new key, this
should be avoided" · "If your idempotency key is over 128 characters,
Xero will return a 400 response" · "A different request is considered
where any part of the endpoint URL, request body or HTTP method has
changed" · "We don't apply any validations to the supplied idempotency
keys and any string will be accepted". **`XERO_IDEMPOTENCY_MAX_KEY_LENGTH
= 128` and `XERO_IDEMPOTENCY_WINDOW_SECONDS = 360` are both correct, and
`PUT` is an idempotency-eligible method — so the method change does not
break the header.** *Official documentation.*

**Is the change adequately justified?** Yes, and the builder's reasoning
is the right reasoning: `POST` is a fine create verb on ordinary Xero
endpoints, but on `/Payments` the `POST` slot is occupied by deletion
*because* payments cannot be modified. The move to `PUT` is therefore a
correction, not a stylistic preference, and it is no longer an
"unverified change" — I verified it independently against the live
source. **What remains Unknown is what `POST /Payments` (collection, no
`PaymentID`, payment body) actually does in production today.** The
builder states exactly this limitation, in those terms. Honest.

### (B) Safety of the retry semantics

**Same key genuinely reused; no per-attempt or derived key.**
*Confirmed in inspected code.*

```
$ grep -nE "uuid|secrets|random|token_hex|sha256|hashlib|md5" src/servers/xero/main.py
(no matches)
```

There is **no key-generation primitive anywhere in the file.** The key
reaches the wire by exactly one route:
`arguments.get("idempotencyKey")` (`main.py:3174`) →
`validate_idempotency_key` → `extra_headers={"Idempotency-Key":
idempotency_key}` (`main.py:3201`). One dispatch = one attempt; identity
is owned entirely by the caller, as `BUILD_PLAN` §7 requires. No
`sha256(invoice|amount|date)` derivation (the rejected v2-plan
behaviour) exists.

**`reference` is not conflated with the key.** *Confirmed in inspected
code.* `arguments["reference"]` is written only to
`payment["Reference"]` (`main.py:3184-3185`). It never reaches
`extra_headers`, `operationId`, or any validation path. The schema
description now says so explicitly ("Business metadata only — this is
NOT an idempotency key and must not be used as one"). Proven at runtime
by `test_reference_is_not_used_as_the_idempotency_key`: same
`reference`, two keys → 2 payments, `keys == ["key-A", "key-B"]`.

**Ambiguous never reported as definite, and vice versa.** See §2.3/§2.4.
The classification is correct for every case I probed, and the
`isinstance` ordering genuinely achieves the connect-error carve-out
despite the inheritance. Two caveats found: **F-3** (a 2xx with an
unparseable JSON body is classified definite — the dangerous direction)
and **F-4** (`PoolTimeout` classified ambiguous although never sent —
the safe direction).

**The tool never recommends a new key.** *Confirmed in inspected code.*
`OUTCOME_UNKNOWN`: "Do not generate a new key and do not change the
amount, date, invoice or account". `RECONCILIATION_REQUIRED`: "do NOT
generate a new key. First read back the payment state". Tool
description: "do not create a new key and do not change any field". All
three ambiguous-path strings forbid it; there is no code path that
suggests it.

**`RECONCILIATION_REQUIRED` and refusing to invent an expiry.** It fires
only when `operationStartedAt` is supplied *and* parses *and* ≥ 360 s
have elapsed (`main.py:206-226`, `main.py:3209`). Absent, non-string or
unparseable input returns `False` — it does **not** guess. That half is
right and tested. **But `operationStartedAt` is optional, so the default
path cannot establish the window at all, and the `OUTCOME_UNKNOWN`
guidance it falls back to tells the agent to retry with the same key
with no window caveat.** See defect **F-1** — the most substantive
finding in this review.

### (C) Does the old bug actually go away?

**Yes.** *Confirmed in inspected code and verified by local test.*

The catch-all is now at `main.py:4464-4466`:

```python
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
```

(the M1-era line ~4258 plus the diff's 206 net lines = 4464 — consistent).
`httpx.ReadTimeout`'s `str()` is `''`, so this path yields exactly
`"Error: "`. The new handler returns its structured JSON from **inside**
the `except` block at `main.py:3264-3268`, so the exception never
propagates to the catch-all for an ambiguous outcome.

I did not take that on reading alone. Mutation **M-3** (§3.D) disabled
the classifier and the old bug reappeared verbatim in the captured log:

```
ERROR    xero:main.py:4466 Error executing tool create_payment:
```

— an empty message, i.e. `"Error: "`. With the real code,
`test_timeout_returns_outcome_unknown_not_error` asserts
`outcome["status"] == "OUTCOME_UNKNOWN"`, `text != "Error: "`, **and**
`payment_count == 1`, and it passes. The structured result reaches the
caller as `result.content[0].text` through the real
`create_server(...).dispatch(...)`, not a stub.

### (D) Test quality — mutation campaign

I copied `mocks/`, `tests/`, `pytest.ini` and `pfMCP/src` to
`<scratchpad>`,
confirmed the unmutated copy gives **19 passed in 36.54s**, then mutated
only the scratch copy, one mutation at a time, restoring the pristine
file between each. **The real `pfMCP/src/servers/xero/main.py` was never
edited** (confirmed afterwards: `git status --short` still shows exactly
one modified file, `+218/-12`, HEAD unchanged).

| # | Mutation | Result |
|---|---|---|
| M-1 | `method="PUT"` → `"POST"` | **killed** — 1 failed: `assert 'POST' == 'PUT'` at `test_create_payment_tool.py:93` |
| M-2 | `extra_headers={"Idempotency-Key": …}` → `{}` | **killed** — 4 failed, incl. `test_retry_after_outcome_unknown_does_not_double_pay` and `test_reference_is_not_used_as_the_idempotency_key` (`assert [None, None] == ['key-A','key-B']`) |
| M-3 | `is_ambiguous_transport_outcome` → always `False` | **killed** — 6 failed; old `"Error: "` bug reproduced in the log |
| M-4 | delete the `ConnectError`/`ConnectTimeout` early return | **SURVIVED — 19 passed** |
| M-5 | `idempotency_window_may_have_expired` → always `True` | **killed** — 5 failed (the tool invents an expiry) |
| M-6 | delete the empty/whitespace key rejection (regress C-2) | **killed** — 2 failed (`[]` and `[   ]` params) |
| M-7 | delete the 128-character limit check | **killed** — 1 failed (`bad_key4`) |

**6 killed, 1 survived.**

Both behaviours the brief named are genuinely protected:

- **(i) same-key retry not double-paying** — M-2 killed
  `test_retry_after_outcome_unknown_does_not_double_pay`. The
  `payment_count == 1` ledger assertion is doing real work, consistent
  with what the M2 reviewer found for the mock.
- **(ii) ambiguous-vs-definite classification** — M-3 killed 6 tests,
  including every reconciliation test.

**M-4 is a significant finding.** Removing the carve-out that makes a
never-delivered connect failure *definite* changes zero test results.
The suite contains no test — unit or end-to-end — of
`is_ambiguous_transport_outcome` against a `ConnectError`, and the mock
is always listening, so no end-to-end test can produce one. The
docstring's most carefully-argued distinction ("Connect failures mean
the request was never delivered, so the payment definitely did not
happen") is **asserted nowhere**. See defect **F-2**.

### (E) Scope and minimality — clean

*Confirmed in inspected code.*

```
$ git diff --name-only
src/servers/xero/main.py
$ git diff -U0 main -- src/servers/xero/main.py | grep ^@@
@@ -17 +17 @@          <- + timezone import (used)
@@ -151,0 +152,77 @@    <- new constants + 3 helpers, beside existing helpers
@@ -217 +294,6 @@       <- call_xero_api: attach .status_code
@@ -1084 +1166,8 @@     <- create_payment description
@@ -1106 +1195,31 @@    <- create_payment schema properties
@@ -1109 +1228,7 @@     <- create_payment required list
@@ -3046,0 +3172,5 @@    <- key validation
@@ -3057,7 +3187,83 @@   <- create_payment send + ambiguous handling
```

- **One file, 8 hunks, all five regions attributable to M3.** No
  reformatting, no reordering, no renaming, no dependency change
  (`timezone` comes from the stdlib `datetime` already imported).
- **`send_message` untouched** — it lives in `src/servers/peakflo/`,
  which is not in the diff at all.
- **`create_batch_payment` untouched** — not in any hunk.
- **The `call_xero_api` change is genuinely additive.** The only
  behavioural delta in the `>= 400` branch is `error.status_code =
  response.status_code` on the instance. Same exception type
  (`Exception`), same message (same `format_xero_error` call, same
  arguments). I confirmed attribute assignment on a bare `Exception`
  cannot itself raise. There are **72 `await call_xero_api` call sites**
  and 66 tools in the file; none can observe the change unless it reads
  `.status_code`, and only `create_payment` does. *Confirmed in
  inspected code.* The 20/37 regression result is consistent with this.
- **The other two `format_xero_error` raise sites were correctly left
  alone** — `main.py:412` and `main.py:451`, both in GET-only
  attachment/PDF download helpers that return `response.content`. Both
  verbatim unchanged; neither appears in any hunk. Correct: neither has
  an ambiguous-outcome consumer.
- **No later-milestone work leaked.** One observation, not a defect: the
  19 new tests already cover most of M4's listed test cases. M3's
  deliverables explicitly include "tests", so this is in scope, but M4
  will have less left to do than the plan implies — worth noting so M4
  is not reported as having independently proved what M3 already proved.

### (F) The required-key decision — consistent with the plan, documented honestly

§10 M3 task 5 says make it **required** "unless M0 reveals a compelling
compatibility constraint. If optionality is proposed, document the
bypass risk and seek approval." The builder chose **required** — the
plan's default — and so needed no approval. M0 §5's finding that
`add_attachment`/`upload_attachment`/`email_invoice` make the key
*optional* was weighed and judged a convention rather than a compelling
constraint. **Consistent with the plan.** *Confirmed in inspected code:*
`main.py:1228-1234` lists `idempotencyKey` in `required`.

The breaking-change risk is documented in `BUILD_LOG.md` under its own
heading, "Required vs optional key — decision and its cost", in plain
language ("this is a **breaking interface change** for existing
`create_payment` callers"), flagged explicitly for Raj to confirm before
any PR, with the one-line alternative named. **Honest and surfaced, not
buried.** Defence in depth is also real: even if the MCP schema layer
did not enforce `required`, `validate_idempotency_key(None)` rejects —
verified in §2.4.

### (G) Safety absolutes — all clear

| Check | Result |
|---|---|
| No live Xero/Peakflo call anywhere, tests included | **Pass.** The only URL literals in `tests/` and `mocks/` are `http://127.0.0.1:` (`mocks/fault_server.py:450`, `tests/test_fault_server.py:420`). `test_create_payment_tool.py:46-47` asserts `urlparse(base_url).hostname in ("127.0.0.1","localhost","::1")` *before* mutating `XERO_API_BASE`, and restores it in a `finally`. The pre-existing `XERO_API_BASE = "https://api.xero.com"` default is untouched and never used in a test. |
| No credentials or secrets | **Pass.** The only credential-shaped string in the new tests is the literal `("fake-local-token-not-a-secret", "fake-local-tenant")` at `test_create_payment_tool.py:50`. Nothing else matched `api[_-]?key\|token\|secret\|password\|bearer`. |
| No production-incident claim | **Pass.** The M3 record makes none; the diff's comments cite only `developer.xero.com`. |
| No permanent exactly-once claim | **Pass.** The schema description states Xero retains a key for 6 minutes and "after that it no longer protects the operation"; both ambiguous outcomes carry `idempotencyWindowSeconds: 360`. |
| Mocks labelled | **Pass.** `test_create_payment_tool.py:13` — "LOCAL SIMULATION ONLY. No real Xero endpoint, credential, or payment." |

### (H) Accuracy of `BUILD_LOG.md` M3 — mostly accurate; discrepancies listed

| Claim | My observation |
|---|---|
| 1 file, +218 / −12 | **Accurate** (working tree) |
| Prototype suite 46 passed | **Accurate** (51.90s here vs 52.11s claimed — immaterial) |
| pfMCP regression 37 failed / 20 passed, identical to M0 | **Accurate** |
| "all 48 credential-bug occurrences" | **Accurate** — `grep -c` gives exactly 48 |
| 19 new end-to-end tool tests | **Accurate** |
| Both official-docs quotations (Payments, Invoices) | **Accurate verbatim** — re-fetched live |
| `PUT` sent with `Idempotency-Key`; business fields preserved | **Accurate** |
| invalid/missing/empty/over-long keys are definite failures that send nothing | **Accurate** — `attempt_count == 0` asserted and passing |
| timeout/502 after commit → `OUTCOME_UNKNOWN`, ledger shows commit | **Accurate** |
| retry with same key leaves exactly one payment | **Accurate** |
| changed payload with same key rejected; distinct keys create distinct payments | **Accurate** |
| expired window → `RECONCILIATION_REQUIRED` pointing at `list_payments` | **Accurate** |
| unparseable/recent `operationStartedAt` does not invent an expiry | **Accurate** |
| identical `reference` with different keys → two payments | **Accurate** |
| "two other `format_xero_error` raise sites… deliberately left alone" | **Accurate** |
| "`call_xero_api` (**2 added lines**, additive only)" | **Imprecise.** The hunk is −1 / +6 (one line replaced by two statements and three comment lines). "Additive only" is correct; "2 added lines" is not. → **F-7** |
| M3 §"Changes made" bullet list | **No claim about the success-path response shape.** It still returns the raw Xero payload, not §8's `{"status":"SUCCESS", …}`, and carries no replay marker. Defensible under §8 ("do not break client compatibility unnecessarily") but undeclared. → **F-8** |
| "Branch `feat/retry-safe-create-payment`… `main` is untouched" | **Misleading.** The branch has no commits; `git diff main...HEAD` is empty. → **F-5** |
| `STATUS.md` "Safety posture: `pfMCP/` checkout unmodified — `git status` clean" | **False as of M3.** → **F-6** |

### (I) M2 condition C-2 — genuinely satisfied

**Confirmed, by three independent means.**

1. *Confirmed in inspected code:* `main.py:176-177` —
   `if not key.strip(): raise ValueError("idempotencyKey must not be
   empty or whitespace.")`, before any request is built.
2. *Verified by local test:* direct probe (§2.4) rejects `''` and
   `'   '`.
3. *Verified by mutation:* removing that check (**M-6**) makes 2 tests
   fail, and the captured log shows what C-2 warned about — the empty
   key would otherwise travel to the transport layer
   (`Illegal header value b'   '`).

C-2's mock-side half (the mock still treats `""` as absent via `if
key:`) remains open for M4, as recorded.

## 4. Acceptance criteria (`BUILD_PLAN_peakflo.md` §10 M3)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Verified HTTP method / body | **Met** | *Official documentation*, re-fetched live by me: `PUT` creates, `POST /Payments/{id}` deletes; documented `{"Payments":[…]}` envelope matches the handler byte-for-byte. Mutation M-1 proves the test asserts it. |
| 2 | Header is sent | **Met** | `main.py:3201` via the existing `extra_headers` mechanism; `test_sends_put_with_idempotency_key_header` asserts it on the wire; mutation M-2 kills 4 tests. |
| 3 | Same operation uses same key | **Met** | No key-generation primitive in the file; key comes only from the caller's argument; `test_retry_after_outcome_unknown_does_not_double_pay` → `payment_count == 1`. |
| 4 | Ambiguous outcomes not reported as definite failure | **Met** | Structured return from inside the `except`, bypassing the `"Error: "` catch-all; classifier correct for every probed case; M-3 kills 6 tests. |
| 5 | Relevant existing tests pass | **Met** | 46 passed; pfMCP regression 20/37, byte-identical to the M0 baseline, same pre-existing cause. |
| 6 | No real Xero call | **Met** | Loopback-only URL literals; loopback assertion before `XERO_API_BASE` is mutated; fake token. |
| 7 | Key validation: type, non-empty, 128 max (§7) | **Met** | §2.4 probe; mutations M-6 and M-7 both killed. |
| 8 | `RECONCILIATION_REQUIRED` path, "to the extent supported by the approved scope" (task 12) | **Met, with a gap** | Fires correctly and refuses to invent an expiry (M-5 killed). But it is unreachable without the optional `operationStartedAt`, and the fallback guidance omits the window caveat → **F-1**. |
| 9 | Minimal diff, no unrelated refactoring (task 13, §12 rule 5) | **Met** | 8 hunks, one file, five attributable regions, no dependency change. |
| 10 | API-contract decision explained with compatibility impact | **Met** | `BUILD_LOG.md` M3 explains the decision, the Invoices comparison, and states the live-Xero behaviour of `POST /Payments` as **Unknown**. |

## 5. Adversarial checks (`QUALITY_GATE_AGENT.md` §4)

**Safety** — no real write · no live endpoint on any path incl. tests ·
no secrets · no production-incident claim · no exactly-once claim ·
mocks labelled. **All pass. No automatic rejection.**

**Retry model** — same key + identical payload across retries ✔ · no
fresh key per attempt ✔ (no generator exists) · `reference` never used
as key ✔ · same key + different payload rejected ✔ (400 surfaced as a
definite failure) · distinct keys not falsely blocked ✔ · ambiguous not
reported as definite ✔ (with **F-3** as a narrow exception in the
dangerous direction) · expiry leads to reconciliation, not a blind
new-key retry ✔ *when the window can be established*, **not when it
cannot** (**F-1**) · key validation covers type, non-empty, 128 ✔.

**Scope and architecture** — no later-milestone work · no unrelated
refactor or reformat · existing conventions preserved (`idempotencyKey`
camelCase matching three sibling tools; `extra_headers`; `TextContent` +
`json.dumps(indent=2)`) · no out-of-scope tool touched · no user work
discarded · no new dependency. **All pass.**

**Test quality** — status **and** ledger asserted together in every
behavioural test ✔ · deterministic ✔ (46 passed, two runs; the 7.0 s
stall vs httpx's 5 s default is still an unasserted margin — M2's
condition C-5, still open and still correctly attributed to M4) ·
negative and failure cases covered ✔ · **would fail on regression —
confirmed by 7 mutations, 6 killed, 1 survived (F-2)**.

**Record accuracy** — `BUILD_LOG.md` matches the repository and the test
output on every behavioural claim and every number I checked. No
fabricated command or metric found. Three record defects: **F-5**,
**F-6**, **F-7**. Stated limitations are present and honest, including
the two that matter most (not tested against live Xero;
`RECONCILIATION_REQUIRED` depends on the caller).

## 6. Defects

### F-1 — `OUTCOME_UNKNOWN` guidance tells the agent to retry with no window caveat (Medium)

`src/servers/xero/main.py:3243-3252`

```python
"retryGuidance": (
    "Retry the SAME logical payment with the SAME idempotencyKey and "
    "identical field values. Do not generate a new key and do not change "
    "the amount, date, invoice or account - a changed request with the "
    "same key is rejected, and a new key can create a second payment."
),
```

Because `operationStartedAt` is **optional**, this is the default path.
Xero's own guide states that after 6 minutes the same key "will instead
be processed as a new key, this should be avoided" — so an agent that
follows this guidance after a delay longer than the window creates a
second payment. The field `idempotencyWindowSeconds: 360` is present in
the payload, but the imperative sentence the agent actually reads
contains no condition. `BUILD_PLAN` §7 says "Once the six-minute
idempotency window may have elapsed: do not assume the key is still
protected" — here the tool cannot establish elapse, and its guidance
assumes protection anyway.

**Required correction (string-only, no logic change):** condition the
`OUTCOME_UNKNOWN` guidance on the window — e.g. append "Only retry if
fewer than 360 seconds have passed since your FIRST attempt with this
key. If more time has passed, or you cannot tell, read the payment state
back first (for example with list_payments for this invoice) instead of
retrying. Pass operationStartedAt on your first attempt so this tool can
make that determination for you." Also state in the
`operationStartedAt` schema description that omitting it disables the
expiry check.

### F-2 — The connect-error carve-out is asserted by no test (Medium)

`src/servers/xero/main.py:189-191`

Mutation **M-4** deleted the early return — making a never-delivered
`ConnectError` report `OUTCOME_UNKNOWN`, i.e. telling an agent "the
payment may exist" when it provably does not — and **all 19 tests still
passed**. No end-to-end test can produce a `ConnectError` (the mock is
always listening), and there is no unit test of
`is_ambiguous_transport_outcome`. The classifier is the heart of the
safety claim; the half that is exercised is strong, and this half is
unexercised.

**Required correction:** add direct unit tests for
`is_ambiguous_transport_outcome` asserting `False` for
`httpx.ConnectError` and `httpx.ConnectTimeout`, and `True` for
`httpx.ReadTimeout`, `httpx.WriteTimeout`, `httpx.RemoteProtocolError`
and a `status_code=502` exception — plus at least one end-to-end case
against a closed port, which produces a real `ConnectError` and must not
return `OUTCOME_UNKNOWN`. Pin the ordering with a comment noting that
`ConnectError ⊂ NetworkError` and `ConnectTimeout ⊂ TimeoutException`,
so the early return cannot be "tidied" below the broad tuple.

### F-3 — A 2xx with an unparseable JSON body is classified as a definite failure (Low–Medium)

`src/servers/xero/main.py:305-306` (pre-existing) +
`main.py:193-200` (new classifier)

```python
if "application/json" in content_type:
    return response.json()        # unguarded; the try/except is only below
```

If Xero returns a success status with a truncated or malformed
`application/json` body, `response.json()` raises `json.JSONDecodeError`
(a `ValueError`). That has no `.status_code` and matches no httpx
branch, so `is_ambiguous_transport_outcome` returns `False` (verified in
§2.4) and the payment — which the server almost certainly accepted — is
re-raised as a definite failure. This is the **dangerous** direction and
the exact failure shape the project exists to eliminate: a probable
success reported as a definite failure invites a blind retry once the
window has lapsed.

**Required correction:** classify a body-parse failure on a non-error
response as ambiguous. The lowest-risk form, local to the payment path,
is to catch `ValueError` separately in the handler and route it to
`OUTCOME_UNKNOWN`; alternatively guard `main.py:306` with the same
`try/except ValueError: return {"raw_response": response.text}` fallback
already used at `main.py:308-311` — but note that second option touches
all 72 call sites and so needs its own scope note.

### F-4 — `PoolTimeout` classified ambiguous although nothing was sent (Low, note only)

`src/servers/xero/main.py:192-195`. `PoolTimeout ⊂ TimeoutException`, so
exhausting the connection pool — which means the request never left the
client — is reported as ambiguous. This is the **safe** direction (the
agent reconciles instead of retrying blindly) and `httpx.AsyncClient()`
is constructed per call here so it is near-unreachable. Recording it so
it is a known deliberate choice rather than an oversight. No correction
required; a one-line comment would close it.

### F-5 — The M3 deliverable is uncommitted; the records imply otherwise (Medium, record accuracy)

`BUILD_LOG.md` M3 §Branch and `STATUS.md` row "M3 build". `git diff
main...HEAD` is empty and `git branch -vv` shows both branches at
`78cda6e`. +218/-12 of payment-creation code exists only in the working
tree: any `git checkout`, `git stash` or `git restore` destroys it, and
no reviewer or CI can fetch "the branch" and see the change.

**Required correction:** commit the change on
`feat/retry-safe-create-payment`, record the commit SHA in
`BUILD_LOG.md` M3, and restate the diffstat against that commit. (Per my
constraints I did not commit anything myself.)

### F-6 — `STATUS.md` safety posture states something now false (Medium, record accuracy)

`STATUS.md` → "Safety posture" → "`pfMCP/` checkout unmodified — `git
status` clean, HEAD `78cda6e…`". The checkout is modified. HEAD is
correct; "unmodified" and "clean" are not. This is the same class of
error the M2 reviewer caught in C-6 (a `STATUS.md` line that was already
false when written).

**Required correction:** amend the line in place to say the Xero server
file is modified on `feat/retry-safe-create-payment` and that `main`
remains at `78cda6e…`. Two other `STATUS.md` rows are also stale and
should be updated in the same pass: "PUT vs POST… Resolution deferred to
M3" (resolved in M3) and "M3 review… being written".

### F-7 — "`call_xero_api` (2 added lines)" understates the hunk (Low, record accuracy)

`BUILD_LOG.md` M3 §"Changes made" item 1. The hunk is −1 / +6. "Additive
only" is correct and I verified it; the line count is not. **Required
correction:** state −1 / +6 (two statements plus three explanatory
comment lines).

### F-8 — The success-path response shape deviates from §8 and is undeclared (Low)

`src/servers/xero/main.py:3269`. On success the handler returns the raw
Xero payload, not §8's `{"status": "SUCCESS", "operationId": …}`, and a
replayed cached response is indistinguishable from a fresh creation. §8
calls its examples illustrative and warns against breaking client
compatibility, so keeping the raw shape is a reasonable choice — but it
means an agent gets an explicit `status` field only on the failure
paths, and the decision appears nowhere in the record.

**Required correction:** record the decision in `BUILD_LOG.md` (one or
two sentences: raw shape retained for client compatibility; `status` is
emitted only on ambiguous paths), and consider in M4 whether a replay
indicator is needed.

## 7. Limitations of this review

1. **Live Xero behaviour is still Unknown.** I verified the
   *documentation* first-hand, not Xero's runtime. What `POST /Payments`
   (collection) actually does today, and whether real Xero enforces the
   128/6-minute rules exactly as written, remain untested. Every
   `Verified by local test` result in this report proves the behaviour
   of this client/mock pair only.
2. **Single platform.** Windows 11, Python 3.14.6, httpx 0.28.1. The
   `isinstance` ordering conclusion is specific to httpx 0.28.1's
   hierarchy; a future httpx reshuffle would need re-checking.
3. **Not an independent environment or party.** Same session, machine,
   interpreter, venv and checkout as the builder; I was handed the venv
   path and the suggested commands. Not a substitute for human review.
4. **I did not run** `repro/retry_dup_repro.py` (to protect
   `m1_baseline_latest.json`), pfMCP's `tests.py` live-client path (it
   would require real Xero credentials), or any lint/type checker (M8's
   job).
5. **No concurrency probe this milestone.** M2's C-4 (non-atomic
   `lookup → commit → store`) is untouched by M3 and remains a hard
   requirement before any concurrent M5/M6 run.
6. **Mutation coverage is 7 mutations, not exhaustive.** A surviving
   mutation proves a gap; the 6 kills prove those 6 behaviours are
   pinned. Other untested behaviours may remain — F-2 is the one I
   found.
7. **I did not verify the three sibling `idempotencyKey` tools still
   behave correctly** beyond the regression run, which cannot exercise
   them because of the pre-existing `_invoke()` bug. Their assertions
   remain unverified on this checkout, as M0 §10 limitation 2 already
   records.

## 8. Verdict

All ten M3 acceptance criteria are met and independently verified,
including the one the project had been carrying as its largest
unverified dependency: I re-fetched Xero's live Payments, Invoices and
Idempotency pages myself and confirmed the contract decision, the
request envelope and both documented constants. No safety absolute is
violated. The retry semantics are correct where they are exercised —
one caller-owned key, no generator anywhere in the file, `reference`
provably separate, ambiguous outcomes structurally bypassing the
`"Error: "` catch-all — and six of seven mutations were killed,
including both behaviours the brief named. The diff is genuinely minimal
and the `call_xero_api` change genuinely additive.

Three things keep this from a clean `APPROVED`: the default
ambiguous-outcome guidance tells an agent to retry with no window caveat
(**F-1**), the connect-error half of the classifier is asserted by no
test at all (**F-2**), and a success-status response with an unparseable
body is classified in the dangerous direction (**F-3**). None
invalidates a criterion or an evidence claim; each is a precise,
cheap correction. **F-5** and **F-6** must also be fixed because a
payment-safety deliverable that exists only in an uncommitted working
tree, alongside a `STATUS.md` that calls the checkout clean, is not a
reviewable artifact.

**Conditions, each with its gate per §5:**

| # | Condition | Safe to proceed to M4? | Must resolve by |
|---|---|---|---|
| **F-1** | Window caveat in `OUTCOME_UNKNOWN` guidance; note the effect of omitting `operationStartedAt` | Yes — the mock cannot hold a key for 6 real minutes, so no current test can hit it | **M4** — must not survive into M5/M6, where an agent reads this guidance and acts on it |
| **F-2** | Unit + closed-port tests for the connect-error classification; pin the `isinstance` ordering | Yes | **M4** (the test milestone) |
| **F-3** | Classify a body-parse failure on a non-error response as ambiguous | Yes — unreachable against the mock | **M4** |
| **F-5** | Commit the branch; record the SHA in `BUILD_LOG.md` M3 | **No — do this first.** Uncommitted payment code is one `git restore` from gone | **before M4 starts** |
| **F-6** | Amend `STATUS.md`'s false "checkout unmodified / clean" line in place, plus the two stale rows | **No — do this first**, with F-5 | **before M4 starts** |
| **F-7** | Correct "2 added lines" to −1 / +6 | Yes | M4 |
| **F-8** | Record the success-shape decision; consider a replay indicator | Yes | M4 (decision), M7 (documentation) |
| **F-4** | `PoolTimeout` — note the deliberate safe-direction choice | Yes | optional; M8 at the latest |

Carried forward unchanged from M2: **C-2** mock side (M4), **C-4**
concurrency (hard requirement before any concurrent M5/M6 run), **C-5**
unasserted test margins (M4) — and C-5 now also applies to
`test_create_payment_tool.py`'s own 7.0 s stall against httpx's implicit
5 s default.

**VERDICT: APPROVED WITH CONDITIONS**

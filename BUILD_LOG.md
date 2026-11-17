# Build Log — Retry-Safe Xero Payment Execution for MCP Agents

This file records actual milestone activity: what was attempted, files
changed, commands run, test results, acceptance status, limitations, and
the next proposed milestone. Entries are written only after the work has
actually happened. See `BUILD_PLAN_peakflo.md` for the governing plan and
`prompts_for_peakflo.md` for the prompt history.

---

## M0 — Repository and environment inspection

**Date:** 2026-11-16
**Status:** Complete. No source code changed. Awaiting human review before M1.

### 1. What was attempted

Inspected the public `peakflo/pfMCP` repository's current Xero
`create_payment` tool, its call chain, its existing tests, and re-checked
the current official Xero Payments and Idempotency documentation, to
confirm or correct the research snapshot in `BUILD_PLAN_peakflo.md`
before any implementation planning.

### 2. Repository state

- **Cloned to:** `R:\Internship_Outreach_prototype\Peakflo\pfMCP`
  (fresh clone, not a copy of any existing local checkout).
- **Remote:** `https://github.com/peakflo/pfMCP.git`
- **Branch:** `main`
- **HEAD commit:** `78cda6ec779cbb704292500f8f8bd5dfafe9b2f1`
- **HEAD commit date:** 2026-11-13 13:35:00 +0700
- **HEAD commit subject:** `chore(stage): keep one warm pf-mcp instance with 1 vCPU (#226)`
- **Working tree:** clean immediately after clone; still clean after this
  milestone (confirmed — *verified by local test*).
- **Fork metadata:** treated as context only, per plan §4.2. Not
  re-verified via GitHub API this milestone; no claim is made about
  production deployment based on it.

### 3. Files changed

**None.** No file under `pfMCP/` was edited. The only artifacts created
this milestone are local, git-ignored, and outside version control:
- `pfMCP/.venv/` — a Python virtual environment (ignored by the repo's
  own `.gitignore`), used only to run tests.
- This `BUILD_LOG.md` and nothing else inside the repo.

### 4. Current `create_payment` implementation — confirmed in inspected code

- **Tool schema:** [`src/servers/xero/main.py:1082-1111`](pfMCP/src/servers/xero/main.py) —
  `invoiceId`, `accountId`, `amount`, `date` required; `reference`
  optional. **No `idempotencyKey` field exists on this tool's schema.**
- **Handler:** [`src/servers/xero/main.py:3036-3064`](pfMCP/src/servers/xero/main.py) —
  builds `{"Invoice": {"InvoiceID": ...}, "Account": {"AccountID": ...}, "Amount": ..., "Date": ...}`,
  optionally adds `Reference`, then calls:
  ```python
  await call_xero_api(
      f"{ACCOUNTING_API}/Payments", access_token, tenant_id,
      method="POST", data={"Payments": [payment]},
  )
  ```
  **No `extra_headers` argument is passed at all** — confirming the
  research snapshot. This is the only create-payment code path; there is
  no separate idempotency handling anywhere in it.
- **Helper:** [`call_xero_api()` at `src/servers/xero/main.py:152-224`](pfMCP/src/servers/xero/main.py) —
  confirmed unchanged from the research snapshot's description. Accepts
  `extra_headers: Dict[str, str] = None` (line 160) and merges it into
  the request headers (lines 186-187) when present. Generic error
  handling via `format_xero_error()`; no `OUTCOME_UNKNOWN` or similar
  structured ambiguous-outcome result exists anywhere in this file.

### 5. New finding not in the research snapshot — an existing idempotency-key precedent

The research snapshot said no dedicated ambiguous-outcome handling was
found and did not mention any existing idempotency convention on Xero
tools other than the unrelated Peakflo cash-advance schema. Direct
inspection of the current checkout shows this needs updating:

- Three *other* Xero tools already accept an **optional** `idempotencyKey`
  string parameter and forward it to Xero as the `Idempotency-Key` header
  via the existing `extra_headers` mechanism:
  - `add_attachment` / `upload_attachment` — schema at
    [`main.py:2341-2344`](pfMCP/src/servers/xero/main.py) /
    [`2376-2379`](pfMCP/src/servers/xero/main.py), handler at
    [`main.py:4175-4186`](pfMCP/src/servers/xero/main.py).
  - `email_invoice` — schema at
    [`main.py:2408-2411`](pfMCP/src/servers/xero/main.py), handler at
    [`main.py:4235-4245`](pfMCP/src/servers/xero/main.py).
  - In all three, the parameter name is **`idempotencyKey`** (camelCase,
    matching the plan's preferred naming) and it is **optional** — the
    header is only added `if arguments.get("idempotencyKey")`.
- **Confirmed in inspected code:** unit tests already exercise this exact
  pattern — `tests/servers/xero/test_accounting_expansion.py:224-251`
  (`idem-123` for `add_attachment`) and `:297-314` (`idem-email` for
  `email_invoice`) — both asserting
  `api_mock.call_args.kwargs["extra_headers"]["Idempotency-Key"]`.

**Implication for M3 (not acted on this milestone):** there is a direct,
tested, in-repo convention to follow for `create_payment` — same
parameter name, same optional-flag-into-`extra_headers` mechanism. The
plan's required-vs-optional question (§7, §10 M3 task 5) should be
weighed against this existing precedent, which makes the key optional
elsewhere. This is a decision for the user before M3, not decided here.

### 6. Current official Xero API contract — re-verified today, 2026-11-16

Fetched directly from `developer.xero.com` (official documentation) via
browser, not from cached search results, because the first WebFetch
attempts returned only partial/unauthenticated renders of this
JavaScript-rendered site.

**Payments API** — `https://developer.xero.com/documentation/api/accounting/payments`:
> "Methods Supported: GET, PUT, POST" — and specifically:
> - **PUT `/Payments`** — "Use this method to **apply payments** to
>   approved AR and AP invoices, refund AR or AP credit notes, refund
>   spend or receive overpayments, or refund spend or receive
>   prepayments." This is the **payment-creation** method.
> - **POST `/Payments`** — "Use this method to **delete (reverse)**
>   payments to invoices, credit notes, prepayments & overpayments... In
>   order to delete a payment, you must POST to the resource ID for the
>   payment, e.g. `POST /Payments/{PaymentID}`" with body
>   `{"Status": "DELETED"}`. **Payments cannot be modified, only created
>   and deleted.**

**Critical verification result:** the research snapshot's flagged
mismatch is **confirmed, not hypothetical**. The inspected `create_payment`
handler calls `POST /api.xro/2.0/Payments` with a payment-creation body —
that is the documented *delete* method/semantics, not the documented
*create* method (`PUT`). The repository's own `PLAN_XERO_INTEGRATION.md`
(line 140) also documents this tool as `POST`, so the mismatch is
pre-existing and self-consistent within the repo, but inconsistent with
Xero's current official contract. **This must be resolved in M3 only
after explicit review**, per plan §10 M3 task 3 — not changed in this
milestone.

**Idempotency guide** — found at
`https://developer.xero.com/documentation/guides/idempotent-requests/idempotency`
(the URL in the plan, `.../idempotent-requests/`, is not the live path —
see §8 below). Re-verified today, all research-snapshot claims hold:
- Header name: `Idempotency-Key` (case-insensitive).
- Applies only to **POST, PUT, PATCH** (mutating methods); ignored for
  others.
- Same key + same request → cached original response returned, not
  reprocessed.
- Same key + a **different** request (different URL, body, or HTTP
  method) → HTTP 400, body `Idempotency Key: KEY_VALUE is used with a
  different request.`
- Max key length **128 characters**; longer → HTTP 400, body
  `Idempotency Key: KEY_VALUE with length KEY_LENGTH is too long.`
- Keys are stored **6 minutes** from the first call, then expire.
  Re-using an expired key is **not** rejected — it is silently treated as
  a brand-new key, which the guide itself says "should be avoided." This
  directly supports the plan's `RECONCILIATION_REQUIRED` design (§7, §10
  M3 task 12): the API will not protect the caller past 6 minutes.
  (*official documentation*)
  Example value actually gives a slightly different phrasing than the
  (second-source) `KEY_LENGTH`/`KEY_VALUE` interpolation, but this is the
  literal text from the official guide and is recorded verbatim.
- An internal error is cached too: "If an idempotent request errors out
  internally, the error will be cached and returned when the request is
  re-run even if the internal error is resolved" — matches the plan's
  §4.3 bullet exactly. (*official documentation*)
- No format/UUID validation is applied by Xero to key values — "any
  string will be accepted" — so caller-side type/length/non-empty
  validation (plan §7 "Operation-key rules") is entirely the caller's
  responsibility. (*official documentation*)
- Key re-use is scoped **per app** (the Xero OAuth application), not per
  organisation or tenant. (*official documentation* — new detail beyond
  the research snapshot, worth keeping in mind for M2's mock design.)

### 7. Existing tests — inspected and run

**Test files found:** `tests/servers/xero/test_accounting_expansion.py`,
`test_attachment_download.py`, `test_get_invoice_pdf.py`,
`test_update_invoice_status.py`, `test_imda_tools.py`, `tests.py`.

**No dedicated `create_payment` test exists anywhere in the repository.**
`tests.py`'s `TOOL_TESTS` list (used by the `client`-fixture / live
MCP-protocol test path) covers `list_payments` and `list_batch_payments`
but never exercises `create_payment`.

**Two different test styles exist, confirmed by reading `conftest.py`
and each test file:**
1. `tests.py` uses a `client` fixture (`tests/servers/conftest.py:41-67`)
   that spins up a real `LocalMCPTestClient`/`RemoteMCPTestClient` and
   calls `load_dotenv()` — this path expects real stored Xero
   credentials/connection and was **not run**, to honor "no live Xero
   calls" (plan §6, §12 rule 9). Not run; not claimed to pass or fail.
2. The other five files use `unittest.mock.patch.object` to mock
   `call_xero_api` and `get_xero_credentials` directly on the
   `src.servers.xero.main` module and dispatch requests through
   `create_server(...).dispatch(...)` — no network, no real credentials,
   no `.env` required. These were run.

**Commands actually run** (from `pfMCP/`, after `git clone`):
```bash
python -m venv .venv
.venv/Scripts/activate  # Windows venv
pip install -q anthropic==0.49.0 httpx==0.28.1 jsonschema==4.25.1 \
    mcp==2.2.0 python-dotenv==1.1.0 "pytest>=7.4.0" \
    "pytest-asyncio>=0.21.1" pytest-timeout pytest-mock==3.11.1
python -m pytest tests/servers/xero/test_accounting_expansion.py \
    tests/servers/xero/test_attachment_download.py \
    tests/servers/xero/test_get_invoice_pdf.py \
    tests/servers/xero/test_update_invoice_status.py \
    tests/servers/xero/test_imda_tools.py -v
```

Note: the repo's full `requirements.txt` could not be installed as-is —
`pip install -r requirements.txt -r requirements-dev.txt` failed with
`No matching distribution found for atproto==0.0.61` because the local
Python is 3.14.6, newer than the versions `atproto` publishes wheels for,
and newer than the Python the repo's own `Dockerfile` targets
(`python:3.10.12`). This is an **environment version mismatch**, not a
code defect; a minimal, individually-pinned subset of packages
sufficient to import and exercise `src/servers/xero/main.py` and its
tests was installed instead, as listed above, with exact versions taken
from `requirements.txt`/`requirements-dev.txt`.

**Actual test results (*verified by local test*):**
```
37 failed, 20 passed in 8.77s
```
All 37 failures share the same root cause, confirmed by reading the
failure output and the relevant source:
- `create_server(user_id=...)` (`main.py:374-390`) sets
  `server.credential_resolver = credential_resolver or get_xero_credentials`
  **at server-construction time**.
- Each test's shared `_invoke()` helper (e.g.
  `test_accounting_expansion.py:11-27`) calls `xero_main.create_server(...)`
  **before** entering the `with patch.object(xero_main, "get_xero_credentials", creds_mock)`
  block, so the real credential resolver is already bound on the server
  object by the time the patch takes effect. Every test that actually
  dispatches a tool call therefore hits the real credential lookup, which
  raises `[credentials_missing] Xero credentials are missing for this
  connection. Connect Xero again.` (from `src/auth/credential_errors.py`),
  and the mocked `call_xero_api` is never called — producing either an
  assertion failure or `IndexError: list index out of range` on
  `api_mock.call_args_list[0]`.
- The 20 tests that **passed** are exactly the ones that never reach
  `call_xero_api` dispatch at all: schema-shape assertions
  (`test_schema_*`, `test_list_invoices_schema_exposes_bounded_page_size`)
  and client-side validation-error paths that raise before any API call
  (`test_list_attachments_unsupported_entity_type`,
  `test_get_attachment_unsupported_entity_type`,
  `test_get_attachment_download_failure`, `test_missing_invoice_id`,
  `test_create_bank_transfer_rejects_missing_fields`,
  `test_create_bank_transfer_rejects_negative_amount`,
  `test_create_batch_payment_rejects_missing_fields`,
  `test_create_batch_payment_rejects_incomplete_payment_items`).

**This is a pre-existing test-infrastructure ordering bug in the cloned
repository's own `_invoke()` test helper, reproduced on a fresh clone at
the recorded HEAD commit, in this environment.** It is **not** caused by
any change made in this milestone (none was made) and is **out of scope**
to fix under this plan (plan §6 "unrelated refactoring... unless
separately approved"). It is recorded here as a known limitation because
it means: (a) the existing `idempotencyKey` precedent described in §5
above is currently **not actually exercised** by a passing test on this
checkout/environment, even though the assertions themselves are correct
and well-formed; and (b) any new `create_payment` tests written in M4
using the same `_invoke()` pattern will hit the same failure unless this
ordering issue is also addressed — which would need explicit approval
first, since it touches shared test infrastructure, not just the Xero
payment path.

### 8. Other discrepancies noted between the plan and the current checkout

- The idempotency guide URL in `BUILD_PLAN_peakflo.md` §4.3 —
  `https://developer.xero.com/documentation/guides/idempotent-requests/`
  — returns "Not Authorized" in a real browser today; the working URL is
  `https://developer.xero.com/documentation/guides/idempotent-requests/idempotency`.
  Content otherwise matches what the plan cited. Noted for anyone citing
  this guide later (e.g. in the final README).
- `PLAN_XERO_INTEGRATION.md` (a file already in the `pfMCP` repo itself,
  not authored by this project) independently documents `create_payment`
  as `POST /api.xro/2.0/Payments` (line 140) and `list_payments` as
  `GET /api.xro/2.0/Payments` (line 114) — consistent with the inspected
  code, and useful corroborating context, but it is the repo's own
  internal planning document, not official Xero documentation, and
  carries no more weight than the code itself.

### 9. Acceptance criteria (plan §10 M0)

| Criterion | Status |
|---|---|
| Current implementation path and API contract understood | **Met** |
| Relevant tests run or failure reason recorded | **Met** — run; failures explained above (§7), root cause identified, not fabricated |
| No source code changed | **Met** — `git status --short` clean before and after |

### 10. Known limitations / unresolved questions

1. The `POST` vs. documented `PUT` method mismatch is confirmed against
   current official docs but **not yet resolved** — that is explicitly
   M3's job, gated on approval.
2. The pre-existing `_invoke()` credential-patch-ordering bug (§7) means
   none of the currently-passing dispatch-level mock tests for
   `add_attachment`/`email_invoice`/etc. actually ran their asserted
   `call_xero_api` path in this environment; their assertions are
   unverified on this checkout even though they look correct by
   inspection. Flagging for awareness going into M2/M4; not fixed here.
3. `tests.py`'s live-client test path was not run at all (by design — no
   real Xero connection exists or should be created). No claim is made
   about its current pass/fail status.
4. Full `requirements.txt` install is not possible unmodified on Python
   3.14; a minimal pinned subset was used instead for this milestone's
   test run. A later milestone that needs more of the dependency tree
   (e.g. `src/auth/factory.py` internals) may need either a Python 3.10
   environment matching the Dockerfile, or further minimal-subset
   installs, as approved.
5. Fork-metadata/production-deployment claims from plan §4.2 were not
   independently re-verified this milestone (no GitHub API check beyond
   the git remote itself); treated as unchanged context only, per the
   plan's own instruction not to assume every path is used in production.

### 11. Human review decision

**Pending.**

### 12. Next milestone proposed

**M1 — Baseline duplicate-effect reproduction** (plan §10 M1): build a
minimal local mock endpoint, implement `commit_then_slow`, and a baseline
client that retries as a new operation without a stable key, to
demonstrate whether the scenario can create two ledger entries for one
intended logical operation. Not started. Waiting for explicit approval
before beginning, per plan §12 rule 2.

---

## Governance change — autonomous build + independent review mode adopted

**Date:** 2026-11-16 (same session, after M0 was reported)

### What changed

Raj supplied `<downloads>\AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md`
and instructed: inspect the repository, then execute the approved build
plan autonomously one milestone at a time, with an **independent
reviewer agent** verifying each milestone and gating progression; fix and
re-review on rejection; maintain `BUILD_LOG.md`, `STATUS.md`,
`prompts.md`, and `reviews/`; Raj reviews the completed project and final
handover rather than approving each routine step.

M0's "pending" human approval is therefore superseded by this
instruction: the reviewer gate now controls progression.

### Document conflicts found — recorded, with the resolution used

**Conflict 1 — operating procedure.** `PROJECT_GUIDE.md`
(`~/Downloads`, 2026-11-16 19:10) §6 rules 5 and 15 say "Do not execute
all milestones autonomously" and "Stop after the approved milestone and
wait"; Phase 8/G says stop for approval after every milestone. This
directly contradicts `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md`, which
requires autonomous progression under reviewer gating.

*Resolution:* Raj's explicit instruction in this session supersedes the
earlier generic guide. `PROJECT_GUIDE.md` is a **reusable template**
("Reusable instructions for ... an existing project folder") describing a
mentor-led learning workflow, not a project-specific approval contract;
`AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` is the newer, project-specific
operating procedure Raj handed over directly. Proceeding autonomously
under reviewer gating. *Recorded, not silently chosen* — Raj can reverse
this at any time and the build will stop at the next gate.

**Conflict 2 — which build plan is authoritative (material).** Two
competing plans exist, both dated 2026-11-16:

| | `BUILD_PLAN_peakflo.md` (project root) | `peakflo-v2-gap-and-build-plan-2026-11-16.md` (`~/Downloads`) |
|---|---|---|
| Status line | "**Approved** for implementation planning" | Gap-finder research output; no approval marker |
| Location | project root (this working directory) | Downloads, alongside other research artifacts |
| Scope | **Xero `create_payment` only**; `send_message` and `create_batch_payment` explicitly **non-goals** (§6) | Xero `create_payment` **and** `create_batch_payment` **and** Peakflo `send_message` |
| Idempotency key | Caller **must supply** it; "Do **not** derive the key only from invoice ID, amount, and date" (§7) | Derive `sha256(tenant|tool|invoiceId|accountId|amount|date|reference)` when not supplied |
| HTTP method | Must **verify** PUT vs POST against official docs before changing (§4.3, §10 M3) | Not addressed |
| Reconciliation | `RECONCILIATION_REQUIRED` state required for expired window (§7, §8) | Not present |
| Milestone numbering | M0 inspect → M1 repro → M2 mock → M3 impl → M4 tests → M5 demo → M6 eval → M7 docs → M8 review | M0 context → M1 mock → M2 patch → M3 tests → M4 repro → M5 eval → M6 docs → M7 video → M8 ship |

*Resolution:* **`BUILD_PLAN_peakflo.md` is authoritative.** Reasons: (a)
it is the document in the project root that Raj's own instruction points
at ("the approved `BUILD_PLAN.md`"); (b) it is the only one carrying an
approval status line; (c) `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` §6 says
"If the current approved build plan has more restrictive rules, follow
the more restrictive rules" — and `BUILD_PLAN_peakflo.md` is strictly the
more restrictive of the two on every axis above (narrower tool scope,
stricter key rules, mandatory contract verification). The v2 gap document
is retained as **research context and evidence**, not as the milestone
plan.

*Consequences Raj should know about:* under the authoritative plan,
`send_message` and `create_batch_payment` are **out of scope**; the
idempotency key is **caller-supplied**, not derived; and the PUT-vs-POST
contract question must be resolved explicitly in M3. If Raj wants the v2
plan's wider scope or derived-key behaviour instead, that is a scope
change and the build must be re-pointed — it will not be adopted
silently.

**Note on v2 evidence E2.** The v2 document cites "today's script
`research/repro/retry_dup_repro.py`" as already demonstrating 2 payments
and 2 messages. No such script exists anywhere in this project folder
(searched). M1 is therefore being built from scratch, and no result from
that claimed earlier run is reused or restated as evidence.

### Missing document created

`QUALITY_GATE_AGENT.md` did not exist and no equivalent review-policy
document was found. It was **derived** from `BUILD_PLAN_peakflo.md`
(§6, §7, §10, §12, §13) and `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md`
(§3 Phase 3, §6, §7), adds no new scope or acceptance criteria, and says
so in its own provenance header.

### Record-file mapping (reusing existing files, not duplicating)

| Orchestrator name | Actual file used |
|---|---|
| `BUILD_PLAN.md` | `BUILD_PLAN_peakflo.md` |
| `prompts.md` | `prompts_for_peakflo.md` |
| `BUILD_LOG.md` | `BUILD_LOG.md` (this file) |
| `STATUS.md` | `STATUS.md` (new) |
| `reviews/` | `reviews/` (new) |
| `QUALITY_GATE_AGENT.md` | `QUALITY_GATE_AGENT.md` (new, derived) |

---

## M1 — Baseline duplicate-effect reproduction (builder record)

**Started / built:** 2026-11-16 (UTC run stamps 14:02–14:03Z)
**Role:** Implementation agent (orchestrator session)
**Status:** Built; submitted for independent review.

### Objective (BUILD_PLAN_peakflo.md §10 M1)
Reproduce the ambiguous-outcome retry problem in an isolated local
client/mock scenario, showing whether one intended payment can become two
ledger entries when a caller retries without a stable key.

### Files created (no existing file modified; pfMCP untouched)
- `repro/baseline_mock.py` — minimal stdlib `ThreadingHTTPServer` on
  127.0.0.1; modes `ok` and `commit_then_slow` (commits to ledger, then
  stalls); `GET /__ledger`, `POST /__reset`. Deliberately **no**
  idempotency cache (that is M2). Labelled LOCAL SIMULATION in its
  docstring.
- `repro/retry_dup_repro.py` — runs `control_ok` and
  `baseline_timeout_retry`; default client drives pfMCP's **real,
  unmodified** `call_xero_api()` with only the module global
  `XERO_API_BASE` redirected to the mock; `--client isolated` uses plain
  httpx of the same shape. Writes JSON to `repro/results/`.
- `repro/results/m1_baseline_20261116T140244Z.json` (pfmcp client),
  `m1_baseline_20261116T140311Z.json` (isolated client),
  `m1_baseline_20261116T140339Z.json` (pfmcp client, re-run),
  `m1_baseline_latest.json` (= the 140339Z run).

### Commands run
```bash
cd repro
../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py             # pfmcp client
../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py --client isolated
../pfMCP/.venv/Scripts/python.exe retry_dup_repro.py             # re-run so latest = pfmcp
git -C ../pfMCP status --short                                   # empty: pfMCP unmodified
```

### Actual results (*verified by local test*, local simulation)
| scenario | client | attempts | ledger committed | duplicates |
|---|---|---|---|---|
| control_ok | pfmcp | 1 | 1 | 0 |
| baseline_timeout_retry | pfmcp | 2 | 2 | 1 |
| control_ok | isolated | 1 | 1 | 0 |
| baseline_timeout_retry | isolated | 2 | 2 | 1 |

Each timed-out attempt failed after roughly 5.0–5.2 s (observed
5.02–5.15 s across builder and reviewer runs; this is httpx's default 5 s
timeout plus scheduling overhead, **not** an invariant) with
`httpx.ReadTimeout`, whose `str()` is the empty string. Through the
inspected dispatcher catch-all (`pfMCP main.py:4258-4260`,
`f"Error: {str(e)}"`) the agent-facing text would therefore be exactly
`"Error: "` — *inference from code + observed exception string*; the full
MCP dispatcher was not executed in M1. Idempotency keys seen by the mock:
`[None, None]`.

### What this proves / does not prove
- **Shows:** in this local client/mock pair, a retry issued as a new
  operation without a stable key, after a timeout that hid a committed
  write, produced a second ledger entry for one intended payment.
- **Does not show:** that Xero would behave identically, that Peakflo
  production behaves this way, or that any real duplicate payment has
  occurred. No request left 127.0.0.1.

### Notes / limitations
- The payload builder in the repro is a verbatim copy of
  `main.py:3047-3055`, not an import, because that code lives inside the
  tool dispatcher. A drift between the two would not be caught
  automatically.
- The repro used `method="POST"`, matching current inspected code. The
  PUT-vs-POST contract question remains M3 work; the M1 mock accepts both
  so the routing choice does not decide the outcome.
- Results depend on httpx's default 5 s timeout and the mock's 7 s
  stall; both are recorded in the JSON `environment` block.

### M1 — Independent review verdict

**Reviewer:** separate `general-purpose` agent, fresh context, did not
write `repro/`. **Report:** `reviews/M1-review.md`.
**Verdict: `APPROVED WITH CONDITIONS`.**

The reviewer explicitly confirmed every condition is non-blocking and
safe to start M2, which is what the gate rule in
`AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` §3 Phase 4 requires before
advancing. M2 is therefore unlocked.

**Independence — stated honestly, not overclaimed.** Separate agent,
fresh context, independent code reading and independent execution. But
it ran as a subagent in the same overall session, on the same machine,
interpreter and checkout, and was handed the venv path and suggested
commands. It is **not** an independent environment or an independent
party, and is not equivalent to human review. Single platform only
(Windows 11, Python 3.14.6, httpx 0.28.1).

**What the reviewer independently verified (not taken from the builder):**
- `pfMCP` unmodified — `git status --short` and `diff --stat` both empty,
  HEAD still `78cda6ec779cbb704292500f8f8bd5dfafe9b2f1`.
- Re-ran both client modes and reproduced the result: 2 attempts, 2
  ledger entries, 1 duplicate; `ReadTimeout` with `str(exc) == ''`.
- Wrote a spy wrapper proving the default client really calls pfMCP's
  own `call_xero_api()` with `base_at_call_time` pointing at
  `127.0.0.1`, `method=POST`, and the exact payload — i.e. claim (c)
  verified by execution, not by reading.
- Confirmed the commit-before-stall ordering in code at
  `baseline_mock.py:174-177`.
- Confirmed payload fidelity against `main.py:3047-3055/3062` on the
  bytes actually reaching the mock.
- URL grep: the only URL literal in `repro/*.py` is
  `http://127.0.0.1:{port}` (`baseline_mock.py:209`). No secrets in
  `repro/results/`.
- Confirmed no M2/M3 work leaked into M1.

**Conditions to track.** The reviewer's prose says "all six conditions"
but its list runs D-1 to D-7. Treating **all seven** as conditions
(recording the discrepancy rather than resolving it silently):

| # | Condition | Severity | Due |
|---|---|---|---|
| D-1 | Timeout-vs-delay margin is never asserted. The 5.0 s is httpx's *implicit* default (no client passes `timeout=`, including `pfMCP main.py:189`) and 7.0 s is an unenforced script default. A changed default or careless `--delay` silently flips the headline result to `false` — the reviewer demonstrated this with `--delay 1`. | medium | **M2**, must not survive into M5 |
| D-2 | Repro exits 0 even when nothing is reproduced. | low | M2 |
| D-3 | `m1_baseline_latest.json` is rewritten by every run and `STATUS.md` cited it as authoritative. | medium | **record fixed now**; code fix M2 |
| D-4 | pfmcp path's safety rests on one global mutation of `XERO_API_BASE` with no loopback assertion. Harmless while sequential; must be fixed before any concurrent M5/M6 run. | medium | M2, hard requirement before M5/M6 |
| D-5 | Every ambiguous attempt prints a raw `ConnectionAbortedError [WinError 10053]` traceback to stderr; the keep-alive read after client abort isn't guarded, only the response write is. Will pollute captured output in M5/M7. Not mentioned in the builder's BUILD_LOG entry. | medium | M2 |
| D-6 | BUILD_LOG's "~5.02–5.05 s" is exact for the builder's runs but reads as an invariant; reviewer observed 5.03–5.15 s. | very low | corrected below |
| D-7 | `baseline_mock.py:162` computes `attempt_index` outside the lock. | latent | M2 |

**D-6 correction, applied now:** the observed timeout spread across all
runs by both builder and reviewer is **~5.02–5.15 s**, not "~5.02–5.05
s". It is not an invariant; it is whatever httpx's default 5 s timeout
plus scheduling overhead produces on this machine.

**D-3 correction, applied now (record accuracy).** The reviewer's
`--delay 1` probe overwrote `m1_baseline_latest.json` with a
`duplicate_effect_reproduced: false` run, then restored it by re-running
the default once. Current state, verified:

- `m1_baseline_latest.json` is now the **reviewer's** run
  `m1_baseline_20261116T140859Z.json` (client `pfmcp`, delay 7.0,
  `duplicate_effect_reproduced: true`) — **not** the builder's
  `...140339Z` run that the M1 builder entry above names.
- The builder's three original files
  (`...140244Z`, `...140311Z`, `...140339Z`) are untouched.
- `...140631Z`, `...140708Z`, `...140738Z`, `...140859Z` are the
  reviewer's artifacts, retained as review evidence.

Both runs used the same client and settings and reached the same result,
so no reported number changes. The provenance is corrected here so no
reader mistakes `latest` for the builder's cited run.

**Gate decision: PROCEED TO M2**, carrying D-1, D-2, D-4, D-5 and D-7
into M2's scope as explicit work items, with D-1 and D-4 flagged to the
M2 reviewer as hard checks.

---

## M2 — Fault-injection mock Xero API (builder record)

**Date:** 2026-11-16
**Role:** Implementation agent (orchestrator session)
**Status:** Built; submitted for independent review.
**Unlocked by:** M1 `APPROVED WITH CONDITIONS` + reviewer's explicit
confirmation that no condition blocks M2.

### Objective (BUILD_PLAN_peakflo.md §9, §10 M2)
Model the relevant Xero idempotency contract and failure modes locally,
deterministically, with tests for every behaviour.

### Files created
- `mocks/fault_server.py` — the fault-injection mock. Ledger,
  idempotency cache keyed by `Idempotency-Key`, request-identity
  fingerprinting, configurable TTL, injectable clock, reconciliation
  read endpoint, and control plane (`/__ledger`, `/__reset`,
  `/__advance_clock`, `/__mode`).
- `mocks/MOCK_CONTRACT.md` — the concise mock contract (M2 deliverable).
- `tests/test_fault_server.py` — 25 tests.
- `tests/conftest.py` — `mock_server` factory fixture; each test gets a
  fresh server and state.

### Files modified (M1 condition remediation, see below)
- `repro/baseline_mock.py`, `repro/retry_dup_repro.py`.

### Design decisions
- **Injectable clock rather than sleeping.** `POST /__advance_clock`
  moves the mock's clock forward, so the six-minute expiry window is
  tested in milliseconds and deterministically. The default TTL is the
  documented **360 s**; tests override it or advance the clock. This
  satisfies "expiry is testable quickly" without a flaky timing race.
- **Request identity** is `sha256(METHOD | path | canonical-JSON-body)`,
  matching Xero's documented definition that a request differs if "any
  part of the endpoint URL, request body or HTTP method has changed".
  Canonical JSON means body key order does not create false conflicts.
- **Both PUT and POST accepted** for creation, so the mock does not
  pre-decide the unresolved PUT-vs-POST question (M3 work). Method still
  participates in request identity.
- **Errors are cached**, per Xero's documented behaviour, including the
  consequence that a cached internal error is replayed even once the
  mock would succeed.
- **Fault injection is kept out of application code** — it lives in
  `mocks/`, and nothing in `pfMCP/` was touched.

### Commands run
```bash
pfMCP/.venv/Scripts/python.exe -m pytest tests/ -p no:cacheprovider -q
git -C pfMCP status --short      # empty: pfMCP still unmodified
```

### Actual results (*verified by local test*)
```
25 passed in 14.94s
```
(run twice, same result; second run after the M1 condition fixes)

Coverage — every behavioural test asserts the ledger side effect as well
as the HTTP result (four of the tests are deliberately non-ledger:
constant pinning, fingerprint stability, TTL configurability and the
loopback-bind check): `ok` commits once · `fail_before_commit` writes nothing ·
`commit_then_502` returns 502 but **has** committed · `commit_then_slow`
times the client out but **has** committed · same key + same payload
replays with one ledger row and the same `PaymentID` · the M1 scenario
replayed with a stable key now yields exactly one payment · same key +
different payload → 400, nothing committed · different keys → two
payments · identical payload with different keys → two payments (no
false block) · no key → two payments (baseline) · over-long key → 400 ·
128-char key accepted · cached error replayed as error · **expired key
treated as new and commits a second time** · key just inside window
replays · TTL configurable · reconciliation read finds the committed
payment after a 502 · reconciliation read returns nothing when nothing
committed · filter by InvoiceID · GET ignores the key · reset clears
everything · ledger exposes counts/keys · PUT vs POST with one key is a
conflict · fingerprint stable and order-insensitive · mock only ever
binds loopback.

### M1 conditions — all seven addressed in this milestone
| # | Fix | Verified by |
|---|---|---|
| D-1 | `client_read_timeout_seconds()` reads httpx's **actual** default; the repro now compares it to `--delay` and refuses to run with a margin under 1.0 s | `--delay 1` → **exit 3** with an explanatory error; `--delay 6.5` → exit 0 |
| D-2 | Repro returns **exit 1** when the duplicate is not reproduced | code path present; D-1 now intercepts the main cause before it can occur |
| D-3 | `*_latest.json` is written **only** for a canonical run (pfmcp client, 2 attempts, adequate margin); non-canonical runs save a timestamped file and say so. Every result now embeds `invocation.argv`, the real read timeout, and the margin | non-canonical `--client isolated` run left `m1_baseline_latest.json` byte-identical (md5 compared before/after) |
| D-4 | `assert_loopback()` gate on **both** client paths, called before `XERO_API_BASE` is mutated | `https://api.xero.com` → REFUSED; `127.0.0.1` and `localhost` → allowed |
| D-5 | `handle_one_request` guard + `_QuietServer.handle_error` in both mocks swallow expected client aborts | stderr from a full canonical run is now 123 bytes, containing a single httpx INFO line and **zero** tracebacks |
| D-6 | BUILD_LOG timing corrected to ~5.02–5.15 s and marked non-invariant | recorded in the M1 verdict section above |
| D-7 | `attempt_index` assigned **inside** the lock in both mocks | code; `test_ledger_exposes_counts_and_keys_for_assertions` asserts indexing |

`m1_baseline_latest.json` is regenerated by any canonical run, so this
log deliberately **does not** name which timestamped file it currently
equals — that claim goes stale the moment anyone (builder or reviewer)
re-runs the repro, and it did exactly that twice. Each result file now
embeds its own `invocation` block, so provenance is read from the file
itself rather than from prose here. (M2 review C-6.)

### What this proves / does not prove
- **Shows:** this mock enforces the modelled idempotency contract — same
  key and payload commit once, conflicting payloads are rejected,
  distinct keys are not falsely blocked, and an expired key stops
  protecting the caller.
- **Does not show:** that Xero behaves identically. The mock is a
  simulation built from Xero's published documentation, not from
  observed Xero behaviour. No real endpoint was contacted.

### Known limitations
- Idempotency is server-wide; Xero scopes key re-use per app.
- No OAuth, tenant isolation, rate limiting, multicurrency, or
  payment-field validation.
- The injectable clock means expiry tests verify the *logic*, not real
  elapsed-time behaviour.
- `mocks/fault_server.py` and `repro/baseline_mock.py` now contain
  similar connection-abort handling; deliberately not refactored into a
  shared module, to keep M1's approved artifact independently runnable.

### M2 — Independent review verdict

**Reviewer:** separate `general-purpose` agent, fresh context, had not
seen `mocks/`, `tests/` or the M2 `repro/` changes. **Report:**
`reviews/M2-review.md`. **Verdict: `APPROVED WITH CONDITIONS`**, with the
reviewer explicitly confirming none of the conditions blocks M3.

**Same independence limitation as M1**, stated again rather than
assumed: separate context, independent reading and execution, but the
same session, machine, interpreter, venv and checkout. Not an
independent environment or party. Windows 11 / Python 3.14.6 /
httpx 0.28.1 only.

**Verification the reviewer performed itself:**
- Ran the suite **three times**: 25 passed in 15.20 s / 14.78 s /
  14.88 s. No flake.
- `pfMCP` untouched — `status` and `diff --stat` empty, HEAD unchanged.
- Its own probe script driving `mocks.fault_server` directly, bypassing
  the project's own tests and fixtures, confirming every contract point.
- **8 mutations** against a scratch copy of the mock.
- A 480-request concurrency probe (24 threads × 20 trials).
- Exercised all seven M1 conditions, including hash-based provenance
  reconstruction of `m1_baseline_latest.json`.

**The result that mattered most.** The reviewer broke the mock in the
single most dangerous way available — replay the cached response *and*
commit again — and confirmed **4 tests failed, every one of them on
`assert state.snapshot()["payment_count"] == 1`**, while all HTTP-status
and replay-marker assertions still passed. That is direct evidence that
the ledger assertions are doing the work and that the suite would catch
a mock which silently double-pays. Mutation results: 5 killed
(replay-plus-commit, conflicting-payload acceptance, GET honouring the
key, naive payload-hash dedupe), 3 survived.

**Conditions, and what was done about each.** Four were fixed
immediately because they were cheap and they weakened the evidence;
four are tracked.

| # | Condition | Due | State |
|---|---|---|---|
| C-1 | The three surviving mutations (TTL `360`→`3600`, max key `128`→`256`, expiry `>=`→`>`) showed the suite derived its values **from the constants** and never asserted the literal documented numbers — so the mock was verified self-consistent, not verified against Xero's documentation | M4 | **fixed now** — `test_documented_xero_constants_are_the_official_values` pins `128` and `360.0`; the over-long-key test now builds its key from the literal `129` |
| C-3 | No test at exactly `t == ttl` | M4 | **fixed now** — `test_key_exactly_at_ttl_boundary_has_expired` pins the `>=` boundary |
| C-8 | `MUTATING_METHODS` clause is vacuous for current callers | — | **resolved now** — kept deliberately, with a comment stating it is an executable statement of the rule so a future non-mutating caller cannot silently start consuming keys |
| C-6 | `BUILD_LOG.md:468` was corrected by appending rather than amending in place; `STATUS.md` named a specific run as `latest` and **was already false when written** (reviewer proved by MD5 that `latest` was the builder's `...142045Z`, not the M1 reviewer's `...140859Z`) | now | **fixed now** — line 468 amended in place; both records now refuse to name a specific file as `latest` and point at each result's embedded `invocation` block instead |
| C-7 | "each asserting **both**" overstated — 4 of 25 tests are legitimately non-ledger | now | **fixed now** — reworded to "every behavioural test", naming the four exceptions |
| C-2 | Empty-string key is silently treated as absent (`if key:`), so it commits twice and caches nothing | **M3 (tool must reject it)**, M4 (mock side) | tracked — feeds directly into M3's key validation |
| C-4 | `lookup → commit → store` is not atomic per key; 480 concurrent same-key requests gave ledger 1 in 20/20 trials, so the race is **latent, not disproven** | before any concurrent M5/M6 run | tracked |
| C-5 | The suite's own timeout-vs-stall margins (0.5 s vs 2.0 s) are unasserted — the same shape as D-1 | M4 | tracked |

After the C-1 and C-3 additions: **27 passed**.

**Reviewer disclosures, recorded rather than quietly absorbed:**
- Its canonical repro run replaced `m1_baseline_latest.json` again, and
  it added three `repro/results/*.json` review artifacts. This is the
  second time this has happened, which is why the records no longer name
  a specific file as `latest` (C-6).
- It did **not** re-fetch `developer.xero.com`, so M0 §6's transcription
  of the official contract is an input it accepted. **If M0 misread the
  guide, M2 faithfully models the misreading.** This is the single
  largest unverified dependency in the project so far and is carried
  forward as a known limitation.
- It did not re-run pfMCP's own suite.
- The `--delay 6.5 → exit 0` claim in the M2 builder record was *not*
  independently re-run (it would have clobbered `latest` again); the
  reviewer labelled it inference. It was, however, run by the builder.

**Gate decision: PROCEED TO M3**, carrying C-2 (into M3's key
validation), C-4 (hard requirement before concurrent M5/M6) and C-5
(M4).

---

## M3 — Minimal Xero tool implementation (builder record)

**Date:** 2026-11-16
**Role:** Implementation agent
**Status:** Built; submitted for independent review.
**Unlocked by:** M2 `APPROVED WITH CONDITIONS` + reviewer confirmation
that nothing blocks M3.

### Branch
`feat/retry-safe-create-payment` in the `pfMCP` checkout. `main` is
untouched. Diff: **1 file, +218 / -12** — `src/servers/xero/main.py`
only. No other tool, no dependency change, no reformatting.

### The API-contract decision (plan §10 M3 task 3) — RESOLVED, with evidence

I re-verified the live Xero documentation rather than relying on M0's
transcription, because the M2 reviewer correctly identified that
transcription as the project's largest unverified dependency.

| Endpoint | What `POST` means | What `PUT` means |
|---|---|---|
| **Invoices** | "Use this method to **create or update** an invoice." | "you can **only create** new invoices with this method" |
| **Payments** | "Use this method to **delete (reverse)** payments…" | "Use this method to **apply payments** to approved AR and AP invoices…" |

*(official documentation, re-read 2026-11-16)*

This is the decisive comparison, and it changes the character of the
finding. On ordinary endpoints `POST` is a perfectly valid create verb —
which is why every other `create_*` tool in this file uses `POST` and
evidently works. **Payments is a genuine special case:** because payments
"cannot be modified, only created and deleted", the slot that `POST`
occupies elsewhere has been reused for deletion. So `create_payment`
using `POST` is not an instance of a safe house style; it is wrong for
this one endpoint specifically.

**Decision: changed to `PUT`.** The payload is unchanged.

**Honest limits on that decision:** I cannot test against real Xero, so
what `POST /Payments` (collection, no `PaymentID`, payment body) actually
does today in production is **Unknown** — Xero may accept it leniently.
What is established is that `PUT` is the documented creation method and
`POST` is documented for deletion. Labelled: *official documentation*,
**not tested against live Xero**.

### Changes made

1. **`call_xero_api` (−1/+6 lines, additive in effect).** The raised
   exception now carries `.status_code`. Same exception type, same
   message, so every existing caller is unaffected; it simply lets the
   payment path tell a definite 4xx from an ambiguous 5xx without
   string-parsing. The two other `format_xero_error` raise sites (in the
   download helpers) were deliberately left alone.
2. **Three module-level helpers**, beside the existing ones:
   `validate_idempotency_key`, `is_ambiguous_transport_outcome`,
   `idempotency_window_may_have_expired`, plus the documented constants
   `XERO_IDEMPOTENCY_MAX_KEY_LENGTH = 128` and
   `XERO_IDEMPOTENCY_WINDOW_SECONDS = 360`.
3. **`create_payment` schema.** Added `idempotencyKey` as a **required**
   string, and optional `operationStartedAt`. Naming follows the
   convention already in this file (`add_attachment`,
   `upload_attachment`, `email_invoice` all use `idempotencyKey`). The
   `reference` description now states explicitly that it is business
   metadata and **must not** be used as an idempotency key.
4. **`create_payment` handler.** Validates the key before sending;
   sends `PUT` with `Idempotency-Key` through the existing
   `extra_headers` mechanism; catches ambiguous transport outcomes and
   returns structured `OUTCOME_UNKNOWN`, or `RECONCILIATION_REQUIRED`
   when `operationStartedAt` shows the six-minute window may have
   elapsed. Definite failures are re-raised untouched, so existing error
   behaviour is preserved for them.

### Required vs optional key — decision and its cost

The plan (§10 M3 task 5) says make it **required** unless M0 found a
compelling compatibility constraint. M0 found that the three existing
idempotency-aware tools make it *optional*. I judged that a convention,
not a compelling constraint, and went with **required**, because an
optional key on a payment tool is a silent bypass: any agent that omits
it gets no protection and no warning.

**The cost, stated plainly:** this is a **breaking interface change** for
existing `create_payment` callers, who would now get a validation error.
That is acceptable for a prototype whose purpose is to demonstrate the
safe shape, but it is exactly the kind of thing that decides whether a
real PR is accepted. **Flagged for Raj as a decision to confirm before
any PR.** The alternative — optional with a loud warning — is a
one-line change if preferred.

### Also addressed
- **M2 condition C-2** (empty-string key silently treated as absent):
  the tool now rejects `""` and whitespace-only keys as definite
  failures. Verified by parameterised test.

### Commands run
```bash
git checkout -b feat/retry-safe-create-payment
pfMCP/.venv/Scripts/python.exe -m pytest tests/ -p no:cacheprovider -q
cd pfMCP && .venv/Scripts/python.exe -m pytest   tests/servers/xero/test_accounting_expansion.py   tests/servers/xero/test_attachment_download.py   tests/servers/xero/test_get_invoice_pdf.py   tests/servers/xero/test_update_invoice_status.py   tests/servers/xero/test_imda_tools.py -p no:cacheprovider -q
git diff --stat
```

### Actual results (*verified by local test*)
- **Prototype suite: 46 passed** (27 mock + 19 new end-to-end tool
  tests), 52.11 s.
- **pfMCP regression: 37 failed, 20 passed — byte-identical to the M0
  baseline.** All 48 credential-bug occurrences are the pre-existing
  `_invoke()` patch-ordering issue documented in M0 §7, not anything
  introduced here.

The new tool tests drive the **real** `create_server(...).dispatch(...)`
against the M2 mock, injecting credentials through the
`credential_resolver` parameter that `create_server` already exposes —
which also sidesteps pfMCP's own test-helper bug without modifying their
test infrastructure.

Proven end to end: `PUT` is sent with the `Idempotency-Key` header ·
business fields preserved · invalid/missing/empty/over-long keys are
definite failures that send nothing · timeout after commit returns
`OUTCOME_UNKNOWN` (not `"Error: "`) while the ledger shows the payment
did commit · 502 after commit likewise · **retry with the same key
leaves exactly one payment** · changed payload with the same key is
rejected · distinct keys still create distinct payments · expired window
returns `RECONCILIATION_REQUIRED` pointing at `list_payments` ·
unparseable or recent `operationStartedAt` does not invent an expiry ·
identical `reference` with different keys creates two payments, proving
`reference` is not the key.

### Known limitations
- Not tested against live Xero; the mock is built from documentation.
- `RECONCILIATION_REQUIRED` depends on the caller passing
  `operationStartedAt`. Without it the tool cannot know the key's age and
  deliberately does not guess — it returns `OUTCOME_UNKNOWN` instead.
  The tool does not itself perform reconciliation; it instructs the
  caller to read first.
- `is_ambiguous_transport_outcome` treats all 5xx as ambiguous. A 5xx
  raised before any commit is then reported as ambiguous rather than as
  a definite failure — deliberately the safe direction.
- M2 conditions C-4 (concurrency) and C-5 (test margins) remain open.

### M3 — Independent review verdict

**Reviewer:** separate `general-purpose` agent, fresh context. **Report:**
`reviews/M3-review.md`. **Verdict: `APPROVED WITH CONDITIONS`.**

**This review was stronger than M1's and M2's on the axis that mattered
most.** The M2 reviewer had flagged that nobody had re-fetched
`developer.xero.com`, making M0's transcription "the single largest
unverified dependency in the project". **The M3 reviewer re-fetched all
three official pages itself** (WebFetch returns only titles because the
site is JavaScript-rendered, so it loaded them in a browser and extracted
the rendered article text). **That dependency is now discharged.**

What it independently confirmed about the contract decision:
- Payments: `Methods Supported: GET, PUT, POST`; `PUT` = "apply payments
  to approved AR and AP invoices"; `POST` = "delete (reverse)
  payments… **Payments cannot be modified, only created and deleted**",
  with `PaymentID` required.
- Invoices: `POST` = "create or update an invoice"; `PUT` = "you can
  **only create** new invoices with this method".
- Both quoted table cells in the M3 record are **verbatim accurate**, and
  so is M0 §6.
- It went further than asked and checked the **payload**: Xero's
  documented `PUT Payments` example is byte-for-byte the
  `{"Payments":[{"Invoice":{"InvoiceID"…},"Account":{"AccountID"…},
  "Date","Amount"}]}` shape the handler builds.
- Idempotency guide re-fetched: POST/PUT/PATCH, 6 minutes, 128
  characters, 400 on a different request. So `PUT` is
  idempotency-eligible and both constants are right.

**Verdict on the change: correct and adequately justified, not
risky-unverified.**

**Other independent verification:**
- `grep -nE "uuid|secrets|random|token_hex|sha256|hashlib|md5"` over the
  file → **no matches**. There is no key generator anywhere; the key
  reaches the wire by exactly one route. `reference` goes only to
  `payment["Reference"]`.
- Verified empirically that `ConnectError ⊂ NetworkError` and
  `ConnectTimeout ⊂ TimeoutException` — so the classifier is correct
  **only because** the early return runs first.
- Proved the old bug is gone by mutation rather than by reading:
  disabling the classifier reproduced
  `Error executing tool create_payment:` with an empty message — the
  literal `"Error: "`.
- Scope clean: 8 hunks, 1 file; `send_message` and
  `create_batch_payment` untouched; the `call_xero_api` change cannot
  affect the other **72** call sites; the two other `format_xero_error`
  raise sites correctly left alone.
- Prototype suite **46 passed**; pfMCP regression **37 failed / 20
  passed — exactly the M0 baseline**, 48 `credentials_missing`
  occurrences, no new cause.
- M2's condition **C-2 genuinely satisfied**, confirmed three ways
  including by mutation (removing the check lets `'   '` reach the
  transport: `Illegal header value b'   '`).

**Mutation campaign: 7 mutations, 6 killed, 1 survived.** PUT→POST
killed 1; dropping the header killed 4 including the double-pay test;
classifier→always-definite killed 6; expiry→always-true killed 5;
removing the empty-key check killed 2; removing the 128 limit killed 1.
**Survivor: deleting the `ConnectError`/`ConnectTimeout` early return
changed nothing — 19 passed.**

#### Conditions and what was done

| # | Finding | Action |
|---|---|---|
| **F-1** (Medium) | `OUTCOME_UNKNOWN`'s `retryGuidance` said "retry with the SAME idempotencyKey" with **no window caveat**. Since `operationStartedAt` is optional this is the *default* path, so an agent following it after six minutes double-pays — exactly what §7 forbids | **fixed now.** The guidance is now conditional on the window, tells the caller to read state back first if more time has passed or it cannot tell, and asks for `operationStartedAt`. This had to be fixed before M5/M6, where an agent actually reads it |
| **F-2** (Medium) | The connect-error carve-out was asserted by **no test** — the surviving mutation. The mock is always listening, so no end-to-end test can produce a `ConnectError` | **fixed now.** New `tests/test_outcome_classifier.py` unit-tests the classifier directly, pins the httpx inheritance that makes the ordering load-bearing, and includes a **real** connect error against a deliberately closed port. **Mutation re-run: deleting the carve-out now fails 3 tests** (was 0) |
| **F-3** (Low–Med) | A 2xx with an unparseable body raised `JSONDecodeError`, classified **definite** — the dangerous direction for a payment that almost certainly succeeded | **fixed now.** `JSONDecodeError`/`UnicodeDecodeError` classify as ambiguous, with tests |
| **F-5** (Medium) | **Nothing is committed.** `git diff main...HEAD` is empty; the payment-creation change exists only in the working tree, and the records read as though it were committed | **records corrected; commit NOT made.** See the decision note below |
| **F-6** (Medium) | `STATUS.md` → Safety posture claimed "`pfMCP/` checkout unmodified — `git status` clean", now false | **fixed now** — amended in place and marked as a correction |
| **F-7** (Low) | "`call_xero_api` (2 added lines)" is really −1/+6 | **fixed now** |
| **F-8** (Low) | The success path returns the raw Xero payload rather than §8's `{"status":"SUCCESS"…}`, with no replay marker | **declared, not changed.** §8 calls its examples illustrative and tells us to fit existing MCP conventions; every other tool here returns the raw payload, and wrapping it would be a gratuitous client-visible change. Recorded as a deliberate decision for Raj to overrule if he wants the §8 shape |
| F-4 (Low) | `PoolTimeout` classified ambiguous though never sent — safe direction | noted; now covered by a test |

**Suite after these fixes: 74 passed** (was 46).

#### The commit condition (F-5) — why I did not act on it

The reviewer's recommendation was to commit the branch and record the
SHA. **I have not done that, and a reviewer cannot authorise it.**
`AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` §3 Phase 6 says plainly: "Do not
create commits unless the approved project instructions explicitly
authorize commits. Never push, merge, publish, deploy, or open a pull
request without Raj's explicit permission." Nothing in
`BUILD_PLAN_peakflo.md` authorises commits, and Raj has not asked for
one.

So the finding is **real and the records are now accurate about it**:
+237/−12 of payment-creation code currently exists only in the working
tree of `pfMCP/`, on branch `feat/retry-safe-create-payment`, uncommitted
and unpushed. The practical risk is that it could be lost.
**Escalated to Raj as a decision rather than resolved autonomously.**

**Gate decision: PROCEED TO M4.** F-1, F-2, F-3, F-6, F-7 are fixed;
F-5 is escalated with accurate records; F-8 is a declared decision.
Carried into M4: C-2 (mock side), C-5 (unasserted margins, now also
applying to `test_create_payment_tool.py`'s 7.0 s stall vs httpx's
implicit 5 s default). C-4 (concurrency) remains a hard requirement
before any concurrent M5/M6 run.

### F-5 resolved — M3 work committed

**Date:** 2026-11-16. **Authorised by:** Raj, explicitly, in session
("Commit the working tree changes with a sensible message"). This is the
permission `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` §3 Phase 6 requires;
the earlier refusal stands as correct, since the request came from the
reviewer rather than from Raj.

- **Commit:** `eb4685f` — *feat(xero): make create_payment retry-safe
  with idempotency key*
- **Branch:** `feat/retry-safe-create-payment`
- **Contents:** 1 file, +237 / −12 — `src/servers/xero/main.py` only.
- `git diff main...HEAD` is now non-empty, so the approved checkpoint
  has a real SHA.
- **Nothing pushed.** 1 unpushed commit; `origin/main` untouched. No PR
  opened. Those still require separate permission.
- **Pre-commit checks run:** secret scan over the diff
  (`api[_-]?key|secret|token|password|bearer|client_secret|xoxb|sk-|ghp_`)
  — every hit was an existing parameter name (`access_token`,
  `api_key`), no values; `git status` confirmed only the intended file
  was staged.
- The committed content is byte-identical to what the 74-passing suite
  was run against, so no re-verification was needed.

**Not committed, deliberately:** the parent repository
`R:\Internship_Outreach_prototype` contains unrelated uncommitted user
work (`Composio`, `Emergent/README.md`, `Emergent/pyproject.toml`,
`Emergent/.claude/`, `Emergent/.streamlit/`, `Emergent/app/`,
`Emergent/tests/ui/`) alongside this untracked `Peakflo/` folder. Per
`BUILD_PLAN_peakflo.md` §12 rule 16, that work was left exactly as
found. The prototype's own records and code (`BUILD_LOG.md`,
`STATUS.md`, `mocks/`, `tests/`, `repro/`, `reviews/`) therefore remain
untracked. Raised with Raj rather than decided here.

### Project records committed

**Date:** 2026-11-17. **Authorised by:** Raj ("Yes, commit Peakflo/").

- **Commit:** `2c52b05` — *Add Peakflo retry-safe payment prototype and
  its build records* — 32 files, 9,836 insertions, in the parent
  repository `R:\Internship_Outreach_prototype`.
- **Scoped to `Peakflo/` only.** Raj's unrelated work (`Composio`,
  `Emergent/README.md`, `Emergent/pyproject.toml`, `Emergent/.claude/`,
  `Emergent/.streamlit/`, `Emergent/app/`, `Emergent/tests/ui/`) was
  left unstaged and unmodified, verified before and after.
- **`Peakflo/.gitignore` added first**, because a plain `git add
  Peakflo/` produced `warning: adding embedded git repository:
  Peakflo/pfMCP` — it would have recorded the pfMCP clone as a gitlink
  pointing at a commit that does not exist upstream, and swept in
  `__pycache__` artefacts. The ignore file excludes `pfMCP/`,
  `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, virtualenvs and `.env`
  files, and explains why in a comment.
- **Secret scan before staging:** no credential-shaped values in any
  committed file. The only token-like strings present are the
  self-labelling fakes `fake-local-token-not-a-secret` and
  `fake-local-tenant`.
- **Suite re-run on the committed state: 74 passed.**
- **Nothing pushed.** The branch has no upstream configured.

**Flagged for Raj — the branch this landed on.** The parent repository
was checked out on **`livecheck/m0-m1-skeleton`**, a LiveCheck feature
branch, so `2c52b05` now sits directly on top of `328e9a2` and
`f27dfbc`, which are LiveCheck commits. The Peakflo prototype is
therefore mixed into unrelated feature history. I did not switch or
create a branch, because changing the checked-out branch is more
invasive than committing and was not what was asked. Moving it to a
branch of its own is straightforward but rewrites that branch's tip, so
it needs Raj's decision.

### Where each piece of work now lives

| Work | Repository | Branch | Commit |
|---|---|---|---|
| Xero `create_payment` change | `Peakflo/pfMCP` (clone of `peakflo/pfMCP`) | `feat/retry-safe-create-payment` | `eb4685f` |
| Mock, repro, tests, reviews, records | `R:\Internship_Outreach_prototype` | `livecheck/m0-m1-skeleton` | `2c52b05` |

Neither has been pushed. No pull request has been opened against
`peakflo/pfMCP`; doing so needs explicit permission and is M8 work.

### Peakflo commit moved to its own branch

**Date:** 2026-11-17. **Authorised by:** Raj ("Yes, move it").

`2c52b05` had landed on `livecheck/m0-m1-skeleton`, mixing the prototype
into unrelated LiveCheck feature history. Moved as follows:

```bash
git branch peakflo-retry-safe 2c52b05     # new branch at the commit
git reset --mixed 328e9a2                 # LiveCheck tip back to where it was
```

**`--mixed`, deliberately not `--hard`.** A hard reset would have
destroyed Raj's uncommitted `Composio` and `Emergent` changes, which are
working-tree modifications to tracked files. `--mixed` moves the branch
pointer and resets the index while leaving the working tree alone.

**Verified after the move:**
- `livecheck/m0-m1-skeleton` tip = `328e9a2` — exactly its pre-commit
  state, as if the Peakflo commit had never been made there.
- `peakflo-retry-safe` tip = `2c52b05`, all 32 files intact.
- Raj's uncommitted work unchanged and still present: `Composio`,
  `Emergent/README.md`, `Emergent/pyproject.toml`, `Emergent/.claude/`,
  `Emergent/.streamlit/`, `Emergent/app/`, `Emergent/tests/ui/`.
- `Peakflo/` is untracked on LiveCheck again, as before the commit; all
  files still on disk.
- Suite re-run: **74 passed.**

**A cherry-pick onto `main` was considered and rejected.** `main` is an
ancestor of LiveCheck (15 commits behind) and carries no `Peakflo/`, so
the cherry-pick itself would have applied cleanly — but it requires
checking out the new branch, which would have had to reconcile 15
commits of working-tree differences while `Composio` and `Emergent` were
dirty. Not worth the risk. `peakflo-retry-safe` therefore has the
LiveCheck commits as ancestors, which is ordinary branch behaviour: it
was simply cut from that point. It can be rebased onto `main` later,
when the working tree is clean, if a fully independent lineage is
wanted.

**Known friction to be aware of.** `git checkout peakflo-retry-safe`
will currently be refused, because the `Peakflo/` files exist untracked
in the working tree and are tracked on that branch. Nothing is lost —
the commit holds them — but switching to that branch needs those
untracked copies moved aside first. Also note `BUILD_LOG.md` and
`STATUS.md` have since been appended to (this section included), so the
working-tree copies are **newer** than the versions inside `2c52b05`;
a forced checkout would discard those later edits.

---

## M4 — Automated integration and regression tests (builder record)

**Date:** 2026-11-17
**Status:** Built; submitted for independent review.
**Unlocked by:** M3 `APPROVED WITH CONDITIONS`, with F-1/F-2/F-3/F-6/F-7
fixed and F-5 resolved by Raj's authorised commit.

### Objective (BUILD_PLAN_peakflo.md §10 M4)
Prove expected behaviour across normal, failure, retry and expiry
scenarios, asserting both returned status and ledger side effects.

### A real defect found by M4 testing — and fixed

Writing the expiry test exposed a genuine gap in M3's implementation.
`RECONCILIATION_REQUIRED` was only produced **after** an ambiguous
failure, which meant the tool still *sent* the create request when the
key was known to be stale. The companion test
`test_expired_window_without_start_time_can_double_pay` demonstrates
what that costs: a stale-key send **commits a second payment**.

`BUILD_PLAN_peakflo.md` §7 is explicit — once the window may have
elapsed, "Do not automatically create a new key and resubmit. First
reconcile payment state." The guard is now **pre-flight**: when
`operationStartedAt` shows the key is older than the documented window,
the tool returns `RECONCILIATION_REQUIRED` with `"requestSent": false`
and sends nothing at all. Verified by asserting the mock's
`attempt_count` is unchanged — nothing reached the server.

Both ambiguous outcomes (`OUTCOME_UNKNOWN` and `RECONCILIATION_REQUIRED`)
now carry `requestSent`, so a caller can tell whether anything was
actually transmitted. The success path deliberately still returns Xero's
raw payload unchanged — the declared F-8 decision — so it carries no such
field.

*(+47 lines in `src/servers/xero/main.py`, on top of the committed
`eb4685f`.)*

### C-4 concurrency — and an honest negative result first

The atomic reservation was implemented: `begin_operation` decides and
reserves under one lock; `finish_operation` publishes and releases
waiters; the outcome is published **before** any artificial stall, so a
concurrent duplicate is freed as soon as the result exists. `reset()`
releases waiters so it cannot hang a live request, and an owner that
raises still publishes, so waiters cannot hang.

**Then the fix failed to prove itself.** Removing the reservation
entirely did not fail a single concurrency test — 5 passed against the
mutated mock. The natural check-then-act window is only as wide as a
dict write, which is exactly why the M2 reviewer's 480 concurrent
requests produced one ledger row in 20/20 trials. The tests were
therefore worthless as evidence, and "the reservation is necessary"
was an untestable claim.

Fixed by adding `MockState.commit_delay_seconds` (test support only,
default `0.0`, documented in both the code and the mock contract), which
widens that window deterministically. Result:

| | ledger rows from 8 concurrent same-key requests |
|---|---|
| With the reservation | **1**, every run |
| Reservation removed (mutation) | **6–8**, varying by run (observed 7, 6, 7, 8, 8 by the reviewer; 6 by the builder) |

So the race is now **demonstrated**, not merely suspected, and C-4's fix
is verified rather than asserted.

### Other conditions closed
- **C-2 (mock side).** `key_is_usable()` makes an empty or
  whitespace-only header value explicitly **absent** rather than
  silently conflated with "no header", and the attempt log records
  `key_treated_as_absent`. Tested: two empty-key requests commit twice
  and cache nothing.
- **C-5 (margins).** Four tests pin the relationships the suites rely
  on: httpx's implicit 5.0 s default, the 7.0 s tool-level stall, the
  mock-level stall-vs-timeout margin, and that `INFLIGHT_WAIT_SECONDS`
  exceeds the longest stall. *(Corrected after review: two of these were
  initially vacuous — they asserted arithmetic on literals retyped from
  another file, so shrinking the real margin left them green. They now
  read the actual constants. C-5 was only nominally closed before this.)*

### Files
- `tests/test_m4_integration.py` (new; **36 tests** after the review repairs)
- `mocks/fault_server.py`, `mocks/MOCK_CONTRACT.md` (concurrency,
  empty-key handling, test-support hook)
- `pfMCP/src/servers/xero/main.py` (pre-flight reconciliation guard)
- `tests/test_create_payment_tool.py` (**two** tests updated to the
  improved behaviour, each with the reason recorded in the test)

### Commands run
```bash
pfMCP/.venv/Scripts/python.exe -m pytest tests/ -p no:cacheprovider -q
cd pfMCP && .venv/Scripts/python.exe -m pytest   tests/servers/xero/test_accounting_expansion.py   tests/servers/xero/test_attachment_download.py   tests/servers/xero/test_get_invoice_pdf.py   tests/servers/xero/test_update_invoice_status.py   tests/servers/xero/test_imda_tools.py -p no:cacheprovider -q
```

### Actual results (*verified by local test*)
- **Prototype suite: 94 passed.** Run twice (79.45 s, 82.22 s) — no
  flake observed. *(Corrected after review: two runs in the same order
  cannot demonstrate "no ordering dependence", and no randomising plugin
  is installed, so within-file order was never shuffled. The reviewer
  separately ran the files in reversed order and the whole suite on a
  standalone copy, also green.)*
- **pfMCP regression: 37 failed / 20 passed — still exactly the M0
  baseline.** Same pre-existing `_invoke()` helper bug.

### M4 test-matrix coverage (§10 M4)
Normal success · missing/empty/invalid key · over-length key · timeout
after commit · retry with same key and payload · same key with changed
payload · different key for a distinct payment · **failure before
commit (tool level, with cached-error replay)** · commit then gateway
error · **expired key requiring reconciliation, both the dangerous path
and the protected one** · correct HTTP method and body · idempotency
header reaching the mock · existing Xero tests still at baseline.

### Known limitations
- The concurrency guarantee is verified only with the forced window;
  real-world interleavings are not exhaustively explored.
- Expiry tests use the injectable clock, so they verify the logic, not
  real elapsed time.
- `RECONCILIATION_REQUIRED` still depends on the caller supplying
  `operationStartedAt`. Without it the tool cannot know the key's age
  and deliberately does not guess — the double-pay path remains
  reachable for a caller that omits it, which
  `test_expired_window_without_start_time_can_double_pay` documents
  honestly rather than hiding.
- *(Superseded: the M4 work is committed as `dd8cc75`.)*

### M4 — Independent review verdict: `REJECTED`, then repaired

**Reviewer:** separate `general-purpose` agent, fresh context. **Report:**
`reviews/M4-review.md`. **Verdict: `REJECTED`.**

Per `AUTONOMOUS_BUILD_AND_REVIEW_PROMPT.md` §3 Phase 4, a rejection does
not advance. This is **repair attempt 1 of the 3 allowed** under Phase 5.

**This rejection was correct and valuable.** It arrived while a push to a
public repository was being prepared, and it stopped a High-severity
payment bug from being published.

**What the reviewer verified before rejecting:** suite green across
**five** runs including reversed file order and a standalone copy
(94 passed, no flake); regression at the M0 baseline with the cause read
from an actual traceback rather than assumed; seven mutations on scratch
copies, all restored and `cmp`-verified; `repro/results/` mtimes
untouched. It confirmed both halves of the builder's own defect claim by
reverting the guard with `patch -R` and watching the ledger go 1 → 2.

#### M4-1 (High) — the timezone bug

`idempotency_window_may_have_expired` silently read a timezone-naive
`operationStartedAt` as UTC. Harmless when the helper only chose a
label; dangerous once M4 promoted it to decide **send / do not send**:

- naive local time from a **UTC-negative** caller → a legitimate,
  seconds-old **first** payment is refused and silently never made
  (reviewer reproduced: `payment_count = 0, attempt_count = 0`);
- naive local time from a **UTC-positive** caller → a genuinely stale
  key reads as fresh and **is sent** — the exact duplicate the guard
  exists to prevent;
- `"2026-11-17"` hard-blocks; an integer epoch is ignored and sends.

**No test covered any of it** — the expiry tests all used tz-aware
stamps or `"junk"`.

**Fixed:** `parse_operation_started_at()` now refuses to guess. Only an
ISO-8601 instant with an explicit offset is accepted; naive values, bare
dates, non-strings and unparseable text are **definite pre-send
validation failures**. New tests cover the ambiguous inputs, both offset directions, and that
nothing is transmitted when rejected. *(An earlier draft said
"seventeen"; the suite grew 94 → 108 across all the repairs, so that
figure was wrong. Current totals are given below, counted rather than
recalled.)*

#### Three surviving mutations — behaviours reported as verified were not

| | What survived | Now |
|---|---|---|
| **M4-2** | Downgrading an in-flight fingerprint mismatch from `conflict` to a silent `wait` → **94 passed**. The test asserted only `payment_count == 1`, never the documented `400`. | Killed. The test now asserts `[200, 400]` and the documented message — and uses `commit_delay_seconds` to hold the key genuinely **in flight**, because otherwise the second request finds it already cached and exercises the wrong branch. My first repair attempt missed this and the mutation survived again. |
| **M4-3** | Publishing the outcome *after* the stall → the "released early" test still passed, duration unchanged. It was killed in the full suite only **incidentally**, by the double-pay demo. | Killed. The test now times each waiter and requires all but the owner to return in well under the stall. |
| **M4-4** | Shrinking the real margin from 2.0/0.5 to 0.6/0.5 → `test_mock_level_margins_hold` still passed, because it asserted arithmetic on **literals retyped from another file**. | Killed. The margin constants are now exported from `test_fault_server.py` and read by the check, so shrinking the real value fails it. **C-5 was only nominally closed before this.** |

All three verified killed by re-running each mutation; scratch copies
restored byte-identically.

#### Other findings

- **M4-5** `INFLIGHT_WAIT_SECONDS` equalled the test client's 30.0 s
  timeout — a needless coin flip over which error surfaces. Now 20.0 s,
  comfortably above the 7.0 s longest stall and below the client's.
- **M4-6** The entire M4 deliverable was uncommitted, so no diff review
  from version control was possible. **Committed as `dd8cc75`** on
  `feat/retry-safe-create-payment` (+113/−20).
- **M4-9** `MockState.lookup()` / `store()` became dead code once the
  reservation replaced them. Removed — leaving them would have kept a
  second, racy route to the same state.
- **M4-7** "1 vs 6" was one observation, not a number. Corrected to
  **6–8, varying** (reviewer observed 7, 6, 7, 8, 8).
- **M4-8** "no ordering dependence" was unsupported by two same-order
  runs with no randomising plugin installed. Corrected.
- **M4-10** `STATUS.md` claimed the pfMCP tree was "clean" when it was
  not — **the same false statement M3's F-6 already required fixing**.
  Corrected. *(And then got it wrong again in the other direction: the
  replacement said "NOT clean" after the work had been committed. Third
  recurrence of this class. The cleanliness and commit lines are now
  generated from `git status` / `git rev-list` output rather than
  written by hand — see the M4 re-review section.)*
- Also corrected: "All structured outcomes now carry `requestSent`" (the
  success path deliberately does not), and a `{5 mock files}` placeholder
  that was not a runnable command.

#### Deferred, with reasons
- **Making `operationStartedAt` required.** The reviewer argues it is the
  other half of the protection that made `idempotencyKey` required, and
  that in M6 an agent omitting one optional field double-pays silently.
  That is persuasive, but it is a second **breaking interface change**
  and Raj has an open decision on the first one. Raised rather than taken
  unilaterally. Note that
  `test_expired_window_without_start_time_can_double_pay` deliberately
  asserts a known-bad outcome and must be rewritten if this is hardened.

#### After repair
- **Prototype suite: 108 passed.**
- **pfMCP regression: 37 failed / 20 passed — still the M0 baseline.**
- `pfMCP` working tree clean; M4 committed as `dd8cc75`.

Resubmitted for review.

### M4 — re-review verdict (repair attempt 1): `APPROVED WITH CONDITIONS`

**Reviewer:** separate `general-purpose` agent, fresh context.
**Report:** `reviews/M4-review-2.md` (round 1's `reviews/M4-review.md`
preserved unchanged, as the gate rules require).

**M4-1 confirmed fixed**, in code, by a 21-input helper probe, and
end-to-end against the mock reading `state.snapshot()`:
- seconds-old first payment at `-08:00` → **sent**, `payment_count=1`
  (legitimate-payment-refused bug gone);
- 2-hour-old key at `+05:30` → **blocked**, `RECONCILIATION_REQUIRED`,
  `attempt_count=0` (stale-key-sent bug gone);
- naive / space-separated / bare date / empty / whitespace / junk / int
  / float / bool / list → all definite failures, nothing transmitted.
- Mutation restoring the old assume-UTC behaviour: **killed**, 6 failed.

**All three previously-surviving mutations killed**, each re-applied by
the reviewer. It independently confirmed the M4-2 test now exercises the
**in-flight** branch rather than the cached one — the `[200, 200]`
failure signature proves it, since a cached hit would have left the test
green.

**It also verified the two rewritten tests were strengthened, not
weakened**, by diffing against `2c52b05`: the `"junk"` assertion was
*inverted* because behaviour improved, and the expiry test *gained*
`requestSent is False` and `attempt_count == 0`. No assertion anywhere
was deleted or loosened.

#### What it found still open, and what was done

| # | Finding | Action |
|---|---|---|
| **R-2** | **C-5 only half closed.** Its mutation cut the *real* tool-level stall 7.0 → 5.2 s at all eight sites and the whole suite **stayed green**, because the guard retyped `tool_stall = 7.0`. My claim that all four C-5 tests "read the actual constants" was disproved by mutation. | **Fixed.** `TOOL_STALL_SECONDS` is now defined once and shared. Re-running that mutation fails: `assert (5.2 - 5.0) >= 1.0`. |
| **R-1 / C-M4-1** | `STATUS.md` traded its false "clean" for a false **"NOT clean"**, never named `dd8cc75`, and said "1 unpushed commit" where there are **2**. **Third recurrence of this class.** | **Fixed, and fixed structurally:** those lines are now *generated* from `git status` / `git log` / `git rev-list` output instead of written from memory. |
| **R-3** | Two required cases unpinned: a future-dated stamp, and the window lapsing *while in flight*. Behaviour was already right; nothing held it. | **Fixed** — both now tested, including that a mid-flight lapse still reports `requestSent: true`, since the caller's recovery differs completely. |
| **R-4** | Three of eight timezone params discriminated nothing: `1763376000`/`12.5` are caught by schema validation anyway, and `"2026-11-17"` passed even under the mutated helper because the `RECONCILIATION_REQUIRED` guidance text *contains* the substring `"operationStartedAt"`. | **Fixed** — the assertion now requires a definite failure and explicitly excludes `RECONCILIATION_REQUIRED`. |
| **R-5** | `MOCK_CONTRACT.md` still said `INFLIGHT_WAIT_SECONDS` is 30 s (code: 20.0); the `{5 mock files}` placeholder was still not a runnable command; "Seventeen new tests" was really 14; "20 tests"/"one assertion updated" stale. | **All fixed**, counts re-derived by collecting them rather than recalling: `test_fault_server` 27, `test_create_payment_tool` 19, `test_outcome_classifier` 28, `test_m4_integration` 36. |
| **R-6** | A rejected `operationStartedAt` returns an unstructured `Error: …` string rather than a structured outcome, and M6 will judge these strings. It also notes, fairly, that **tightening validation is itself a breaking contract change** taken unilaterally in the same session that deferred making the field required as too breaking to decide alone. | **Deferred to M6** as the reviewer gated it, and the inconsistency is acknowledged rather than argued away. The distinction I would draw: rejecting input that was previously *misread* removes a money bug, while requiring a new field removes a working call — but that is a judgement, and both belong in the same decision Raj makes. |

**After these repairs: 110 passed.** pfMCP regression still exactly the
M0 baseline.

**Gate decision: conditions gating M5 are cleared** (C-M4-1 and the
C-M4-2 wording half, plus R-2's code half, R-3, R-4 and R-5 done early).
Remaining, as the reviewer scheduled them: **C-M4-5 at M6** (structured
shape for rejected input, and declaring the strictness change);
**C-M4-4 at M8** (any further param tightening). `operationStartedAt`
staying optional remains **Raj's decision**, recorded here and surfaced
to him.

### Pre-publication redaction

Before the first push to a public repository, local machine paths were
replaced with `<scratchpad>`, `<downloads>` and `<home>` across
`BUILD_LOG.md` and all five review reports (8 occurrences). These
exposed a Windows username and temp-directory layout that have no place
in a public repo and cannot be removed afterwards without rewriting
published history.

**Only locations were redacted.** No finding, number, command result,
verdict or limitation was altered. The reviewers' reports are otherwise
exactly as they wrote them, rejections included.

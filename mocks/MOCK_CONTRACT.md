# Mock Xero Payments API — contract

**This is a LOCAL SIMULATION. It is not Xero and it is not Peakflo.**
Everything below describes `mocks/fault_server.py` only. Results obtained
against it demonstrate the behaviour of this mock and the client talking
to it — nothing more. They are not evidence of a real duplicate payment
and not evidence of any production incident.

Implements: `BUILD_PLAN_peakflo.md` §9 and §10 (M2).
Modelled on official Xero documentation re-verified 2026-11-16
(`BUILD_LOG.md` M0 §6).

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `PUT` / `POST` / `PATCH` | `/api.xro/2.0/Payments` | Create a payment. Honours `Idempotency-Key`. |
| `GET` | `/api.xro/2.0/Payments?InvoiceID=&Reference=` | Deterministic reconciliation read. Exact-match filters. Ignores `Idempotency-Key`. |
| `GET` | `/__ledger` | Full state: ledger, attempts, cached keys, TTL. |
| `POST` | `/__reset` | Clear ledger, attempts, cache and clock offset. Optional `{"ttl_seconds": n}`. |
| `POST` | `/__advance_clock` | `{"seconds": n}` — move the mock's clock forward so expiry is testable instantly, with no sleeping. |
| `POST` | `/__mode` | `{"mode": "...", "delay_seconds": n}` — switch fault mode at runtime. |

Both `PUT` and `POST` are accepted for creation so that the unresolved
PUT-vs-POST contract question (M3) is not pre-decided by the mock's
routing. Method **is** part of request identity, so the same key used
with a different method is a conflict.

## Fault modes

| Mode | Server behaviour | What the caller sees | Ledger |
|---|---|---|---|
| `ok` | Commit, respond | `200` | +1 |
| `commit_then_slow` | **Commit**, then stall `delay_seconds`, then respond | read timeout (if the stall exceeds the client timeout) | **+1** |
| `commit_then_502` | **Commit**, then return a gateway error | `502` | **+1** |
| `fail_before_commit` | Fail before any write | `500` | +0 |

The two middle rows are the point of the project: the caller sees a
failure while the side effect has already happened.

## Idempotency rules

Applied only to mutating methods (`POST`, `PUT`, `PATCH`), matching
Xero's documented behaviour.

| Situation | Result |
|---|---|
| No key | No protection at all. Every request commits. |
| Empty or whitespace-only key | Treated as **absent**, so no protection — and the attempt log records `key_treated_as_absent: true` rather than silently conflating it with "no header". The tool itself refuses to send such a key. |
| Two concurrent requests, same key | The first claims the key; the others **wait** for its outcome and receive the cached response. Exactly one ledger row. Xero: "Once the first call is processed, the cached response will be returned for all remaining requests." |
| Key, first use | Processed normally; outcome cached against the key. |
| Same key, **same** request | Cached response replayed. **No second commit.** Response carries `__replayed_from_idempotency_cache__: true`. |
| Same key, **different** request | `400` — `Idempotency Key: {key} is used with a different request.` Nothing committed. |
| Key longer than 128 chars | `400` — `Idempotency Key: {key} with length {n} is too long.` Nothing committed. |
| Cached outcome was an **error** | The error is replayed, even if the mock would now succeed. |
| Key **expired** (default 360 s) | **Not an error.** Treated as a brand-new key, so it commits again. |

Request identity is `sha256(METHOD | path | canonical-JSON-body)`, so key
ordering in the body does not affect it but any value change does.

### Why expiry matters

The last row is the reason `RECONCILIATION_REQUIRED` exists in the
approved design. Xero retains keys for six minutes; after that the header
provides no protection whatsoever, and a late retry will happily create a
second payment. A caller that is unsure must **read before it writes**,
which is what the `GET` endpoint above is for.

**This mock does not provide, and must not be described as providing,
permanent exactly-once execution.**

## Concurrency

A key is claimed atomically. `begin_operation` decides and reserves in
one critical section, so two callers cannot both miss the cache and both
commit; `finish_operation` publishes the outcome and releases waiters.
The outcome is published **before** any artificial stall, so a duplicate
is released as soon as the result exists rather than waiting out the
delay. A waiter that gets nothing within `INFLIGHT_WAIT_SECONDS` (20 s —
above the longest stall used in tests, below the test client's own
timeout so the failure mode is unambiguous)
receives `503`.

`MockState.commit_delay_seconds` is **test support only** (default
`0.0`): it widens the check-then-act window so the race can be forced
deterministically. Without it the window is only as wide as a dict
write, and removing the reservation fails no test — which would make
"the reservation is necessary" an untestable claim. With it, removing
the reservation reliably produces duplicates.

## Simplifications

Deliberately not modelled: OAuth, tenant isolation, rate limiting,
multicurrency, validation of payment fields, `SummarizeErrors`, history
and notes. Idempotency is scoped to the whole server (Xero scopes key
re-use per app; there is one notional app here).

## Running it

```bash
python mocks/fault_server.py --mode commit_then_slow --delay 7 --port 8788
```

Tests drive it in-process instead; see `tests/test_fault_server.py`.

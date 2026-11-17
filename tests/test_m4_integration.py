"""
M4 integration and regression tests — LOCAL SIMULATION ONLY.

Covers the cases BUILD_PLAN_peakflo.md §10 M4 requires that earlier
milestones did not reach, and closes the conditions carried out of the
M1–M3 gates:

  * C-4 concurrency: two callers racing the same key must not double-pay.
  * C-2 empty key: an empty header value must be handled explicitly.
  * C-5 margins: the stall-vs-timeout relationships the suites depend on
    must be asserted, not assumed.

Every test asserts the mock ledger as well as the returned status,
because the whole problem is that those two can disagree.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PFMCP = PROJECT_ROOT / "pfMCP"
for path in (str(PROJECT_ROOT), str(PFMCP)):
    if path not in sys.path:
        sys.path.insert(0, path)

from mocks.fault_server import (  # noqa: E402
    INFLIGHT_WAIT_SECONDS,
    MODE_COMMIT_THEN_SLOW,
    MODE_FAIL_BEFORE_COMMIT,
    MODE_OK,
    PAYMENTS_PATH,
    XERO_IDEMPOTENCY_TTL_SECONDS,
    key_is_usable,
)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_create_payment_tool import (
    TOOL_STALL_SECONDS,
    call_tool,
    valid_args,
)  # noqa: E402

KEY = "stable-operation-key-m4"


def post_payment(base_url: str, key: str | None, amount: float = 1000.0,
                 timeout: float = 30.0) -> httpx.Response:
    headers = {"Content-Type": "application/json"}
    if key is not None:
        headers["Idempotency-Key"] = key
    body = {"Payments": [{
        "Invoice": {"InvoiceID": "inv-1"},
        "Account": {"AccountID": "acc-1"},
        "Amount": amount,
        "Date": "2026-11-17",
    }]}
    with httpx.Client(timeout=timeout) as client:
        return client.put(f"{base_url}{PAYMENTS_PATH}", json=body,
                          headers=headers)


# =================================================== C-4 concurrency =====

def _fire_concurrently(base_url: str, n: int, key: str | None,
                       amount: float = 1000.0) -> list:
    """Fire n identical requests as simultaneously as threads allow."""
    barrier = threading.Barrier(n)
    results: list = [None] * n

    def worker(i: int) -> None:
        barrier.wait()  # release all at once
        try:
            results[i] = post_payment(base_url, key, amount)
        except Exception as exc:  # noqa: BLE001
            results[i] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=INFLIGHT_WAIT_SECONDS + 15)
    return results


def test_concurrent_same_key_commits_exactly_once(mock_server):
    """C-4. The race that was latent but never disproven.

    Before the atomic reservation, both callers could miss the cache and
    both commit. One ledger row is the only acceptable outcome.
    """
    base_url, state, _ = mock_server(mode=MODE_OK)

    results = _fire_concurrently(base_url, n=16, key=KEY)

    assert all(isinstance(r, httpx.Response) for r in results), results
    assert all(r.status_code == 200 for r in results)
    assert state.snapshot()["payment_count"] == 1, (
        "concurrent requests with one key must produce exactly one payment")


def test_concurrent_same_key_with_a_forced_race_window(mock_server):
    """C-4, made falsifiable.

    The tests above pass even with the reservation removed, because the
    natural check-then-act window is only as wide as a dict write. That
    makes them useless as evidence that the reservation does anything --
    the same reason 480 concurrent requests never reproduced the race.

    This test widens the window deliberately, so that removing the
    reservation reliably produces duplicate payments and this test
    reliably fails. That is what makes the fix verified rather than
    merely asserted.
    """
    base_url, state, _ = mock_server(mode=MODE_OK)
    state.commit_delay_seconds = 0.4  # force the interleaving

    results = _fire_concurrently(base_url, n=8, key=KEY)

    assert all(isinstance(r, httpx.Response) for r in results), results
    assert state.snapshot()["payment_count"] == 1, (
        "with a wide check-then-act window, only an atomic per-key "
        "reservation can keep this at one payment")


def test_concurrent_same_key_under_a_slow_commit(mock_server):
    """The widest possible race window: commit, then a long stall.

    The first caller holds the key for the whole stall. Without the
    reservation every other caller would sail past the empty cache and
    commit again.
    """
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                     delay_seconds=1.5)

    results = _fire_concurrently(base_url, n=8, key=KEY)

    assert all(isinstance(r, httpx.Response) for r in results), results
    assert state.snapshot()["payment_count"] == 1
    # Everyone who waited got the first caller's result back.
    replayed = [r for r in results
                if r.json().get("__replayed_from_idempotency_cache__")]
    assert len(replayed) == len(results) - 1


def test_concurrent_waiters_are_released_without_serving_the_full_stall(mock_server):
    """The outcome is published BEFORE the artificial delay.

    Xero: "Once the first call is processed, the cached response will be
    returned for all remaining requests."

    M4 review M4-3: this previously asserted only the ledger count, so
    moving the publish to *after* the stall left it green. It must
    measure the thing it is named for, so it now times the waiters.
    """
    stall = 3.0
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                     delay_seconds=stall)

    started = time.monotonic()
    results = _fire_concurrently(base_url, n=4, key=KEY)
    elapsed_per_result = [r.elapsed.total_seconds()
                          for r in results if isinstance(r, httpx.Response)]

    assert state.snapshot()["payment_count"] == 1
    assert all(r.status_code == 200 for r in results)

    # Exactly one caller owns the key and eats the stall; the rest are
    # released as soon as the result exists.
    quick = [e for e in elapsed_per_result if e < stall * 0.6]
    assert len(quick) == len(results) - 1, (
        f"expected {len(results) - 1} waiters released early, got "
        f"{len(quick)}; per-request times {elapsed_per_result}")
    assert time.monotonic() - started < stall * 2, "no waiter should queue"


def test_concurrent_different_keys_all_commit(mock_server):
    """Concurrency must not over-correct and block legitimate payments."""
    base_url, state, _ = mock_server(mode=MODE_OK)
    barrier = threading.Barrier(6)
    errors: list = []

    def worker(i: int) -> None:
        barrier.wait()
        try:
            post_payment(base_url, f"distinct-key-{i}")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, errors
    assert state.snapshot()["payment_count"] == 6


def test_concurrent_same_key_different_payload_is_rejected(mock_server):
    """One wins; the conflicting one is refused, not committed.

    M4 review M4-2: this must exercise the IN-FLIGHT conflict branch, not
    the cached one. Because the outcome is published before any stall,
    a second request normally arrives to find the key already cached and
    is rejected by the cache path — which left the in-flight branch
    untested and a mutation of it alive. `commit_delay_seconds` holds the
    key genuinely in flight so the intended branch is the one under test.
    """
    base_url, state, _ = mock_server(mode=MODE_OK)
    state.commit_delay_seconds = 0.5  # keep the key in flight, uncached
    outcomes: list = []
    barrier = threading.Barrier(2)

    def worker(amount: float) -> None:
        barrier.wait()
        try:
            outcomes.append(post_payment(base_url, KEY, amount=amount))
        except Exception as exc:  # noqa: BLE001
            outcomes.append(exc)

    threads = [threading.Thread(target=worker, args=(a,))
               for a in (1000.0, 2000.0)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert state.snapshot()["payment_count"] == 1, (
        "a conflicting concurrent request must not add a second payment")
    # M4 review M4-2: asserting only the ledger left this green when a
    # conflicting in-flight request was downgraded to a silent `wait`.
    # The conflict must be REPORTED, with Xero's documented 400.
    statuses = sorted(r.status_code for r in outcomes
                      if isinstance(r, httpx.Response))
    assert statuses == [200, 400], f"expected one 200 and one 400, got {statuses}"
    rejected = [r for r in outcomes
                if isinstance(r, httpx.Response) and r.status_code == 400]
    assert "used with a different request" in rejected[0].json()["Message"]


# ====================================================== C-2 empty key =====

def test_key_is_usable_helper():
    assert key_is_usable("k") is True
    assert key_is_usable(None) is False
    assert key_is_usable("") is False
    assert key_is_usable("   ") is False


def test_empty_key_is_treated_as_absent_and_recorded(mock_server):
    """C-2. An empty header value gives no protection -- explicitly.

    The mock documents this rather than silently conflating it with "no
    header". The tool itself refuses to send such a key at all, so this
    pins the mock's half of the contract.
    """
    base_url, state, _ = mock_server(mode=MODE_OK)

    post_payment(base_url, key="")
    post_payment(base_url, key="")

    snapshot = state.snapshot()
    assert snapshot["payment_count"] == 2, "an empty key protects nothing"
    assert all(a["key_treated_as_absent"] for a in snapshot["attempts"])
    assert snapshot["idempotency_keys_cached"] == []


# ======================================= failure-before-commit, tool ======

async def test_tool_reports_fail_before_commit_conservatively(mock_server):
    """A 5xx before any write is reported ambiguous -- the safe direction.

    The mock committed nothing, but the tool cannot know that from a 500
    alone, so it must not claim a definite failure.
    """
    base_url, state, _ = mock_server(mode=MODE_FAIL_BEFORE_COMMIT)

    outcome = json.loads(await call_tool(base_url, valid_args(
        idempotencyKey=KEY)))

    assert outcome["status"] == "OUTCOME_UNKNOWN"
    assert state.snapshot()["payment_count"] == 0


async def test_retry_after_failure_before_commit_replays_cached_error(mock_server):
    """Xero caches internal errors; a retry must not quietly succeed."""
    base_url, state, set_mode = mock_server(mode=MODE_FAIL_BEFORE_COMMIT)

    first = json.loads(await call_tool(base_url, valid_args(idempotencyKey=KEY)))
    assert first["status"] == "OUTCOME_UNKNOWN"

    set_mode(MODE_OK)  # the mock would now succeed...
    second = json.loads(await call_tool(base_url, valid_args(idempotencyKey=KEY)))

    # ...but the cached error wins, so still nothing committed.
    assert second["status"] == "OUTCOME_UNKNOWN"
    assert state.snapshot()["payment_count"] == 0


# ============================== expiry end-to-end: why reconciliation =====

async def test_expired_window_without_start_time_can_double_pay(mock_server):
    """The documented gap, demonstrated rather than asserted.

    Past six minutes the key protects nothing. A caller that retries
    blindly -- giving the tool no way to know the key's age -- gets a
    second payment. This is precisely the case RECONCILIATION_REQUIRED
    exists for, and it is why `operationStartedAt` matters.
    """
    base_url, state, set_mode = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                            delay_seconds=TOOL_STALL_SECONDS,
                                            ttl_seconds=XERO_IDEMPOTENCY_TTL_SECONDS)

    first = json.loads(await call_tool(base_url, valid_args(idempotencyKey=KEY)))
    assert first["status"] == "OUTCOME_UNKNOWN"
    assert state.snapshot()["payment_count"] == 1

    state.advance_clock(XERO_IDEMPOTENCY_TTL_SECONDS + 1)
    set_mode(MODE_OK)
    await call_tool(base_url, valid_args(idempotencyKey=KEY))

    assert state.snapshot()["payment_count"] == 2, (
        "an expired key no longer protects -- this is the documented gap")


async def test_expired_window_with_start_time_refuses_to_send(mock_server):
    """The protection: told the key is old, the tool does not send at all."""
    base_url, state, set_mode = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                            delay_seconds=TOOL_STALL_SECONDS)

    first = json.loads(await call_tool(base_url, valid_args(idempotencyKey=KEY)))
    assert first["status"] == "OUTCOME_UNKNOWN"
    assert state.snapshot()["payment_count"] == 1
    attempts_before = state.snapshot()["attempt_count"]

    state.advance_clock(XERO_IDEMPOTENCY_TTL_SECONDS + 1)
    set_mode(MODE_OK)
    outcome = json.loads(await call_tool(base_url, valid_args(
        idempotencyKey=KEY, operationStartedAt="2020-01-01T00:00:00Z")))

    assert outcome["status"] == "RECONCILIATION_REQUIRED"
    assert outcome["requestSent"] is False
    assert "Do NOT retry" in outcome["retryGuidance"]
    assert state.snapshot()["payment_count"] == 1, "must not create a second"
    assert state.snapshot()["attempt_count"] == attempts_before, (
        "nothing should have been sent at all -- the guard is pre-flight, "
        "not merely a different label on a failure that already happened")


async def test_reconciliation_read_then_informed_decision(mock_server):
    """The full recovery path a caller is told to follow."""
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                     delay_seconds=TOOL_STALL_SECONDS)

    outcome = json.loads(await call_tool(base_url, valid_args(
        idempotencyKey=KEY, reference="INV-RECON-M4")))
    assert outcome["status"] == "OUTCOME_UNKNOWN"

    # Follow the guidance: read the state back before doing anything else.
    with httpx.Client(timeout=10.0) as client:
        found = client.get(f"{base_url}{PAYMENTS_PATH}",
                           params={"Reference": "INV-RECON-M4"}).json()

    assert len(found["Payments"]) == 1, (
        "the caller can discover the payment did happen, and stop")
    assert state.snapshot()["payment_count"] == 1


# ================================== M4-1: timestamps must be unambiguous ==

@pytest.mark.parametrize("ambiguous", [
    "2026-11-17T09:30:00",        # naive local time -- whose clock?
    "2026-11-17 09:30:00",        # naive, space-separated
    "2026-11-17",                 # bare date: parses, means nothing precise
    "junk",
    "",
    "   ",
    1763376000,                   # epoch int
    12.5,
])
async def test_ambiguous_start_time_is_rejected_and_sends_nothing(
        mock_server, ambiguous):
    """M4 review M4-1 (High).

    This value decides whether a payment is SENT, so misreading it is a
    money bug in both directions: a naive timestamp from a UTC-negative
    caller made a legitimate seconds-old first payment look expired and
    be refused outright, while from a UTC-positive caller a genuinely
    stale key looked fresh and was SENT -- the very duplicate the guard
    exists to prevent. The tool now refuses to guess.
    """
    base_url, state, _ = mock_server(mode=MODE_OK)

    text = await call_tool(base_url, valid_args(
        idempotencyKey=KEY, operationStartedAt=ambiguous))

    # R-4: assert a DEFINITE failure specifically. Checking only for the
    # substring "operationStartedAt" was too weak -- the
    # RECONCILIATION_REQUIRED guidance text contains that word too, so a
    # value wrongly routed to the expiry path would still have passed.
    assert "OUTCOME_UNKNOWN" not in text
    assert "RECONCILIATION_REQUIRED" not in text
    assert text.lstrip().startswith("Error:") or "validation error" in text.lower(), (
        f"expected a definite validation failure, got: {text[:200]}")
    assert state.snapshot()["attempt_count"] == 0, "nothing may be sent"
    assert state.snapshot()["payment_count"] == 0


async def test_future_dated_start_time_is_not_treated_as_expired(mock_server):
    """R-3. A clock-skewed or future stamp must not read as ancient."""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    base_url, state, _ = mock_server(mode=MODE_OK)
    text = await call_tool(base_url, valid_args(idempotencyKey=KEY,
                                                operationStartedAt=future))

    assert "RECONCILIATION_REQUIRED" not in text
    assert state.snapshot()["payment_count"] == 1


async def test_window_crossed_while_in_flight_still_reports_sent(mock_server):
    """R-3. If the window lapses DURING the attempt, the request did go out.

    The pre-flight guard passed, so something was transmitted. The result
    must say so (`requestSent: true`) rather than implying nothing was
    sent, because the caller's recovery differs completely between those
    two cases.
    """
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    # Old enough that the window lapses during the stall, but not before.
    started = (datetime.now(timezone.utc)
               - timedelta(seconds=XERO_IDEMPOTENCY_TTL_SECONDS - 3)).isoformat()

    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                     delay_seconds=TOOL_STALL_SECONDS)
    outcome = json.loads(await call_tool(base_url, valid_args(
        idempotencyKey=KEY, operationStartedAt=started)))

    assert outcome["requestSent"] is True, (
        "the request was transmitted before the window lapsed; saying "
        "otherwise would send the caller down the wrong recovery path")
    assert outcome["status"] in ("OUTCOME_UNKNOWN", "RECONCILIATION_REQUIRED")
    assert state.snapshot()["attempt_count"] == 1


@pytest.mark.parametrize("offset", ["+05:30", "-08:00", "Z", "+00:00"])
async def test_unambiguous_start_times_are_accepted(mock_server, offset):
    """A fresh, explicit timestamp in any zone must let the payment through."""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    if offset == "Z":
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        sign = 1 if offset.startswith("+") else -1
        hours, minutes = (int(p) for p in offset[1:].split(":"))
        tz = timezone(sign * timedelta(hours=hours, minutes=minutes))
        stamp = datetime.now(tz).isoformat()

    base_url, state, _ = mock_server(mode=MODE_OK)
    await call_tool(base_url, valid_args(idempotencyKey=KEY,
                                         operationStartedAt=stamp))

    assert state.snapshot()["payment_count"] == 1, (
        f"a fresh {offset} timestamp must not be treated as expired")


async def test_a_fresh_payment_in_a_negative_offset_zone_is_not_refused(mock_server):
    """The regression that motivated M4-1, pinned explicitly.

    Read as UTC, a naive timestamp from (say) UTC-08:00 looks eight hours
    old -- comfortably past the six-minute window -- so a brand-new
    payment was refused and silently never made.
    """
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    tz = timezone(-timedelta(hours=8))
    stamp = datetime.now(tz).isoformat()  # explicit offset, seconds old

    base_url, state, _ = mock_server(mode=MODE_OK)
    text = await call_tool(base_url, valid_args(idempotencyKey=KEY,
                                                operationStartedAt=stamp))

    assert "RECONCILIATION_REQUIRED" not in text
    assert state.snapshot()["payment_count"] == 1


async def test_a_stale_key_in_a_positive_offset_zone_is_still_blocked(mock_server):
    """The other direction: a positive offset must not make stale look fresh."""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    tz = timezone(timedelta(hours=5, minutes=30))
    stale = (datetime.now(tz) - timedelta(hours=2)).isoformat()

    base_url, state, _ = mock_server(mode=MODE_OK)
    outcome = json.loads(await call_tool(base_url, valid_args(
        idempotencyKey=KEY, operationStartedAt=stale)))

    assert outcome["status"] == "RECONCILIATION_REQUIRED"
    assert outcome["requestSent"] is False
    assert state.snapshot()["attempt_count"] == 0


# ========================================== C-5 margins, not assumptions ==

def test_default_client_timeout_is_what_the_suites_assume():
    """C-5. Pin httpx's implicit default the tool inherits."""
    assert float(httpx.Client().timeout.read) == 5.0
    assert float(httpx.AsyncClient().timeout.read) == 5.0


def test_tool_level_stall_exceeds_the_client_timeout():
    """C-5. The tool tests stall 7.0s against an implicit 5.0s timeout."""
    client_timeout = float(httpx.AsyncClient().timeout.read)
    assert TOOL_STALL_SECONDS - client_timeout >= 1.0, (
        "the stall must clear the client timeout by a real margin, or the "
        "ambiguous-outcome tests silently stop testing anything")


def test_mock_level_margins_hold():
    """C-5, made substantive.

    M4 review M4-4: this was `assert 2.0 - 0.5 >= 1.0` on literals
    retyped from another file, so shrinking the REAL margin there left it
    passing. It now reads the actual constants those tests use.
    """
    from test_fault_server import (  # noqa: PLC0415
        MOCK_CLIENT_TIMEOUT_SECONDS,
        MOCK_STALL_SECONDS,
    )

    assert MOCK_STALL_SECONDS - MOCK_CLIENT_TIMEOUT_SECONDS >= 1.0, (
        "the mock-level tests' stall must clear their client timeout by a "
        "real margin, or those ambiguous-outcome tests stop testing anything")


def test_inflight_wait_covers_the_longest_stall_used():
    """A waiter must not time out before the owner finishes.

    Reads the real stall constant, not a retyped copy (R-2).
    """
    assert INFLIGHT_WAIT_SECONDS > TOOL_STALL_SECONDS


# ================================================= regression guards ======

async def test_create_payment_still_accepts_all_original_fields(mock_server):
    """Regression: M3 must not have dropped any pre-existing field."""
    base_url, state, _ = mock_server(mode=MODE_OK)

    await call_tool(base_url, valid_args())

    payment = state.snapshot()["payments"][0]["request_body"]["Payments"][0]
    for field in ("Invoice", "Account", "Amount", "Date", "Reference"):
        assert field in payment, f"{field} was lost from the payload"


async def test_other_tools_keep_their_optional_idempotency_key():
    """Regression: out-of-scope tools must be untouched.

    `add_attachment`, `upload_attachment` and `email_invoice` already had
    an OPTIONAL idempotencyKey. M3 changed only create_payment, so these
    must still not require one.
    """
    from mcp.types import ListToolsRequest  # noqa: PLC0415
    from src.servers.xero import main as xero_main  # noqa: PLC0415

    server = xero_main.create_server(user_id="test-user")
    tools = (await server.dispatch(ListToolsRequest(method="tools/list"))).tools
    by_name = {t.name: t for t in tools}

    for name in ("add_attachment", "upload_attachment", "email_invoice"):
        schema = by_name[name].input_schema
        assert "idempotencyKey" in schema["properties"]
        assert "idempotencyKey" not in schema.get("required", []), (
            f"{name} must keep its key optional -- it is out of scope")

    # And the one in scope must require it.
    create = by_name["create_payment"].input_schema
    assert "idempotencyKey" in create["required"]


async def test_out_of_scope_tools_still_exist():
    """Regression: nothing was removed while editing this file."""
    from mcp.types import ListToolsRequest  # noqa: PLC0415
    from src.servers.xero import main as xero_main  # noqa: PLC0415

    server = xero_main.create_server(user_id="test-user")
    names = {t.name for t in
             (await server.dispatch(ListToolsRequest(method="tools/list"))).tools}

    for name in ("create_payment", "list_payments", "create_batch_payment",
                 "email_invoice", "add_attachment", "create_invoice"):
        assert name in names, f"{name} disappeared"

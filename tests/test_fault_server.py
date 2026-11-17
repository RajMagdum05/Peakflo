"""
M2 tests for the fault-injection mock — LOCAL SIMULATION ONLY.

Every test here asserts BOTH the HTTP result AND the mock ledger side
effect, because the whole point of this project is that the two can
disagree: a caller can see a failure while a payment was in fact
committed.

These tests prove how the mock behaves. They do not prove how Xero
behaves. Nothing here contacts a real system.
"""

from __future__ import annotations

import httpx
import pytest

from mocks.fault_server import (
    MODE_COMMIT_THEN_502,
    MODE_COMMIT_THEN_SLOW,
    MODE_FAIL_BEFORE_COMMIT,
    MODE_OK,
    PAYMENTS_PATH,
    XERO_IDEMPOTENCY_TTL_SECONDS,
    XERO_MAX_KEY_LENGTH,
    fingerprint_request,
)

KEY = "stable-operation-key-0001"

# The stall/timeout pair the ambiguous-outcome tests in this module rely
# on. Exported as constants so that the margin check in
# test_m4_integration.py reads the REAL values rather than retyping
# literals — a retyped copy passes even when the real margin is broken
# (M4 review M4-4).
MOCK_STALL_SECONDS = 2.0
MOCK_CLIENT_TIMEOUT_SECONDS = 0.5


def payment_body(amount: float = 1000.00, reference: str = "INV-DEMO-001",
                 invoice_id: str = "inv-1") -> dict:
    """The payload shape pfMCP's create_payment builds (main.py:3047-3055)."""
    payment = {
        "Invoice": {"InvoiceID": invoice_id},
        "Account": {"AccountID": "acc-1"},
        "Amount": amount,
        "Date": "2026-11-16",
    }
    if reference:
        payment["Reference"] = reference
    return {"Payments": [payment]}


def create(base_url: str, body: dict, key: str | None = None,
           method: str = "PUT", timeout: float = 5.0) -> httpx.Response:
    headers = {"Content-Type": "application/json"}
    if key is not None:
        headers["Idempotency-Key"] = key
    with httpx.Client(timeout=timeout) as client:
        return client.request(method, f"{base_url}{PAYMENTS_PATH}",
                              json=body, headers=headers)


def ledger(base_url: str) -> dict:
    with httpx.Client(timeout=5.0) as client:
        return client.get(f"{base_url}/__ledger").json()


# ---------------------------------------------------------------- basics ---

def test_ok_mode_commits_once(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)

    response = create(base_url, payment_body(), key=KEY)

    assert response.status_code == 200
    assert len(response.json()["Payments"]) == 1
    assert state.snapshot()["payment_count"] == 1


def test_fail_before_commit_writes_nothing(mock_server):
    base_url, state, _ = mock_server(mode=MODE_FAIL_BEFORE_COMMIT)

    response = create(base_url, payment_body(), key=KEY)

    assert response.status_code == 500
    # The defining property: a definite failure left no side effect.
    assert state.snapshot()["payment_count"] == 0


def test_commit_then_502_is_ambiguous_not_failure(mock_server):
    """The caller sees 502 but the payment DID commit. This is the trap."""
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_502)

    response = create(base_url, payment_body(), key=KEY)

    assert response.status_code == 502
    assert state.snapshot()["payment_count"] == 1


def test_commit_then_slow_times_out_client_but_commits(mock_server):
    """Client-visible timeout, server-side side effect already done."""
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                     delay_seconds=MOCK_STALL_SECONDS)

    with pytest.raises(httpx.ReadTimeout):
        create(base_url, payment_body(), key=KEY,
               timeout=MOCK_CLIENT_TIMEOUT_SECONDS)

    assert state.snapshot()["payment_count"] == 1


# --------------------------------------------------------- idempotency ---

def test_same_key_same_payload_replays_and_commits_once(mock_server):
    """The core guarantee: retry with the same key does NOT double-pay."""
    base_url, state, _ = mock_server(mode=MODE_OK)
    body = payment_body()

    first = create(base_url, body, key=KEY)
    second = create(base_url, body, key=KEY)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json().get("__replayed_from_idempotency_cache__") is True
    # Same PaymentID returned, and only one ledger row.
    assert (first.json()["Payments"][0]["PaymentID"]
            == second.json()["Payments"][0]["PaymentID"])
    assert state.snapshot()["payment_count"] == 1


def test_retry_after_ambiguous_timeout_with_same_key_commits_once(mock_server):
    """The M1 scenario, now with a stable key: 1 intended -> 1 committed."""
    base_url, state, set_mode = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                            delay_seconds=MOCK_STALL_SECONDS)
    body = payment_body()

    with pytest.raises(httpx.ReadTimeout):
        create(base_url, body, key=KEY, timeout=MOCK_CLIENT_TIMEOUT_SECONDS)
    assert state.snapshot()["payment_count"] == 1

    # Caller retries the SAME logical operation: same key, same payload.
    set_mode(MODE_OK)
    retry = create(base_url, body, key=KEY)

    assert retry.status_code == 200
    assert retry.json().get("__replayed_from_idempotency_cache__") is True
    assert state.snapshot()["payment_count"] == 1, "retry must not double-pay"


def test_same_key_different_payload_is_rejected(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)

    first = create(base_url, payment_body(amount=1000.00), key=KEY)
    conflict = create(base_url, payment_body(amount=2000.00), key=KEY)

    assert first.status_code == 200
    assert conflict.status_code == 400
    assert "used with a different request" in conflict.json()["Message"]
    # The conflicting request must not have committed anything.
    assert state.snapshot()["payment_count"] == 1


def test_different_keys_create_distinct_payments(mock_server):
    """No false blocking: two legitimate instalments must both post."""
    base_url, state, _ = mock_server(mode=MODE_OK)

    first = create(base_url, payment_body(reference="INSTALMENT-1"),
                   key="key-instalment-1")
    second = create(base_url, payment_body(reference="INSTALMENT-2"),
                    key="key-instalment-2")

    assert first.status_code == 200
    assert second.status_code == 200
    assert state.snapshot()["payment_count"] == 2


def test_identical_payload_with_different_keys_still_creates_two(mock_server):
    """Two genuinely distinct operations can look identical. Allow both."""
    base_url, state, _ = mock_server(mode=MODE_OK)
    body = payment_body()

    create(base_url, body, key="operation-a")
    create(base_url, body, key="operation-b")

    assert state.snapshot()["payment_count"] == 2


def test_no_key_means_no_protection(mock_server):
    """Baseline: without a key the mock happily commits twice."""
    base_url, state, _ = mock_server(mode=MODE_OK)
    body = payment_body()

    create(base_url, body, key=None)
    create(base_url, body, key=None)

    assert state.snapshot()["payment_count"] == 2


def test_documented_xero_constants_are_the_official_values():
    """M2 review C-1: pin the LITERAL documented values.

    Every other test derives its key length and TTL from these constants,
    so without this test the suite is merely self-consistent: changing
    XERO_MAX_KEY_LENGTH to 256 or the TTL to 3600 would keep the whole
    suite green while silently no longer modelling Xero. These literals
    come from official documentation, re-verified 2026-11-16
    (BUILD_LOG.md M0 §6).
    """
    assert XERO_MAX_KEY_LENGTH == 128, "Xero documents a 128-character maximum"
    assert XERO_IDEMPOTENCY_TTL_SECONDS == 360.0, (
        "Xero documents a six-minute (360 s) retention window")


def test_over_long_key_is_rejected(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)
    # C-1: built from the literal 129, not from the constant, so this test
    # keeps testing "over the documented limit" even if the constant drifts.
    long_key = "k" * 129

    response = create(base_url, payment_body(), key=long_key)

    assert response.status_code == 400
    assert "is too long" in response.json()["Message"]
    assert state.snapshot()["payment_count"] == 0


def test_key_at_maximum_length_is_accepted(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)

    response = create(base_url, payment_body(), key="k" * XERO_MAX_KEY_LENGTH)

    assert response.status_code == 200
    assert state.snapshot()["payment_count"] == 1


def test_cached_internal_error_is_replayed_as_error(mock_server):
    """Xero documents that a cached error stays an error on replay."""
    base_url, state, set_mode = mock_server(mode=MODE_FAIL_BEFORE_COMMIT)
    body = payment_body()

    first = create(base_url, body, key=KEY)
    assert first.status_code == 500

    # Even though the mock would now succeed, the cached error wins.
    set_mode(MODE_OK)
    replay = create(base_url, body, key=KEY)

    assert replay.status_code == 500
    assert state.snapshot()["payment_count"] == 0


# ---------------------------------------------------------------- expiry ---

def test_expired_key_is_treated_as_new_and_can_double_commit(mock_server):
    """Why reconciliation is mandatory.

    Xero retains keys for six minutes. After that, replaying the same key
    is NOT an error -- it is processed as a brand-new request. So the
    header alone cannot protect a late retry.
    """
    base_url, state, _ = mock_server(mode=MODE_OK, ttl_seconds=360.0)
    body = payment_body()

    create(base_url, body, key=KEY)
    assert state.snapshot()["payment_count"] == 1

    # Deterministic expiry: move the mock's clock past the window.
    state.advance_clock(361.0)
    late_retry = create(base_url, body, key=KEY)

    assert late_retry.status_code == 200
    assert late_retry.json().get("__replayed_from_idempotency_cache__") is None
    assert state.snapshot()["payment_count"] == 2, (
        "an expired key must behave like a new key -- this is exactly the "
        "case that requires RECONCILIATION_REQUIRED rather than a blind retry"
    )


def test_key_just_inside_window_still_replays(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK, ttl_seconds=360.0)
    body = payment_body()

    create(base_url, body, key=KEY)
    state.advance_clock(359.0)
    replay = create(base_url, body, key=KEY)

    assert replay.json().get("__replayed_from_idempotency_cache__") is True
    assert state.snapshot()["payment_count"] == 1


def test_key_exactly_at_ttl_boundary_has_expired(mock_server):
    """M2 review C-3: pin the boundary itself, not just either side of it.

    The mock expires at ``>= ttl``, i.e. a key is already dead *at* the
    boundary. That is the safer direction (it never claims protection it
    no longer has), but it is a real choice and must be asserted so a
    later `>` / `>=` slip is caught.
    """
    base_url, state, _ = mock_server(mode=MODE_OK, ttl_seconds=360.0)
    body = payment_body()

    create(base_url, body, key=KEY)
    state.advance_clock(360.0)  # exactly the window
    at_boundary = create(base_url, body, key=KEY)

    assert at_boundary.json().get("__replayed_from_idempotency_cache__") is None
    assert state.snapshot()["payment_count"] == 2


def test_ttl_is_configurable_for_fast_tests(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK, ttl_seconds=0.01)
    assert state.snapshot()["ttl_seconds"] == 0.01


# ------------------------------------------------- reconciliation read ---

def test_reconciliation_read_finds_the_committed_payment(mock_server):
    """After an ambiguous outcome, a caller must be able to look first."""
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_502)

    response = create(base_url, payment_body(reference="INV-RECON-1"),
                      key=KEY, method="PUT")
    assert response.status_code == 502  # caller cannot tell from this alone

    with httpx.Client(timeout=5.0) as client:
        found = client.get(f"{base_url}{PAYMENTS_PATH}",
                           params={"Reference": "INV-RECON-1"}).json()

    assert len(found["Payments"]) == 1, "reconciliation must reveal the commit"
    assert state.snapshot()["payment_count"] == 1


def test_reconciliation_read_returns_nothing_when_nothing_committed(mock_server):
    base_url, _state, _ = mock_server(mode=MODE_FAIL_BEFORE_COMMIT)

    create(base_url, payment_body(reference="INV-RECON-2"), key=KEY)

    with httpx.Client(timeout=5.0) as client:
        found = client.get(f"{base_url}{PAYMENTS_PATH}",
                           params={"Reference": "INV-RECON-2"}).json()

    assert found["Payments"] == []


def test_reconciliation_filter_by_invoice_id(mock_server):
    base_url, _state, _ = mock_server(mode=MODE_OK)

    create(base_url, payment_body(invoice_id="inv-A"), key="k-a")
    create(base_url, payment_body(invoice_id="inv-B"), key="k-b")

    with httpx.Client(timeout=5.0) as client:
        found = client.get(f"{base_url}{PAYMENTS_PATH}",
                           params={"InvoiceID": "inv-A"}).json()

    assert len(found["Payments"]) == 1


def test_get_ignores_idempotency_key(mock_server):
    """Xero ignores the header on non-mutating methods."""
    base_url, _state, _ = mock_server(mode=MODE_OK)

    with httpx.Client(timeout=5.0) as client:
        first = client.get(f"{base_url}{PAYMENTS_PATH}",
                           headers={"Idempotency-Key": KEY})
        second = client.get(f"{base_url}{PAYMENTS_PATH}",
                            headers={"Idempotency-Key": KEY})

    assert first.status_code == 200
    assert second.status_code == 200
    assert "__replayed_from_idempotency_cache__" not in second.json()


# ------------------------------------------------------- infrastructure ---

def test_reset_clears_ledger_cache_and_clock(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)
    create(base_url, payment_body(), key=KEY)
    assert state.snapshot()["payment_count"] == 1

    with httpx.Client(timeout=5.0) as client:
        client.post(f"{base_url}/__reset", json={})

    snapshot = state.snapshot()
    assert snapshot["payment_count"] == 0
    assert snapshot["attempt_count"] == 0
    assert snapshot["idempotency_keys_cached"] == []
    # A previously used key is usable again after reset.
    assert create(base_url, payment_body(), key=KEY).status_code == 200


def test_ledger_exposes_counts_and_keys_for_assertions(mock_server):
    base_url, _state, _ = mock_server(mode=MODE_OK)
    create(base_url, payment_body(), key="k-1")

    snapshot = ledger(base_url)

    assert snapshot["payment_count"] == 1
    assert "k-1" in snapshot["idempotency_keys_cached"]
    assert snapshot["attempts"][0]["attempt_index"] == 1


def test_put_and_post_are_distinct_requests_for_one_key(mock_server):
    """Method is part of request identity, per Xero's definition."""
    base_url, state, _ = mock_server(mode=MODE_OK)
    body = payment_body()

    assert create(base_url, body, key=KEY, method="PUT").status_code == 200
    conflict = create(base_url, body, key=KEY, method="POST")

    assert conflict.status_code == 400
    assert state.snapshot()["payment_count"] == 1


def test_fingerprint_is_stable_and_order_insensitive():
    a = fingerprint_request("PUT", PAYMENTS_PATH,
                            {"Amount": 1, "Date": "2026-11-16"})
    b = fingerprint_request("PUT", PAYMENTS_PATH,
                            {"Date": "2026-11-16", "Amount": 1})
    c = fingerprint_request("PUT", PAYMENTS_PATH,
                            {"Amount": 2, "Date": "2026-11-16"})

    assert a == b, "key ordering must not change request identity"
    assert a != c, "a changed amount must change request identity"


def test_mock_never_targets_a_non_loopback_host(mock_server):
    base_url, _state, _ = mock_server(mode=MODE_OK)
    assert base_url.startswith("http://127.0.0.1:")

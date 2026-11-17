"""
M3 end-to-end tests: pfMCP's REAL create_payment tool against the M2 mock.

These drive `create_server(...).dispatch(...)` from the patched pfMCP
checkout, with only two things redirected:

  * ``credential_resolver`` -- injected via the parameter `create_server`
    already exposes, which also sidesteps the pre-existing patch-ordering
    bug in pfMCP's own test helpers (BUILD_LOG.md M0 §7).
  * ``XERO_API_BASE`` -- pointed at the local mock, guarded by a loopback
    assertion.

LOCAL SIMULATION ONLY. No real Xero endpoint, credential, or payment.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PFMCP = PROJECT_ROOT / "pfMCP"
if str(PFMCP) not in sys.path:
    sys.path.insert(0, str(PFMCP))

from mcp.types import CallToolRequest, CallToolRequestParams  # noqa: E402

from mocks.fault_server import (  # noqa: E402
    MODE_COMMIT_THEN_502,
    MODE_COMMIT_THEN_SLOW,
    MODE_OK,
)

pytest.importorskip("src.servers.xero.main")
from src.servers.xero import main as xero_main  # noqa: E402

KEY = "stable-operation-key-m3"

# The stall these tool-level ambiguous-outcome tests rely on, against
# httpx's implicit 5.0s default timeout. Defined once and shared, so the
# margin guard in test_m4_integration.py reads the REAL value rather than
# a retyped copy (M4 re-review R-2).
TOOL_STALL_SECONDS = 7.0


async def call_tool(base_url: str, arguments: dict) -> str:
    """Invoke the real create_payment tool against the local mock."""
    host = urlparse(base_url).hostname
    assert host in ("127.0.0.1", "localhost", "::1"), "must be loopback"

    async def fake_credentials(user_id, api_key=None):
        return ("fake-local-token-not-a-secret", "fake-local-tenant")

    server = xero_main.create_server(
        user_id="test-user", credential_resolver=fake_credentials
    )
    original_base = xero_main.XERO_API_BASE
    xero_main.XERO_API_BASE = base_url
    try:
        result = await server.dispatch(CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="create_payment", arguments=arguments),
        ))
    finally:
        xero_main.XERO_API_BASE = original_base
    return result.content[0].text


def valid_args(**overrides) -> dict:
    args = {
        "invoiceId": "inv-1",
        "accountId": "acc-1",
        "amount": 1000.00,
        "date": "2026-11-16",
        "reference": "INV-DEMO-001",
        "idempotencyKey": KEY,
    }
    args.update(overrides)
    return args


# ------------------------------------------------------- happy path ------

async def test_sends_put_with_idempotency_key_header(mock_server):
    """The two contract decisions of M3, asserted on the wire."""
    base_url, state, _ = mock_server(mode=MODE_OK)

    text = await call_tool(base_url, valid_args())

    assert "Payments" in text
    attempt = state.snapshot()["attempts"][0]
    # Xero documents PUT as the payment-CREATION method; POST /Payments is
    # delete/reverse.
    assert attempt["http_method"] == "PUT"
    assert attempt["idempotency_key"] == KEY
    assert state.snapshot()["payment_count"] == 1


async def test_business_fields_are_preserved(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)

    await call_tool(base_url, valid_args())

    payment = state.snapshot()["payments"][0]["request_body"]["Payments"][0]
    assert payment["Invoice"]["InvoiceID"] == "inv-1"
    assert payment["Account"]["AccountID"] == "acc-1"
    assert payment["Amount"] == 1000.00
    assert payment["Date"] == "2026-11-16"
    assert payment["Reference"] == "INV-DEMO-001"


# -------------------------------------------------- key validation ------

@pytest.mark.parametrize("bad_key", [None, "", "   ", 123, "k" * 129])
async def test_invalid_key_is_a_definite_failure_and_sends_nothing(
        mock_server, bad_key):
    """Validation failures must never look ambiguous, and must not send.

    Two layers reject these. Because `idempotencyKey` is now a *required*
    string in the tool schema, the MCP layer itself rejects a missing key
    or a non-string one before the handler runs; the handler's own
    `validate_idempotency_key` catches the cases the schema cannot express
    (empty, whitespace-only, over-length). Either way the property that
    matters is the same: a definite failure, and nothing sent.
    """
    base_url, state, _ = mock_server(mode=MODE_OK)

    text = await call_tool(base_url, valid_args(idempotencyKey=bad_key))

    assert "OUTCOME_UNKNOWN" not in text
    assert "RECONCILIATION_REQUIRED" not in text
    assert ("idempotencyKey" in text) or ("validation error" in text.lower())
    # Nothing reached the server at all.
    assert state.snapshot()["attempt_count"] == 0
    assert state.snapshot()["payment_count"] == 0


async def test_missing_key_is_rejected_by_the_schema(mock_server):
    """Omitting the key entirely must fail, not silently lose protection."""
    base_url, state, _ = mock_server(mode=MODE_OK)
    args = valid_args()
    del args["idempotencyKey"]

    text = await call_tool(base_url, args)

    assert "OUTCOME_UNKNOWN" not in text
    assert state.snapshot()["attempt_count"] == 0


async def test_key_at_documented_maximum_is_accepted(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)

    await call_tool(base_url, valid_args(idempotencyKey="k" * 128))

    assert state.snapshot()["payment_count"] == 1


# ------------------------------------------- ambiguous outcomes ---------

async def test_timeout_returns_outcome_unknown_not_error(mock_server):
    """The core fix: a timeout that hid a commit is NOT a definite failure."""
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                     delay_seconds=TOOL_STALL_SECONDS)

    text = await call_tool(base_url, valid_args())
    outcome = json.loads(text)

    assert outcome["status"] == "OUTCOME_UNKNOWN"
    assert outcome["operationId"] == KEY
    assert "SAME idempotencyKey" in outcome["retryGuidance"]
    # The payment DID commit -- which is exactly why this must not be
    # reported as a failure.
    assert state.snapshot()["payment_count"] == 1
    # And the old behaviour is gone.
    assert text != "Error: "


async def test_gateway_error_after_commit_is_outcome_unknown(mock_server):
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_502)

    outcome = json.loads(await call_tool(base_url, valid_args()))

    assert outcome["status"] == "OUTCOME_UNKNOWN"
    assert state.snapshot()["payment_count"] == 1


async def test_retry_after_outcome_unknown_does_not_double_pay(mock_server):
    """End-to-end proof of the whole point of the project."""
    base_url, state, set_mode = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                            delay_seconds=TOOL_STALL_SECONDS)

    first = json.loads(await call_tool(base_url, valid_args()))
    assert first["status"] == "OUTCOME_UNKNOWN"
    assert state.snapshot()["payment_count"] == 1

    # The agent follows the guidance: same key, identical payload.
    set_mode(MODE_OK)
    retry_text = await call_tool(base_url, valid_args())

    assert "OUTCOME_UNKNOWN" not in retry_text
    assert state.snapshot()["payment_count"] == 1, (
        "retrying with the same key must not create a second payment")


async def test_changing_payload_on_retry_is_rejected_by_xero_contract(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)

    await call_tool(base_url, valid_args(amount=1000.00))
    text = await call_tool(base_url, valid_args(amount=2000.00))

    assert "used with a different request" in text
    assert state.snapshot()["payment_count"] == 1


async def test_distinct_keys_still_create_distinct_payments(mock_server):
    """Two legitimate instalments must not be falsely blocked."""
    base_url, state, _ = mock_server(mode=MODE_OK)

    await call_tool(base_url, valid_args(idempotencyKey="instalment-1",
                                         reference="INSTALMENT-1"))
    await call_tool(base_url, valid_args(idempotencyKey="instalment-2",
                                         reference="INSTALMENT-2"))

    assert state.snapshot()["payment_count"] == 2


# ------------------------------------------- reconciliation path --------

async def test_expired_window_returns_reconciliation_required(mock_server):
    """Past the six-minute window the key protects nothing. Read first.

    Updated in M4: this guard is now **pre-flight**. Originally the tool
    only relabelled an ambiguous failure, which meant it still sent the
    create request — and M4 testing proved that a stale-key send commits
    a second payment. It now refuses to send at all.
    """
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                     delay_seconds=TOOL_STALL_SECONDS)

    outcome = json.loads(await call_tool(base_url, valid_args(
        operationStartedAt="2020-01-01T00:00:00Z")))

    assert outcome["status"] == "RECONCILIATION_REQUIRED"
    assert outcome["requestSent"] is False
    assert "Do NOT retry" in outcome["retryGuidance"]
    assert "list_payments" in outcome["retryGuidance"]
    assert state.snapshot()["attempt_count"] == 0, "nothing may be sent"


async def test_recent_start_time_still_returns_outcome_unknown(mock_server):
    from datetime import datetime, timezone

    base_url, _state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                      delay_seconds=TOOL_STALL_SECONDS)
    now = datetime.now(timezone.utc).isoformat()

    outcome = json.loads(await call_tool(base_url,
                                         valid_args(operationStartedAt=now)))

    assert outcome["status"] == "OUTCOME_UNKNOWN"


async def test_unparseable_start_time_is_rejected_outright(mock_server):
    """Updated in M4 (review finding M4-1).

    This previously asserted that an unparseable timestamp was silently
    ignored. That leniency was the bug: because this value now decides
    whether a payment is SENT, quietly discarding it hid a caller error
    that could cost a duplicate payment or a silently-refused one. An
    unusable value is now a definite, pre-send validation failure.
    """
    base_url, state, _ = mock_server(mode=MODE_COMMIT_THEN_SLOW,
                                     delay_seconds=TOOL_STALL_SECONDS)

    text = await call_tool(base_url, valid_args(operationStartedAt="junk"))

    assert "OUTCOME_UNKNOWN" not in text
    assert "operationStartedAt" in text
    assert state.snapshot()["attempt_count"] == 0, "nothing may be sent"


# ------------------------------------------------- definite failures ----

async def test_missing_business_fields_still_fail_definitely(mock_server):
    base_url, state, _ = mock_server(mode=MODE_OK)

    text = await call_tool(base_url, valid_args(invoiceId=None))

    # Rejected by the schema (wrong type) rather than by the handler's own
    # `required` check; either way it is definite and nothing was sent.
    assert ("required" in text) or ("validation error" in text.lower())
    assert "OUTCOME_UNKNOWN" not in text
    assert state.snapshot()["attempt_count"] == 0


async def test_reference_is_not_used_as_the_idempotency_key(mock_server):
    """The plan forbids repurposing `reference`. Prove they are separate."""
    base_url, state, _ = mock_server(mode=MODE_OK)

    await call_tool(base_url, valid_args(reference="SAME-REF",
                                         idempotencyKey="key-A"))
    await call_tool(base_url, valid_args(reference="SAME-REF",
                                         idempotencyKey="key-B"))

    # Identical reference, different keys -> two distinct operations.
    assert state.snapshot()["payment_count"] == 2
    keys = [a["idempotency_key"] for a in state.snapshot()["attempts"]]
    assert keys == ["key-A", "key-B"]

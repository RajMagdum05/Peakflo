"""
Unit tests for the ambiguous-vs-definite classifier (M3 review F-2).

The M3 reviewer's mutation campaign found that deleting the
`ConnectError`/`ConnectTimeout` early return from
`is_ambiguous_transport_outcome` broke **no test**: the end-to-end suite
cannot produce a connect error because the mock is always listening. That
carve-out is safety-critical and load-bearing, so it is pinned directly
here.

Why it is load-bearing: httpx's exception hierarchy means
``ConnectError`` is a subclass of ``NetworkError`` and ``ConnectTimeout``
is a subclass of ``TimeoutException``. Both would therefore be classified
ambiguous by the second branch. Only the ordering keeps them definite.

Getting this wrong in either direction is harmful:
  * definite reported as ambiguous -> the caller hesitates, and a payment
    that never happened goes unmade while someone investigates;
  * ambiguous reported as definite -> the caller retries blindly and may
    pay twice. That is the bug this whole project exists to prevent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

PFMCP = Path(__file__).resolve().parent.parent / "pfMCP"
if str(PFMCP) not in sys.path:
    sys.path.insert(0, str(PFMCP))

from src.servers.xero.main import (  # noqa: E402
    XERO_IDEMPOTENCY_MAX_KEY_LENGTH,
    XERO_IDEMPOTENCY_WINDOW_SECONDS,
    is_ambiguous_transport_outcome,
)


def http_error(status_code: int) -> Exception:
    """An exception shaped like the one call_xero_api raises for >=400."""
    exc = Exception(f"Xero API error (HTTP {status_code})")
    exc.status_code = status_code
    return exc


# ---------------------------------------------------- definite failures ---

@pytest.mark.parametrize("exc", [
    httpx.ConnectError("connection refused"),
    httpx.ConnectTimeout("timed out connecting"),
])
def test_connect_failures_are_definite_not_ambiguous(exc):
    """The request was never delivered, so no payment can have happened."""
    assert is_ambiguous_transport_outcome(exc) is False


def test_the_httpx_inheritance_trap_is_real():
    """Pin the inheritance that makes the ordering necessary.

    If httpx ever changed this, the early return would become redundant
    rather than load-bearing -- but while it holds, removing that return
    silently reclassifies connect failures as ambiguous.
    """
    assert issubclass(httpx.ConnectError, httpx.NetworkError)
    assert issubclass(httpx.ConnectTimeout, httpx.TimeoutException)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 429])
def test_4xx_is_definite(status):
    """Client errors are the server telling us it did NOT act."""
    assert is_ambiguous_transport_outcome(http_error(status)) is False


@pytest.mark.parametrize("exc", [
    ValueError("bad input"),
    KeyError("missing"),
    RuntimeError("something else"),
])
def test_unrelated_exceptions_are_definite(exc):
    """Anything we do not recognise must not be called ambiguous."""
    assert is_ambiguous_transport_outcome(exc) is False


def test_exception_without_status_code_is_definite():
    assert is_ambiguous_transport_outcome(Exception("no status")) is False


# -------------------------------------------------- ambiguous outcomes ---

@pytest.mark.parametrize("exc", [
    httpx.ReadTimeout("read timed out"),
    httpx.WriteTimeout("write timed out"),
    httpx.PoolTimeout("pool timed out"),
    httpx.RemoteProtocolError("server disconnected"),
    httpx.ReadError("read error"),
    httpx.WriteError("write error"),
])
def test_post_send_transport_failures_are_ambiguous(exc):
    """The request may have been delivered and acted on."""
    assert is_ambiguous_transport_outcome(exc) is True


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_is_ambiguous(status):
    """The server may well have committed before failing."""
    assert is_ambiguous_transport_outcome(http_error(status)) is True


@pytest.mark.parametrize("exc", [
    json.JSONDecodeError("bad json", "doc", 0),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"),
])
def test_unparseable_success_response_is_ambiguous(exc):
    """M3 review F-3.

    A 2xx whose body will not parse means the write almost certainly
    succeeded and we merely cannot read the confirmation. Calling that a
    definite failure is the dangerous direction.
    """
    assert is_ambiguous_transport_outcome(exc) is True


# ------------------------------------------- against a real closed port ---

async def test_real_connect_error_against_a_closed_port():
    """End-to-end proof, not a synthetic exception.

    The suite otherwise cannot generate a connect error, because the mock
    is always listening. Bind a socket, close it, and use the port.
    """
    import socket  # noqa: PLC0415

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    closed_port = sock.getsockname()[1]
    sock.close()

    with pytest.raises(httpx.ConnectError) as caught:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.put(f"http://127.0.0.1:{closed_port}/api.xro/2.0/Payments",
                             json={"Payments": []})

    assert is_ambiguous_transport_outcome(caught.value) is False


# ---------------------------------------------------- documented values ---

def test_documented_constants_match_official_xero_values():
    """These drive caller-facing guidance, so pin the literals."""
    assert XERO_IDEMPOTENCY_MAX_KEY_LENGTH == 128
    assert XERO_IDEMPOTENCY_WINDOW_SECONDS == 360

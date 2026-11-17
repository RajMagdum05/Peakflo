"""
M1 baseline mock — LOCAL SIMULATION ONLY. This is NOT Xero.

This is a deliberately minimal local HTTP server used by
``retry_dup_repro.py`` to reproduce the ambiguous-outcome retry problem
described in BUILD_PLAN_peakflo.md §2 and §10 (M1).

What it models
--------------
A payment-creation endpoint that keeps a local ledger, plus one fault
mode in which the server **commits the payment first and only then
becomes slow**, so the client's read timeout fires after the side effect
has already happened. That is the whole point: from the client's side the
outcome is genuinely unknown.

What it deliberately does NOT model
-----------------------------------
There is **no idempotency-key cache here**. This mock does not implement
Xero's ``Idempotency-Key`` contract, expiry, or conflict detection — that
is M2's job (BUILD_PLAN_peakflo.md §9, §10 M2). M1 exists only to show
the baseline behaviour *without* any protection. Any ``Idempotency-Key``
header sent to this server is recorded for the attempt log and otherwise
ignored.

Evidence boundary
-----------------
Results produced against this server demonstrate the behaviour of the
local client/mock pair only. They do not demonstrate how Xero behaves,
they do not demonstrate how Peakflo production behaves, and they are not
evidence of any real duplicate payment. No network call leaves
127.0.0.1.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# Fault modes.
MODE_OK = "ok"
MODE_COMMIT_THEN_SLOW = "commit_then_slow"
MODES = (MODE_OK, MODE_COMMIT_THEN_SLOW)

# The path the inspected pfMCP create_payment handler targets.
# Confirmed in inspected code: pfMCP src/servers/xero/main.py:3057-3063
# builds f"{ACCOUNTING_API}/Payments" where ACCOUNTING_API = "/api.xro/2.0".
PAYMENTS_PATH = "/api.xro/2.0/Payments"


class LedgerState:
    """In-memory ledger plus a full attempt log. Reset between scenarios."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.payments: list[dict[str, Any]] = []
        self.attempts: list[dict[str, Any]] = []

    def reset(self) -> None:
        with self._lock:
            self.payments.clear()
            self.attempts.clear()

    def record_attempt(self, entry: dict[str, Any]) -> int:
        with self._lock:
            # M1 review D-7: assign the index under the lock, so concurrent
            # attempts cannot be given the same attempt_index.
            entry["attempt_index"] = len(self.attempts) + 1
            self.attempts.append(entry)
            return len(self.attempts)

    def commit_payment(self, payload: dict[str, Any], method: str,
                       idempotency_key: str | None) -> dict[str, Any]:
        """Append one ledger entry. No de-duplication of any kind here."""
        with self._lock:
            entry = {
                "PaymentID": str(uuid.uuid4()),
                "committed_at": time.time(),
                "http_method": method,
                "idempotency_key": idempotency_key,
                "payload": payload,
            }
            self.payments.append(entry)
            return entry

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "payment_count": len(self.payments),
                "payments": list(self.payments),
                "attempt_count": len(self.attempts),
                "attempts": list(self.attempts),
            }


class _Handler(BaseHTTPRequestHandler):
    # Set by make_server().
    state: LedgerState
    mode: str
    delay_seconds: float

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D102
        # Keep the repro output readable; attempts are logged in the ledger.
        pass

    def handle_one_request(self) -> None:
        # M1 review D-5: a client that times out and aborts is the POINT of
        # this mock, not an error. Swallow the resulting connection errors
        # so they don't dump tracebacks into captured demo output.
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError,
                BrokenPipeError, TimeoutError):
            self.close_connection = True

    # -- helpers ---------------------------------------------------------
    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {"__unparsed_body__": repr(raw[:200])}

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- routes ----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/__ledger":
            self._send_json(200, self.state.snapshot())
            return
        self._send_json(404, {"error": f"no GET route {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/__reset":
            self.state.reset()
            self._send_json(200, {"reset": True})
            return
        self._handle_payment("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._handle_payment("PUT")

    def _handle_payment(self, method: str) -> None:
        """Accept a payment-creation request on either method.

        Both PUT and POST are accepted so the repro records which method
        the client actually used without the mock's own routing choice
        deciding the outcome. (The PUT-vs-POST contract question is
        BUILD_PLAN_peakflo.md §4.3 / M3 work, not M1 work.)
        """
        if not self.path.startswith(PAYMENTS_PATH):
            self._send_json(404, {"error": f"no {method} route {self.path}"})
            return

        body = self._read_body()
        idem = self.headers.get("Idempotency-Key")
        received_at = time.time()

        attempt_no = self.state.record_attempt({
            "http_method": method,
            "path": self.path,
            "idempotency_key": idem,
            "received_at": received_at,
            "body": body,
        })

        if self.mode == MODE_COMMIT_THEN_SLOW:
            # The side effect happens FIRST. Then the response is delayed
            # past the client's timeout. The client therefore cannot tell
            # whether this committed.
            committed = self.state.commit_payment(body, method, idem)
            time.sleep(self.delay_seconds)
            try:
                self._send_json(200, {"Payments": [committed], "__mock_mode__": self.mode})
            except (BrokenPipeError, ConnectionResetError, OSError):
                # Expected: the client already gave up and closed the socket.
                pass
            return

        # MODE_OK
        committed = self.state.commit_payment(body, method, idem)
        self._send_json(200, {
            "Payments": [committed],
            "__mock_mode__": self.mode,
            "__attempt_no__": attempt_no,
        })


class _QuietServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that treats an aborted client as normal.

    M1 review D-5: the ambiguous-timeout scenario deliberately makes the
    client hang up mid-response, which socketserver would otherwise report
    as an unhandled error with a full traceback.
    """

    def handle_error(self, request, client_address) -> None:
        import sys  # noqa: PLC0415
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError,
                            BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def make_server(mode: str = MODE_OK, delay_seconds: float = 7.0,
                port: int = 0) -> tuple[ThreadingHTTPServer, LedgerState, str]:
    """Create (but do not start) a mock server.

    Returns ``(server, state, base_url)``. ``port=0`` picks a free port.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")

    state = LedgerState()
    handler = type("_BoundHandler", (_Handler,), {
        "state": state,
        "mode": mode,
        "delay_seconds": delay_seconds,
    })
    server = _QuietServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    return server, state, base_url


def serve_in_thread(server: ThreadingHTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default=MODE_OK)
    parser.add_argument("--delay", type=float, default=7.0,
                        help="seconds to stall after committing (commit_then_slow)")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    server, _state, base_url = make_server(args.mode, args.delay, args.port)
    print(f"LOCAL SIMULATION (not Xero) listening on {base_url} mode={args.mode}")
    print(f"  payments:  PUT/POST {base_url}{PAYMENTS_PATH}")
    print(f"  ledger:    GET  {base_url}/__ledger")
    print(f"  reset:     POST {base_url}/__reset")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

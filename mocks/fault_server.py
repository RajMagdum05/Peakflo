"""
M2 fault-injection mock Xero API — LOCAL SIMULATION ONLY. This is NOT Xero.

Implements the subset of Xero's documented behaviour that the prototype
needs, plus deterministic fault injection, so retry behaviour can be
tested without touching any real system (BUILD_PLAN_peakflo.md §9, §10 M2).

No request ever leaves 127.0.0.1. There are no credentials here and
nothing in this file talks to Xero or Peakflo.

Modelled from official Xero documentation (re-verified 2026-11-16, see
BUILD_LOG.md M0 §6):

  * ``Idempotency-Key`` is honoured on mutating methods (POST/PUT/PATCH)
    and ignored on others.
  * Same key + same request  -> the original cached response is returned
    and the operation is NOT processed again.
  * Same key + different request -> HTTP 400,
    "Idempotency Key: {key} is used with a different request."
    A request differs if the URL, body, or HTTP method differs.
  * Key longer than 128 characters -> HTTP 400,
    "Idempotency Key: {key} with length {n} is too long."
  * Keys are retained 6 minutes, then expire. Replaying an EXPIRED key is
    NOT an error -- it is processed as a brand-new key. That is precisely
    why a caller still needs reconciliation and cannot treat the header
    as permanent protection.
  * An internal error is cached too, and is returned again on replay.
  * Xero applies no format validation to key values.

Deliberate simplifications (this is a simulation, not an emulator):
  * Only the ``/api.xro/2.0/Payments`` surface is modelled.
  * No OAuth, tenant isolation, rate limiting, or multicurrency logic.
  * Idempotency scope here is the whole server. Xero scopes key re-use
    per app; there is one notional app here.
  * The clock is injectable so expiry is testable instantly.

What results from this file prove: how THIS mock behaves. They do not
prove how Xero behaves, do not prove how Peakflo production behaves, and
are not evidence of any real duplicate payment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# --- fault modes -----------------------------------------------------------
MODE_OK = "ok"
MODE_COMMIT_THEN_SLOW = "commit_then_slow"
MODE_COMMIT_THEN_502 = "commit_then_502"
MODE_FAIL_BEFORE_COMMIT = "fail_before_commit"
MODES = (MODE_OK, MODE_COMMIT_THEN_SLOW, MODE_COMMIT_THEN_502,
         MODE_FAIL_BEFORE_COMMIT)

PAYMENTS_PATH = "/api.xro/2.0/Payments"

# Xero's documented values (official documentation, verified 2026-11-16).
XERO_IDEMPOTENCY_TTL_SECONDS = 360.0   # 6 minutes
XERO_MAX_KEY_LENGTH = 128

MUTATING_METHODS = ("POST", "PUT", "PATCH")

# How long a concurrent duplicate waits for the first caller's result
# before giving up. Must comfortably exceed the longest stall used in
# tests (7.0s) and must stay BELOW the test client's own timeout (30.0s),
# so a waiter that gives up produces a clean 503 rather than racing the
# client's timeout for which error the caller sees. (M4 review M4-5.)
INFLIGHT_WAIT_SECONDS = 20.0


def fingerprint_request(method: str, path: str, body: dict[str, Any]) -> str:
    """Identity of a request, per Xero's "different request" definition.

    Official documentation: "A different request is considered where any
    part of the endpoint URL, request body or HTTP method has changed."
    """
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(
        f"{method.upper()}|{path}|{canonical}".encode("utf-8")
    ).hexdigest()


def key_is_usable(key: str | None) -> bool:
    """Whether a supplied header value counts as an idempotency key here.

    M2 review C-2. Previously a plain ``if key:`` meant an empty string
    was silently indistinguishable from no header at all, so a caller
    sending ``Idempotency-Key: `` got no protection and no signal. Xero
    states it applies no validation and accepts any string, but an empty
    or whitespace-only header value is not a usable key, so this mock
    treats it as ABSENT and records that it did so. The tool itself
    rejects such keys outright before sending (see
    `validate_idempotency_key` in pfMCP).
    """
    return bool(key is not None and key.strip())


class CachedResult:
    """One stored idempotent outcome."""

    __slots__ = ("fingerprint", "status", "body", "stored_at", "payment_id")

    def __init__(self, fingerprint: str, status: int, body: dict[str, Any],
                 stored_at: float, payment_id: str | None) -> None:
        self.fingerprint = fingerprint
        self.status = status
        self.body = body
        self.stored_at = stored_at
        self.payment_id = payment_id


class InFlightOperation:
    """A key whose first request is still being processed.

    M2 review C-4. ``lookup -> commit -> store`` was not atomic per key,
    so two concurrent requests carrying the same key could both miss the
    cache and both commit, producing exactly the duplicate payment this
    project exists to prevent. The race was latent rather than
    demonstrated (480 concurrent requests gave one ledger row in 20/20
    trials), but "we could not make it happen" is not a guarantee.

    Xero documents the correct behaviour: "Concurrent requests, within
    the concurrency limit will be processed for idempotency. Once the
    first call is processed, the cached response will be returned for all
    remaining requests." So a second caller waits for the first and then
    receives its result.
    """

    __slots__ = ("fingerprint", "event", "result")

    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint
        self.event = threading.Event()
        self.result: CachedResult | None = None


class MockState:
    """Ledger + idempotency cache + attempt log, with an injectable clock."""

    def __init__(self, ttl_seconds: float = XERO_IDEMPOTENCY_TTL_SECONDS) -> None:
        self._lock = threading.RLock()
        self.ttl_seconds = ttl_seconds
        self._clock_offset = 0.0
        # TEST SUPPORT ONLY. An artificial pause inserted between claiming
        # an idempotency key and writing the ledger row, used to widen the
        # check-then-act window deterministically.
        #
        # Why this exists: the C-4 race is real but almost impossible to
        # observe naturally -- the window is only as wide as a dict write,
        # so 480 concurrent requests failed to trigger it, and removing the
        # reservation did not fail any concurrency test. Without a way to
        # force the interleaving, "the reservation is necessary" would be
        # an untestable claim. With it, removing the reservation reliably
        # produces duplicate payments. Defaults to 0.0 and is never set in
        # normal operation.
        self.commit_delay_seconds = 0.0
        self.payments: list[dict[str, Any]] = []
        self.attempts: list[dict[str, Any]] = []
        self.idempotency_cache: dict[str, CachedResult] = {}
        self.inflight: dict[str, InFlightOperation] = {}

    # -- clock ----------------------------------------------------------
    def now(self) -> float:
        return time.monotonic() + self._clock_offset

    def advance_clock(self, seconds: float) -> None:
        """Move the mock's clock forward so expiry is testable instantly."""
        with self._lock:
            self._clock_offset += seconds

    # -- lifecycle ------------------------------------------------------
    def reset(self, ttl_seconds: float | None = None) -> None:
        with self._lock:
            self.payments.clear()
            self.attempts.clear()
            self.idempotency_cache.clear()
            # Release anyone waiting, so a reset cannot hang a live request.
            for pending in self.inflight.values():
                pending.event.set()
            self.inflight.clear()
            self._clock_offset = 0.0
            if ttl_seconds is not None:
                self.ttl_seconds = ttl_seconds

    # -- recording ------------------------------------------------------
    def record_attempt(self, entry: dict[str, Any]) -> None:
        with self._lock:
            # D-7 (M1 review): index assigned under the lock, not outside it.
            entry["attempt_index"] = len(self.attempts) + 1
            self.attempts.append(entry)

    def commit_payment(self, body: dict[str, Any], method: str,
                       key: str | None) -> dict[str, Any]:
        with self._lock:
            entry = {
                "PaymentID": str(uuid.uuid4()),
                "committed_at": self.now(),
                "http_method": method,
                "idempotency_key": key,
                "request_body": body,
            }
            self.payments.append(entry)
            return entry

    # -- atomic per-key reservation (M2 review C-4) ----------------------
    # NOTE: the earlier non-atomic `lookup()` / `store()` pair was removed
    # in M4 once `begin_operation` / `finish_operation` replaced it. Keeping
    # them would have left a second, racy way to reach the same state.
    # (M4 review M4-9.)
    def begin_operation(self, key: str, fingerprint: str
                        ) -> tuple[str, Any]:
        """Claim a key, or report what is already happening to it.

        Done under one critical section so that the decision and the
        reservation cannot be interleaved. Returns one of:

        ``("replay", CachedResult)``  already completed; return it
        ``("conflict", None)``        same key, different request
        ``("wait", InFlightOperation)`` someone else owns it right now
        ``("own", InFlightOperation)``  caller must process and then call
                                        ``finish_operation``
        """
        with self._lock:
            cached = self.idempotency_cache.get(key)
            if cached is not None:
                if self.now() - cached.stored_at >= self.ttl_seconds:
                    del self.idempotency_cache[key]  # expired -> brand new
                elif cached.fingerprint != fingerprint:
                    return "conflict", None
                else:
                    return "replay", cached

            pending = self.inflight.get(key)
            if pending is not None:
                if pending.fingerprint != fingerprint:
                    return "conflict", None
                return "wait", pending

            owned = InFlightOperation(fingerprint)
            self.inflight[key] = owned
            return "own", owned

    def finish_operation(self, key: str, result: CachedResult | None) -> None:
        """Publish the outcome for a key and release any waiters."""
        with self._lock:
            pending = self.inflight.pop(key, None)
            if result is not None:
                self.idempotency_cache[key] = result
            if pending is not None:
                pending.result = result
                pending.event.set()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "payment_count": len(self.payments),
                "payments": list(self.payments),
                "attempt_count": len(self.attempts),
                "attempts": list(self.attempts),
                "idempotency_keys_cached": sorted(self.idempotency_cache),
                "ttl_seconds": self.ttl_seconds,
            }


class _Handler(BaseHTTPRequestHandler):
    state: MockState
    mode: str
    delay_seconds: float

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    # D-5 (M1 review): a client that times out and aborts mid-response is
    # EXPECTED here, not an error. Swallow the resulting connection errors
    # instead of letting Python dump a traceback into captured output.
    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, TimeoutError):
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

    def _send_json(self, status: int, payload: dict[str, Any]) -> bool:
        """Write a JSON response. Returns False if the client already left."""
        body = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return True
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
            self.close_connection = True
            return False

    def _path_only(self) -> str:
        return self.path.split("?", 1)[0]

    def _query(self) -> dict[str, str]:
        if "?" not in self.path:
            return {}
        from urllib.parse import parse_qs  # noqa: PLC0415
        raw = parse_qs(self.path.split("?", 1)[1])
        return {k: v[0] for k, v in raw.items() if v}

    # -- control plane ---------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self._path_only()
        if path == "/__ledger":
            self._send_json(200, self.state.snapshot())
            return
        if path == PAYMENTS_PATH:
            self._get_payments()
            return
        self._send_json(404, {"error": f"no GET route {path}"})

    def do_POST(self) -> None:  # noqa: N802
        path = self._path_only()
        if path == "/__reset":
            body = self._read_body()
            self.state.reset(ttl_seconds=body.get("ttl_seconds"))
            self._send_json(200, {"reset": True,
                                  "ttl_seconds": self.state.ttl_seconds})
            return
        if path == "/__advance_clock":
            body = self._read_body()
            seconds = float(body.get("seconds", 0))
            self.state.advance_clock(seconds)
            self._send_json(200, {"advanced_seconds": seconds})
            return
        if path == "/__mode":
            body = self._read_body()
            mode = body.get("mode")
            if mode not in MODES:
                self._send_json(400, {"error": f"unknown mode {mode!r}",
                                      "modes": list(MODES)})
                return
            type(self).mode = mode
            if "delay_seconds" in body:
                type(self).delay_seconds = float(body["delay_seconds"])
            self._send_json(200, {"mode": mode,
                                  "delay_seconds": type(self).delay_seconds})
            return
        self._mutating_payment("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._mutating_payment("PUT")

    def do_PATCH(self) -> None:  # noqa: N802
        self._mutating_payment("PATCH")

    # -- reconciliation read ---------------------------------------------
    def _get_payments(self) -> None:
        """Deterministic read endpoint used for reconciliation in tests.

        Supports ``?InvoiceID=`` and ``?Reference=`` exact-match filters.
        A GET is non-mutating, so any Idempotency-Key is ignored here --
        which is also what Xero documents.
        """
        query = self._query()
        with self.state._lock:  # noqa: SLF001 - same module, deliberate
            rows = list(self.state.payments)
        invoice_id = query.get("InvoiceID")
        reference = query.get("Reference")

        def matches(row: dict[str, Any]) -> bool:
            payment = (row.get("request_body", {}).get("Payments") or [{}])[0]
            if invoice_id and payment.get("Invoice", {}).get("InvoiceID") != invoice_id:
                return False
            if reference and payment.get("Reference") != reference:
                return False
            return True

        found = [r for r in rows if matches(r)]
        self.state.record_attempt({
            "http_method": "GET",
            "path": self.path,
            "idempotency_key": self.headers.get("Idempotency-Key"),
            "received_at": self.state.now(),
            "outcome": "READ",
            "matched": len(found),
        })
        self._send_json(200, {"Payments": found, "__mock__": True})

    # -- mutating payment path -------------------------------------------
    def _mutating_payment(self, method: str) -> None:
        path = self._path_only()
        if path != PAYMENTS_PATH:
            self._send_json(404, {"error": f"no {method} route {path}"})
            return

        body = self._read_body()
        raw_key = self.headers.get("Idempotency-Key")
        # C-2: an empty or whitespace-only header value is not a usable key.
        key = raw_key if key_is_usable(raw_key) else None
        fingerprint = fingerprint_request(method, path, body)
        attempt: dict[str, Any] = {
            "http_method": method,
            "path": path,
            "idempotency_key": key,
            "raw_idempotency_key": raw_key,
            "key_treated_as_absent": raw_key is not None and key is None,
            "request_fingerprint": fingerprint,
            "received_at": self.state.now(),
            "mode": self.mode,
        }

        # --- key validation (Xero returns 400 for an over-long key) ------
        # M2 review C-8: the MUTATING_METHODS test is always true for the
        # current callers (do_POST/do_PUT/do_PATCH). It is kept deliberately
        # as an executable statement of the rule -- Xero honours the header
        # only on mutating methods -- so that adding a non-mutating caller
        # later cannot silently start consuming idempotency keys.
        if key is not None and method.upper() in MUTATING_METHODS:
            if len(key) > XERO_MAX_KEY_LENGTH:
                attempt["outcome"] = "KEY_TOO_LONG"
                self.state.record_attempt(attempt)
                self._send_json(400, {
                    "Message": (f"Idempotency Key: {key} with length "
                                f"{len(key)} is too long."),
                    "__mock__": True,
                })
                return

            action, holder = self.state.begin_operation(key, fingerprint)
            attempt["reservation"] = action

            if action == "conflict":
                # Same key, different request -> 400, nothing committed.
                attempt["outcome"] = "KEY_CONFLICT"
                self.state.record_attempt(attempt)
                self._send_json(400, {
                    "Message": (f"Idempotency Key: {key} is used with a "
                                f"different request."),
                    "__mock__": True,
                })
                return

            if action == "replay":
                # Same key, same request -> replay. No second commit, and a
                # cached error stays an error (Xero documents both).
                attempt["outcome"] = "REPLAY"
                attempt["replayed_payment_id"] = holder.payment_id
                self.state.record_attempt(attempt)
                self._send_replay(holder)
                return

            if action == "wait":
                # C-4: a concurrent duplicate waits for the first caller's
                # result instead of racing it into a second commit.
                attempt["outcome"] = "WAITED_FOR_INFLIGHT"
                self.state.record_attempt(attempt)
                if holder.event.wait(timeout=INFLIGHT_WAIT_SECONDS) and holder.result:
                    self._send_replay(holder.result)
                else:
                    self._send_json(503, {
                        "Message": ("Mock: the first request with this "
                                    "idempotency key has not completed."),
                        "__mock__": True,
                    })
                return

            # action == "own": this request must process it and MUST
            # publish an outcome, or waiters would hang.
            try:
                self._process(method, body, key, fingerprint, attempt)
            except BaseException:
                self.state.finish_operation(key, None)
                raise
            return

        # No usable key: no protection at all.
        self._process(method, body, key, fingerprint, attempt)

    def _send_replay(self, cached: CachedResult) -> None:
        replay = dict(cached.body)
        replay["__replayed_from_idempotency_cache__"] = True
        self._send_json(cached.status, replay)

    def _process(self, method: str, body: dict[str, Any], key: str | None,
                 fingerprint: str, attempt: dict[str, Any]) -> None:
        """Apply the current fault mode, publish the outcome, then respond.

        The outcome is published BEFORE any artificial stall, so that a
        concurrent duplicate is released as soon as the result exists
        rather than waiting out the full delay. Xero documents the same:
        "Once the first call is processed, the cached response will be
        returned for all remaining requests."
        """
        now = self.state.now()

        if self.mode == MODE_FAIL_BEFORE_COMMIT:
            attempt["outcome"] = "FAIL_BEFORE_COMMIT"
            self.state.record_attempt(attempt)
            status, payload = 500, {
                "Message": "Mock internal error before ledger write.",
                "__mock__": True,
            }
            # Xero caches internal errors too.
            cached = CachedResult(fingerprint, status, payload, now, None)
            if key:
                self.state.finish_operation(key, cached)
            self._send_json(status, payload)
            return

        # Test-support widening of the check-then-act window (see
        # MockState.commit_delay_seconds). 0.0 in normal operation.
        if self.state.commit_delay_seconds:
            time.sleep(self.state.commit_delay_seconds)

        committed = self.state.commit_payment(body, method, key)
        attempt["committed_payment_id"] = committed["PaymentID"]
        success_payload = {"Payments": [committed], "__mock__": True,
                           "__mock_mode__": self.mode}
        cached = CachedResult(fingerprint, 200, success_payload, now,
                              committed["PaymentID"])

        if self.mode == MODE_COMMIT_THEN_502:
            # Committed, then the gateway swallows the response. Ambiguous
            # to the caller unless it reconciles.
            attempt["outcome"] = "COMMIT_THEN_502"
            self.state.record_attempt(attempt)
            if key:
                self.state.finish_operation(key, cached)
            self._send_json(502, {"Message": "Mock gateway error after commit.",
                                  "__mock__": True})
            return

        if self.mode == MODE_COMMIT_THEN_SLOW:
            attempt["outcome"] = "COMMIT_THEN_SLOW"
            self.state.record_attempt(attempt)
            if key:
                self.state.finish_operation(key, cached)
            time.sleep(self.delay_seconds)
            self._send_json(200, success_payload)
            return

        attempt["outcome"] = "OK"
        self.state.record_attempt(attempt)
        if key:
            self.state.finish_operation(key, cached)
        self._send_json(200, success_payload)


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        # D-5: aborted clients are the point of this mock, not a failure.
        import sys  # noqa: PLC0415
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError,
                            BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def make_server(mode: str = MODE_OK, delay_seconds: float = 7.0,
                port: int = 0,
                ttl_seconds: float = XERO_IDEMPOTENCY_TTL_SECONDS
                ) -> tuple[_Server, MockState, str]:
    """Create (not start) a mock server. ``port=0`` picks a free port."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    state = MockState(ttl_seconds=ttl_seconds)
    handler = type("_BoundHandler", (_Handler,), {
        "state": state, "mode": mode, "delay_seconds": delay_seconds,
    })
    server = _Server(("127.0.0.1", port), handler)
    return server, state, f"http://127.0.0.1:{server.server_address[1]}"


def serve_in_thread(server: _Server) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def main() -> None:
    parser = argparse.ArgumentParser(description="LOCAL SIMULATION of a Xero-like payments API")
    parser.add_argument("--mode", choices=MODES, default=MODE_OK)
    parser.add_argument("--delay", type=float, default=7.0)
    parser.add_argument("--ttl", type=float, default=XERO_IDEMPOTENCY_TTL_SECONDS)
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()

    server, _state, base_url = make_server(args.mode, args.delay, args.port, args.ttl)
    print(f"LOCAL SIMULATION (not Xero) on {base_url}  mode={args.mode}  ttl={args.ttl}s")
    print(f"  create : PUT/POST {base_url}{PAYMENTS_PATH}  [Idempotency-Key honoured]")
    print(f"  read   : GET      {base_url}{PAYMENTS_PATH}?InvoiceID=...&Reference=...")
    print(f"  ledger : GET      {base_url}/__ledger")
    print(f"  reset  : POST     {base_url}/__reset           {{\"ttl_seconds\": n}}")
    print(f"  clock  : POST     {base_url}/__advance_clock   {{\"seconds\": n}}")
    print(f"  mode   : POST     {base_url}/__mode            {{\"mode\": \"...\"}}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

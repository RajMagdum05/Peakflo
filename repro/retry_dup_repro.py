"""
M1 baseline reproduction — LOCAL SIMULATION ONLY.

Question this script answers (BUILD_PLAN_peakflo.md §2, §10 M1):

    When a payment-creation request commits on the server but the
    response is lost to a client timeout, and the caller then retries
    **as a new operation with no stable idempotency key** — which is what
    the inspected pfMCP ``create_payment`` path does today — can one
    intended payment become two ledger entries?

How it answers it
-----------------
Two scenarios, both against ``baseline_mock.py`` on 127.0.0.1:

  * ``control_ok``          — mock returns promptly. One logical
                              operation, one attempt, expect 1 ledger row.
  * ``baseline_timeout_retry`` — mock commits then stalls past the
                              client's timeout. The client sees an
                              ambiguous failure and retries the same
                              logical payment. Ledger rows are counted.

Client under test
-----------------
``--client pfmcp`` (default) drives **pfMCP's own** ``call_xero_api()``
helper, imported unmodified from the checkout, with only the module-level
``XERO_API_BASE`` redirected at the local mock. Nothing in the pfMCP
source tree is edited. The request shape is the one the inspected
``create_payment`` handler builds (pfMCP src/servers/xero/main.py:3047-3063).

``--client isolated`` uses a plain httpx request of the same shape, for
environments where the pfMCP package cannot be imported.

Evidence boundary — read before quoting any number from this script
-------------------------------------------------------------------
This demonstrates the behaviour of **this local client/mock pair only**.
It is not evidence that Xero behaves this way, not evidence that Peakflo
production behaves this way, and not evidence that any real duplicate
payment has ever occurred anywhere. No request leaves 127.0.0.1 and no
real credential, account, or payment is involved.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from baseline_mock import (
    MODE_COMMIT_THEN_SLOW,
    MODE_OK,
    PAYMENTS_PATH,
    make_server,
    serve_in_thread,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PFMCP = REPO_ROOT / "pfMCP"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# The payment the agent intends to make — ONE logical operation.
INTENDED_PAYMENT = {
    "invoiceId": "11111111-1111-1111-1111-111111111111",
    "accountId": "22222222-2222-2222-2222-222222222222",
    "amount": 1000.00,
    "date": "2026-11-16",
    "reference": "INV-DEMO-001",
}


def assert_loopback(base_url: str) -> None:
    """Refuse to run against anything that is not 127.0.0.1 / localhost.

    M1 review D-4. This is a safety gate, not a convenience check: every
    client path in this file must pass through it before issuing a
    payment-creation request.
    """
    from urllib.parse import urlparse  # noqa: PLC0415

    host = urlparse(base_url).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(
            f"REFUSING TO RUN: base_url {base_url!r} is not loopback. "
            "This script may only ever talk to a local mock."
        )


def client_read_timeout_seconds() -> float:
    """The read timeout the clients will actually use.

    Neither this script nor pfMCP's call_xero_api passes ``timeout=``, so
    both inherit httpx's default. M1 review D-1: read it rather than
    assuming 5.0, so the margin check below stays true if the default
    ever changes.
    """
    timeout = httpx.AsyncClient().timeout
    return float(timeout.read if timeout.read is not None else 5.0)


def build_payment_payload(args: dict[str, Any]) -> dict[str, Any]:
    """Mirror of the inspected pfMCP create_payment payload construction.

    Confirmed in inspected code: pfMCP src/servers/xero/main.py:3047-3055.
    Reproduced here (not imported) because that code lives inside the tool
    dispatcher and cannot be called without a full MCP server + credential
    resolver. The shape is copied verbatim.
    """
    payment = {
        "Invoice": {"InvoiceID": args["invoiceId"]},
        "Account": {"AccountID": args["accountId"]},
        "Amount": args["amount"],
        "Date": args["date"],
    }
    if args.get("reference"):
        payment["Reference"] = args["reference"]
    return {"Payments": [payment]}


# --------------------------------------------------------------------------
# Clients
# --------------------------------------------------------------------------

async def _attempt_pfmcp(base_url: str, pfmcp_path: Path) -> dict[str, Any]:
    """One attempt through pfMCP's real call_xero_api()."""
    sys.path.insert(0, str(pfmcp_path))
    from src.servers.xero import main as xero_main  # noqa: PLC0415

    # M1 review D-4: hard safety assertion. This function mutates a module
    # global that otherwise points at the real Xero API, so refuse outright
    # unless the replacement is loopback. Without this, a bad base_url would
    # silently send a payment request to a real host.
    assert_loopback(base_url)

    original_base = xero_main.XERO_API_BASE
    xero_main.XERO_API_BASE = base_url
    started = time.monotonic()
    try:
        result = await xero_main.call_xero_api(
            f"{xero_main.ACCOUNTING_API}/Payments",
            access_token="fake-local-token-not-a-secret",
            tenant_id="fake-local-tenant",
            method="POST",  # current inspected behaviour; see BUILD_LOG M0 §6
            data=build_payment_payload(INTENDED_PAYMENT),
        )
        return {
            "outcome": "SUCCESS",
            "elapsed_s": round(time.monotonic() - started, 3),
            "response": result,
            "tool_would_return": json.dumps(result)[:200],
        }
    except Exception as exc:  # noqa: BLE001 - mirrors main.py:4258
        # This mirrors the inspected dispatcher's catch-all at
        # pfMCP src/servers/xero/main.py:4258-4260, which turns ANY
        # exception into the string f"Error: {str(e)}".
        return {
            "outcome": "EXCEPTION",
            "elapsed_s": round(time.monotonic() - started, 3),
            "exception_type": type(exc).__name__,
            "exception_str": str(exc),
            "tool_would_return": f"Error: {exc}",
        }
    finally:
        xero_main.XERO_API_BASE = original_base


async def _attempt_isolated(base_url: str, _pfmcp_path: Path) -> dict[str, Any]:
    """One attempt through a plain httpx client of the same shape."""
    assert_loopback(base_url)  # M1 review D-4
    started = time.monotonic()
    headers = {
        "Authorization": "Bearer fake-local-token-not-a-secret",
        "xero-tenant-id": "fake-local-tenant",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}{PAYMENTS_PATH}",
                headers=headers,
                json=build_payment_payload(INTENDED_PAYMENT),
            )
            response.raise_for_status()
            return {
                "outcome": "SUCCESS",
                "elapsed_s": round(time.monotonic() - started, 3),
                "response": response.json(),
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "outcome": "EXCEPTION",
            "elapsed_s": round(time.monotonic() - started, 3),
            "exception_type": type(exc).__name__,
            "exception_str": str(exc),
            "tool_would_return": f"Error: {exc}",
        }


CLIENTS = {"pfmcp": _attempt_pfmcp, "isolated": _attempt_isolated}


# --------------------------------------------------------------------------
# Scenarios
# --------------------------------------------------------------------------

async def run_scenario(name: str, mode: str, attempts: int, delay: float,
                       client: str, pfmcp_path: Path) -> dict[str, Any]:
    """Run one scenario end to end against a freshly started mock."""
    server, state, base_url = make_server(mode=mode, delay_seconds=delay)
    serve_in_thread(server)
    attempt_fn = CLIENTS[client]

    print(f"\n=== scenario: {name} ===")
    print(f"    mock mode   : {mode} (LOCAL SIMULATION, not Xero)")
    print(f"    mock url    : {base_url}")
    print(f"    client      : {client}")
    print(f"    retry policy: new operation each attempt, NO stable key")

    records: list[dict[str, Any]] = []
    try:
        for i in range(1, attempts + 1):
            # BASELINE BEHAVIOUR UNDER TEST: each attempt is issued as a
            # brand-new operation. No idempotency key is generated, stored,
            # or reused -- matching the inspected create_payment path, which
            # passes no extra_headers at all (main.py:3057-3063).
            record = await attempt_fn(base_url, pfmcp_path)
            record["attempt"] = i
            records.append(record)
            print(f"    attempt {i}: {record['outcome']}"
                  f" after {record['elapsed_s']}s"
                  + (f" ({record['exception_type']}: "
                     f"{record.get('exception_str','')!r})"
                     if record["outcome"] == "EXCEPTION" else ""))
            if record["outcome"] == "SUCCESS":
                print("      -> caller got a definite answer; stopping retries")
                break
            print("      -> caller cannot tell if the payment happened; retrying")

        ledger = state.snapshot()
    finally:
        server.shutdown()
        server.server_close()

    intended_operations = 1
    committed = ledger["payment_count"]
    print(f"    ATTEMPTS MADE           : {len(records)}")
    print(f"    INTENDED OPERATIONS     : {intended_operations}")
    print(f"    LEDGER ENTRIES COMMITTED: {committed}")
    print(f"    DUPLICATE ENTRIES       : {max(0, committed - intended_operations)}")
    print(f"    IDEMPOTENCY KEYS SEEN   : "
          f"{[a['idempotency_key'] for a in ledger['attempts']]}")

    return {
        "scenario": name,
        "mock_mode": mode,
        "client": client,
        "intended_operations": intended_operations,
        "attempts_made": len(records),
        "ledger_entries_committed": committed,
        "duplicate_entries": max(0, committed - intended_operations),
        "idempotency_keys_seen": [a["idempotency_key"] for a in ledger["attempts"]],
        "attempt_records": records,
        "ledger": ledger,
    }


async def main_async(args: argparse.Namespace) -> int:
    pfmcp_path = Path(args.pfmcp).resolve()
    if args.client == "pfmcp" and not (pfmcp_path / "src" / "servers" / "xero" / "main.py").exists():
        print(f"ERROR: pfMCP checkout not found at {pfmcp_path}", file=sys.stderr)
        print("       pass --pfmcp <path> or use --client isolated", file=sys.stderr)
        return 2

    print("=" * 72)
    print("M1 BASELINE REPRODUCTION -- LOCAL SIMULATION ONLY, NOT XERO")
    print("No real Xero or Peakflo endpoint is contacted. No real payment.")
    print("=" * 72)

    # M1 review D-1: the whole result hinges on the mock stalling LONGER
    # than the client is willing to wait. Both numbers were previously
    # implicit. Compare them explicitly and refuse to produce a misleading
    # "not reproduced" result from a mis-set delay.
    read_timeout = client_read_timeout_seconds()
    margin = args.delay - read_timeout
    print(f"client read timeout : {read_timeout}s (httpx default, not set by us)")
    print(f"mock stall          : {args.delay}s   (margin {margin:+.1f}s)")
    if margin < 1.0:
        print("\nERROR: the mock stall must exceed the client read timeout by at",
              file=sys.stderr)
        print(f"       least 1.0s, but the margin is {margin:+.1f}s. With this",
              file=sys.stderr)
        print("       setting the client would NOT time out and the scenario",
              file=sys.stderr)
        print("       would be meaningless. Raise --delay or lower the timeout.",
              file=sys.stderr)
        return 3

    results = [
        await run_scenario("control_ok", MODE_OK, 1, args.delay, args.client, pfmcp_path),
        await run_scenario("baseline_timeout_retry", MODE_COMMIT_THEN_SLOW,
                           args.attempts, args.delay, args.client, pfmcp_path),
    ]

    baseline = results[1]
    print("\n" + "=" * 72)
    print("SUMMARY (local simulation)")
    print("=" * 72)
    print(f"{'scenario':<26}{'attempts':>9}{'committed':>11}{'duplicates':>12}")
    for r in results:
        print(f"{r['scenario']:<26}{r['attempts_made']:>9}"
              f"{r['ledger_entries_committed']:>11}{r['duplicate_entries']:>12}")

    reproduced = baseline["duplicate_entries"] > 0
    print(f"\nDuplicate effect reproduced in this local setup: {reproduced}")
    print("What this shows   : with no stable idempotency key, a retry after an")
    print("                    ambiguous timeout committed an extra ledger entry")
    print("                    in THIS mock.")
    print("What it does NOT  : it does not show that Xero or Peakflo production")
    print("                    behaves this way, and it is not evidence of any")
    print("                    real duplicate payment.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {
        "label": "LOCAL SIMULATION - mock server on 127.0.0.1, not Xero",
        "milestone": "M1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "duplicate_effect_reproduced": reproduced,
        "client_under_test": args.client,
        "mock_delay_seconds": args.delay,
        "max_attempts": args.attempts,
        # M1 review D-3: record exactly how this run was invoked, so a file
        # can never be mistaken for a differently-configured run.
        "invocation": {
            "argv": sys.argv[1:],
            "client_read_timeout_seconds": read_timeout,
            "stall_margin_seconds": round(margin, 3),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "httpx": httpx.__version__,
            "httpx_default_timeout": str(httpx.AsyncClient().timeout),
        },
        "scenarios": results,
    }
    serialized = json.dumps(out, indent=2, default=str)
    path = RESULTS_DIR / f"m1_baseline_{stamp}.json"
    path.write_text(serialized, encoding="utf-8")
    print(f"\nSaved: {path}")

    # M1 review D-3: previously EVERY run overwrote *_latest.json, so an
    # exploratory run with odd settings could silently replace the
    # headline evidence. Only a canonical run may claim that name.
    canonical = (args.client == "pfmcp" and args.attempts == 2
                 and margin >= 1.0)
    out["canonical_run"] = canonical
    if canonical:
        latest = RESULTS_DIR / "m1_baseline_latest.json"
        latest.write_text(json.dumps(out, indent=2, default=str),
                          encoding="utf-8")
        print(f"Saved: {latest}  (canonical run)")
    else:
        print("NOT updating m1_baseline_latest.json: this was a non-canonical")
        print(f"  run (client={args.client}, attempts={args.attempts},"
              f" margin={margin:+.1f}s). The timestamped file above holds it.")

    # M1 review D-2: a run that reproduces nothing must not look like success.
    if not reproduced:
        print("\nEXIT 1: the duplicate effect was NOT reproduced in this run.",
              file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=sorted(CLIENTS), default="pfmcp")
    parser.add_argument("--pfmcp", default=str(DEFAULT_PFMCP),
                        help="path to the pfMCP checkout")
    parser.add_argument("--attempts", type=int, default=2,
                        help="max attempts for the ambiguous scenario")
    parser.add_argument("--delay", type=float, default=7.0,
                        help="mock stall in seconds (must exceed client timeout)")
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parent)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

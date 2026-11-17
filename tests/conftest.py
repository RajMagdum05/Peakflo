"""Shared fixtures for the prototype's own tests (not pfMCP's test suite)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mocks.fault_server import (  # noqa: E402
    MODE_OK,
    make_server,
    serve_in_thread,
)


@pytest.fixture
def mock_server():
    """Factory for a running mock. Each test gets a fresh server and state.

    Usage::

        base_url, state, set_mode = mock_server(mode=..., ttl_seconds=...)
    """
    created = []

    def _factory(mode: str = MODE_OK, delay_seconds: float = 0.5,
                 ttl_seconds: float = 360.0):
        server, state, base_url = make_server(
            mode=mode, delay_seconds=delay_seconds, ttl_seconds=ttl_seconds)
        serve_in_thread(server)
        created.append(server)

        def set_mode(new_mode: str, new_delay: float | None = None) -> None:
            handler_cls = server.RequestHandlerClass
            handler_cls.mode = new_mode
            if new_delay is not None:
                handler_cls.delay_seconds = new_delay

        return base_url, state, set_mode

    yield _factory

    for server in created:
        server.shutdown()
        server.server_close()

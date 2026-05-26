"""Regression guard: anyio lock cleanup race must not burn reconnect retries (#31987).

anyio raises RuntimeError("The current task is not holding this lock") as part
of normal streamable_http_client teardown when the cancel-scope cleans up its
internal lock in a different task from the one that acquired it.  This is an
expected race — not a genuine connection failure.

Before the fix, this exception fell through to the retry counter, which meant
5 normal session closes would permanently disconnect the MCP server.

The fix: detect the specific RuntimeError message and, if the server was
previously healthy (_ready is set), skip incrementing the retry counter and
continue the loop immediately.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch


_ANYIO_LOCK_EXC = RuntimeError("The current task is not holding this lock")


async def _instant_sleep(*args, **kwargs):
    """Async no-op drop-in for asyncio.sleep."""


class TestAnyioLockCleanupNotCounted:
    """The anyio lock cleanup error must not increment the reconnect retry counter."""

    def test_retry_count_stays_zero_on_anyio_lock_error(self):
        """Six consecutive anyio lock errors after a healthy connect -> counter stays 0."""
        from tools.mcp_tool import MCPServerTask

        server = MCPServerTask("lock-test")
        call_count = 0
        shutdown_after = 6

        async def _run():
            nonlocal call_count

            async def fake_run_http(self_inner, config):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # First call: succeed and set ready so subsequent cleanup
                    # errors hit the post-ready branch.
                    self_inner._ready.set()
                    return  # clean return (like a reconnect-event path)
                if call_count <= shutdown_after:
                    raise _ANYIO_LOCK_EXC
                # After shutdown_after cleanups, signal shutdown and return.
                self_inner._shutdown_event.set()

            with patch.object(MCPServerTask, "_run_http", fake_run_http), \
                 patch.object(MCPServerTask, "_is_http", lambda self: True):
                task = asyncio.ensure_future(server.run({"url": "http://fake"}))
                # Wait for the task to process all lock errors and exit.
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    server._shutdown_event.set()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except Exception:
                        pass

        asyncio.run(_run())

        # retries (the post-ready counter) must never have been incremented.
        # We infer this by checking the server didn't give up (no _error set).
        assert server._error is None, (
            f"Server error was set unexpectedly: {server._error} — "
            f"anyio lock cleanup race incorrectly counted as failure (#31987)"
        )

    def test_genuine_error_still_counts(self):
        """A real connection error (not the anyio lock race) still increments retries."""
        from tools.mcp_tool import MCPServerTask, _MAX_RECONNECT_RETRIES

        server = MCPServerTask("genuine-error-test")
        call_count = 0

        async def _run():
            nonlocal call_count

            async def fake_run_http(self_inner, config):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # First call: succeed and set ready.
                    self_inner._ready.set()
                    return
                # Subsequent calls: raise a genuine connection error.
                raise ConnectionResetError("server reset")

            with patch.object(MCPServerTask, "_run_http", fake_run_http), \
                 patch.object(MCPServerTask, "_is_http", lambda self: True), \
                 patch("asyncio.sleep", side_effect=_instant_sleep):
                task = asyncio.ensure_future(server.run({"url": "http://fake"}))
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    server._shutdown_event.set()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except Exception:
                        pass

        asyncio.run(_run())

        # After _MAX_RECONNECT_RETRIES genuine errors, the server gives up.
        # call_count = 1 (initial success) + _MAX_RECONNECT_RETRIES + 1 (give-up call).
        assert call_count >= _MAX_RECONNECT_RETRIES + 1, (
            f"Expected >= {_MAX_RECONNECT_RETRIES + 1} calls, got {call_count} — "
            f"genuine errors should still be counted"
        )

    def test_anyio_lock_error_before_ready_still_counts(self):
        """Before server is ready, even the anyio lock error is a real failure."""
        from tools.mcp_tool import MCPServerTask

        server = MCPServerTask("pre-ready-lock-test")

        async def _run():
            async def fake_run_http(self_inner, config):
                # Raise the lock error BEFORE _ready is ever set.
                raise _ANYIO_LOCK_EXC

            # Patch asyncio.sleep so the initial-connect backoff doesn't stall
            # the test suite for tens of seconds (1+2+4+8+16s = 31s otherwise).
            with patch.object(MCPServerTask, "_run_http", fake_run_http), \
                 patch.object(MCPServerTask, "_is_http", lambda self: True), \
                 patch("asyncio.sleep", side_effect=_instant_sleep):
                task = asyncio.ensure_future(server.run({"url": "http://fake"}))
                await server._ready.wait()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    server._shutdown_event.set()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except Exception:
                        pass

        asyncio.run(_run())

        # The error must propagate to _error (initial-connect failure path).
        assert server._error is not None, (
            "Pre-ready anyio lock error must be treated as initial connect "
            "failure, not silently skipped"
        )
        assert "not holding this lock" in str(server._error)

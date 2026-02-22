"""Tests for the persistent background event loop (EventLoopManager)."""

import asyncio
import pytest
import threading
import time
from lamia.async_bridge import EventLoopManager


class TestEventLoopManager:
    """Core functionality of EventLoopManager."""

    def setup_method(self):
        EventLoopManager.shutdown()

    def teardown_method(self):
        EventLoopManager.shutdown()

    def test_get_loop_returns_running_loop(self):
        loop = EventLoopManager.get_loop()
        assert loop is not None
        assert loop.is_running()
        assert not loop.is_closed()

    def test_get_loop_returns_same_loop(self):
        loop1 = EventLoopManager.get_loop()
        loop2 = EventLoopManager.get_loop()
        assert loop1 is loop2

    def test_run_coroutine_returns_value(self):
        async def add(a, b):
            return a + b

        result = EventLoopManager.run_coroutine(add(2, 3))
        assert result == 5

    def test_run_coroutine_propagates_exception(self):
        async def fail():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            EventLoopManager.run_coroutine(fail())

    def test_run_coroutine_supports_await(self):
        async def inner():
            await asyncio.sleep(0.01)
            return 42

        assert EventLoopManager.run_coroutine(inner()) == 42

    def test_multiple_sequential_coroutines_share_loop(self):
        loop_ids = []

        async def capture_loop():
            loop_ids.append(id(asyncio.get_running_loop()))

        EventLoopManager.run_coroutine(capture_loop())
        EventLoopManager.run_coroutine(capture_loop())
        EventLoopManager.run_coroutine(capture_loop())

        assert len(set(loop_ids)) == 1

    def test_shutdown_is_idempotent(self):
        EventLoopManager.get_loop()
        EventLoopManager.shutdown()
        EventLoopManager.shutdown()

    def test_loop_recreated_after_shutdown(self):
        loop1 = EventLoopManager.get_loop()
        EventLoopManager.shutdown()
        loop2 = EventLoopManager.get_loop()
        assert loop1 is not loop2
        assert loop2.is_running()

    def test_run_coroutine_after_shutdown_and_recreate(self):
        async def greet():
            return "hello"

        assert EventLoopManager.run_coroutine(greet()) == "hello"
        EventLoopManager.shutdown()
        assert EventLoopManager.run_coroutine(greet()) == "hello"

    def test_loop_runs_in_daemon_thread(self):
        EventLoopManager.get_loop()
        assert EventLoopManager._thread is not None
        assert EventLoopManager._thread.daemon is True
        assert EventLoopManager._thread.name == "lamia-event-loop"

    def test_cached_async_resource_survives_across_calls(self):
        """Simulates the LLM adapter caching scenario: an async resource created
        in one coroutine is reusable in a subsequent coroutine."""
        shared_state = {}

        async def create_resource():
            shared_state["session"] = {"id": id(asyncio.get_running_loop()), "active": True}

        async def use_resource():
            loop_id = id(asyncio.get_running_loop())
            assert shared_state["session"]["id"] == loop_id
            assert shared_state["session"]["active"] is True
            return "ok"

        EventLoopManager.run_coroutine(create_resource())
        result = EventLoopManager.run_coroutine(use_resource())
        assert result == "ok"

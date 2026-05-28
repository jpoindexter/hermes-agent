"""Regression guard: session-reuse liveness probe evicts dead env (#32460).

Before the fix, reusing a cached SSH/Docker/Modal environment that had become
unresponsive caused a silent 50-65s hang — the agent blocked on execute() until
an underlying OS or network timeout fired with no log output.

After the fix, a 5s liveness probe runs before execute() on all non-local reused
environments. If the probe times out or the sentinel is absent, the env is evicted
from _active_environments and a fresh one is created.

These tests verify:
1. A responsive cached env passes the probe and is reused (no fresh creation).
2. An unresponsive cached env fails the probe, is evicted, and a fresh env is created.
3. The probe is skipped entirely for env_type=="local" (spawn-per-call, never stale).
"""
from __future__ import annotations

import json
import threading
import time

import pytest

import tools.terminal_tool as tt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _AliveEnv:
    """Fake env whose execute() returns immediately with the probe sentinel."""
    env = {}
    calls: list

    def __init__(self):
        self.calls = []

    def execute(self, command, **kwargs):
        self.calls.append(command)
        return {"output": f"__HERMES_PROBE__\n{command}", "returncode": 0}

    def cleanup(self):
        pass


class _DeadEnv:
    """Fake env whose execute() blocks indefinitely (simulates dead SSH/Docker)."""
    env = {}
    cleanup_called: bool

    def __init__(self):
        self.cleanup_called = False

    def execute(self, command, **kwargs):
        # Block until the test is done — simulates a hung remote call.
        time.sleep(300)  # far longer than the 5s probe timeout
        return {"output": "", "returncode": 1}

    def cleanup(self):
        self.cleanup_called = True


class _FreshEnv:
    """Fake env returned by the environment factory after eviction."""
    env = {}
    calls: list

    def __init__(self):
        self.calls = []

    def execute(self, command, **kwargs):
        self.calls.append(command)
        return {"output": "fresh_env_result", "returncode": 0}

    def cleanup(self):
        pass


# ---------------------------------------------------------------------------
# Tests: _env_is_alive unit tests
# ---------------------------------------------------------------------------

class TestEnvIsAlive:
    def test_alive_env_returns_true(self):
        """_env_is_alive returns True when the probe completes with the sentinel."""
        env = _AliveEnv()
        assert tt._env_is_alive(env, probe_timeout=5.0) is True

    def test_dead_env_returns_false(self):
        """_env_is_alive returns False when execute() blocks past probe_timeout."""
        env = _DeadEnv()
        start = time.monotonic()
        result = tt._env_is_alive(env, probe_timeout=0.3)  # short timeout for test speed
        elapsed = time.monotonic() - start
        assert result is False
        # Should not wait far beyond the probe_timeout
        assert elapsed < 2.0, f"Probe took too long: {elapsed:.2f}s"

    def test_raises_returns_false(self):
        """_env_is_alive returns False when execute() raises."""
        class _RaisingEnv:
            def execute(self, command, **kwargs):
                raise RuntimeError("connection refused")
            def cleanup(self):
                pass

        env = _RaisingEnv()
        assert tt._env_is_alive(env, probe_timeout=5.0) is False

    def test_wrong_sentinel_returns_false(self):
        """_env_is_alive returns False when output doesn't contain the sentinel."""
        class _SilentEnv:
            def execute(self, command, **kwargs):
                return {"output": "something else", "returncode": 0}
            def cleanup(self):
                pass

        env = _SilentEnv()
        assert tt._env_is_alive(env, probe_timeout=5.0) is False


# ---------------------------------------------------------------------------
# Tests: session reuse path in terminal_tool()
# ---------------------------------------------------------------------------

class TestSessionReuseLiveness:
    def _patch_common(self, monkeypatch, task_id, env_type: str,
                      active_envs: dict, creation_factory=None):
        """Wire common monkeypatches for terminal_tool() integration tests."""
        monkeypatch.setattr(tt, "_active_environments", active_envs)
        monkeypatch.setattr(tt, "_last_activity", {})
        monkeypatch.setattr(tt, "_task_env_overrides", {})
        monkeypatch.setattr(tt, "_check_all_guards",
                            lambda command, env_type: {"approved": True})
        monkeypatch.setattr(tt, "_get_env_config", lambda: {
            "env_type": env_type,
            "timeout": 10,
            "cwd": "/tmp",
            "host_cwd": None,
            "docker_image": "test-image",
            "singularity_image": "docker://test-image",
            "modal_image": "test-image",
            "modal_mode": "auto",
            "daytona_image": "test-image",
            "vercel_runtime": "",
            "docker_mount_cwd_to_workspace": False,
            "docker_volumes": [],
            "docker_forward_env": [],
            "docker_env": {},
            "docker_run_as_host_user": False,
            "docker_extra_args": [],
            "container_cpu": 1,
            "container_memory": 5120,
            "container_disk": 51200,
            "container_persistent": True,
            "ssh_host": "",
            "ssh_user": "",
            "ssh_port": 22,
            "ssh_key": "",
            "ssh_persistent": False,
            "local_persistent": False,
            "lifetime_seconds": 300,
        })
        # Also stub out _start_cleanup_thread to avoid side effects
        monkeypatch.setattr(tt, "_start_cleanup_thread", lambda: None)
        if creation_factory:
            monkeypatch.setattr(tt, "_create_environment", creation_factory)

    def test_alive_env_reused_no_creation(self, monkeypatch):
        """When the cached env passes the probe, no new env is created."""
        # task_id=None resolves to effective_task_id="default" via _resolve_container_task_id
        alive_env = _AliveEnv()
        active_envs = {"default": alive_env}
        created = []

        def _factory(**kwargs):
            created.append(kwargs)
            return _FreshEnv()

        self._patch_common(monkeypatch, None, "ssh", active_envs, _factory)
        # Shorten probe timeout so the test is fast
        monkeypatch.setattr(tt, "_env_is_alive", lambda env, probe_timeout=5.0: True)

        result = json.loads(tt.terminal_tool(command="echo hi"))

        assert not created, "Factory should NOT have been called for a live env"
        assert active_envs["default"] is alive_env, "Active env should still be the original"

    def test_dead_env_evicted_and_recreated(self, monkeypatch):
        """When the cached env fails the probe, it is evicted and a fresh env created."""
        dead_env = _DeadEnv()
        active_envs = {"default": dead_env}
        fresh_env = _FreshEnv()
        created = []

        def _factory(**kwargs):
            created.append(kwargs)
            return fresh_env

        self._patch_common(monkeypatch, None, "docker", active_envs, _factory)
        # Simulate a failed probe
        monkeypatch.setattr(tt, "_env_is_alive", lambda env, probe_timeout=5.0: False)

        result = json.loads(tt.terminal_tool(command="echo hi"))

        assert created, "Factory MUST have been called after evicting dead env"
        assert dead_env.cleanup_called, "Dead env's cleanup() must be called on eviction"
        assert active_envs.get("default") is fresh_env, "Active env should be the fresh one"

    def test_local_env_skips_probe(self, monkeypatch):
        """For env_type=='local', the liveness probe is never called."""
        local_env = _AliveEnv()
        active_envs = {"default": local_env}
        probe_calls = []

        def _fake_probe(env, probe_timeout=5.0):
            probe_calls.append(env)
            return True

        self._patch_common(monkeypatch, None, "local", active_envs)
        monkeypatch.setattr(tt, "_env_is_alive", _fake_probe)

        result = json.loads(tt.terminal_tool(command="echo hi"))

        assert not probe_calls, (
            "_env_is_alive must NOT be called for env_type='local' "
            "(spawn-per-call, always alive)"
        )

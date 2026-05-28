"""Regression guard: AIAgent construction must not make synchronous network calls (#32221).

Before the fix, _check_compression_model_feasibility → get_model_context_length
→ _query_ollama_api_show made a blocking httpx.post to Ollama during __init__
for any provider, adding ~1.7s (or indefinite hang) on cold start.

After the fix:
- _compression_feasibility_checked is set to False at init (lazy, not eager)
- get_model_context_length skips the Ollama probe for known non-Ollama providers
- ContextCompressor receives provider= so it also skips the probe

This test verifies that constructing AIAgent with provider="openrouter" does NOT
trigger any synchronous HTTP calls (httpx or requests).
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest


def _build_minimal_agent(provider: str = "openrouter", model: str = "gpt-4o"):
    """Construct an AIAgent with the minimal required kwargs and heavy I/O mocked out.

    Patches out:
    - All httpx/requests network calls (assert none are made synchronously)
    - load_config / save_config (no filesystem dependency)
    - Tool discovery (expensive, irrelevant here)
    - OpenAI client construction (requires API key validation)
    """
    import run_agent as ra

    # Patch every plausible synchronous HTTP call surface.
    with (
        patch("httpx.Client.post") as mock_httpx_client_post,
        patch("httpx.Client.get") as mock_httpx_client_get,
        patch("httpx.post") as mock_httpx_post,
        patch("httpx.get") as mock_httpx_get,
        patch("requests.post") as mock_requests_post,
        patch("requests.get") as mock_requests_get,
        patch("requests.request") as mock_requests_request,
        # Stub out heavy side effects that are not under test
        patch("agent.model_metadata.fetch_model_metadata", return_value={}),
        patch("hermes_cli.config.load_config", return_value={}),
        patch("hermes_cli.config.save_config"),
        patch("model_tools.get_tool_definitions", return_value=([], [])),
        patch("model_tools.check_toolset_requirements", return_value=None),
        patch("tools.approval.load_permanent_allowlist", return_value=set()),
        # Prevent background threads from firing network calls after construction
        patch("threading.Thread.start"),
    ):
        # Use a simple MagicMock for the OpenAI client to avoid real auth
        with patch.object(ra, "OpenAI", return_value=MagicMock()):
            agent = ra.AIAgent(
                model=model,
                provider=provider,
                api_key="sk-dummy",
                base_url="https://openrouter.ai/api/v1",
            )

        # None of the synchronous HTTP call mocks should have been invoked
        for name, mock in [
            ("httpx.Client.post", mock_httpx_client_post),
            ("httpx.Client.get", mock_httpx_client_get),
            ("httpx.post", mock_httpx_post),
            ("httpx.get", mock_httpx_get),
            ("requests.post", mock_requests_post),
            ("requests.get", mock_requests_get),
            ("requests.request", mock_requests_request),
        ]:
            assert not mock.called, (
                f"Synchronous network call made during AIAgent.__init__: "
                f"{name} was called {mock.call_count} time(s). "
                f"Call args: {mock.call_args_list}"
            )

        return agent


class TestNoInitNetworkCall:
    def test_openrouter_no_network_call_on_init(self):
        """AIAgent(provider='openrouter') must not make any HTTP calls at construction."""
        agent = _build_minimal_agent(provider="openrouter")
        assert agent is not None

    @pytest.mark.parametrize("provider", [
        "anthropic", "openai", "openai-codex", "copilot",
        "nous", "gmi", "novita", "bedrock", "azure",
    ])
    def test_known_non_ollama_no_network_call_on_init(self, provider):
        """Any known non-Ollama provider must not trigger network calls at init."""
        agent = _build_minimal_agent(provider=provider, model="test-model")
        assert agent is not None

    def test_compression_feasibility_deferred(self):
        """_compression_feasibility_checked must be False after construction.

        The feasibility check (which probes the aux provider chain) must
        not run eagerly — it's deferred to the first compression threshold hit.
        """
        agent = _build_minimal_agent(provider="openrouter")
        assert getattr(agent, "_compression_feasibility_checked", None) is False, (
            "_compression_feasibility_checked should be False after init "
            "(lazy check, not eager)"
        )

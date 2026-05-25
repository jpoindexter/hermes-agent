"""Regression guard: Ollama /api/show probe skipped for known non-Ollama providers (#31555).

Before the fix, _query_ollama_api_show was called unconditionally whenever
base_url was set, adding ~1.7s SSL round-trip on every cold start for
providers like Anthropic, OpenAI, and Codex.

After the fix, the probe only runs when effective_provider is None/"" (unknown)
or one of the Ollama-family providers ("ollama", "ollama-cloud").
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest


def _call_get_model_context(provider, base_url):
    """Call get_model_context_length with _query_ollama_api_show patched to a spy."""
    from agent import model_metadata as mm

    with (
        patch.object(mm, "_query_ollama_api_show", return_value=None) as mock_probe,
        # Stub out everything else that would make network calls.
        patch.object(mm, "get_cached_context_length", return_value=None),
        patch.object(mm, "_resolve_endpoint_context_length", return_value=None),
        patch.object(mm, "_query_anthropic_context_length", return_value=None),
        patch.object(mm, "_is_custom_endpoint", return_value=False),
        patch.object(mm, "_is_known_provider_base_url", return_value=True),
        patch.object(mm, "lookup_models_dev_context" if hasattr(mm, "lookup_models_dev_context") else "_resolve_nous_context_length", return_value=None),
        patch("agent.models_dev.lookup_models_dev_context", return_value=None, create=True),
    ):
        try:
            mm.get_model_context_length(
                model="test-model",
                provider=provider,
                base_url=base_url,
                api_key="",
            )
        except Exception:
            pass  # we only care whether the probe was called
        return mock_probe.called


class TestOllamaProbeSkip:
    @pytest.mark.parametrize("provider", [
        "anthropic", "openai", "openai-codex", "copilot", "openrouter",
        "nous", "gmi", "novita", "bedrock", "azure",
    ])
    def test_probe_skipped_for_known_non_ollama(self, provider):
        """Known non-Ollama providers must not trigger the /api/show probe."""
        called = _call_get_model_context(provider, "https://some-provider.com/v1")
        assert not called, f"Ollama probe should be skipped for provider={provider!r}"

    @pytest.mark.parametrize("provider", ["ollama", "ollama-cloud"])
    def test_probe_runs_for_ollama_providers(self, provider):
        """Ollama providers must still trigger the probe."""
        called = _call_get_model_context(provider, "http://localhost:11434")
        assert called, f"Ollama probe should run for provider={provider!r}"

    def test_probe_runs_for_unknown_provider(self):
        """Unknown/empty provider with a base_url must still probe (could be Ollama)."""
        called = _call_get_model_context(None, "http://192.168.1.5:11434")
        assert called, "Ollama probe should run when provider is unknown"

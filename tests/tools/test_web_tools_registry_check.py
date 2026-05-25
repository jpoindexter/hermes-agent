"""Regression guard: check_web_api_key() consults plugin registry first.

Before #31873, check_web_api_key() only checked hardcoded backends, so plugin
providers (registered via web_search_registry) were always reported unavailable.
"""
from __future__ import annotations

import types
import sys
from unittest.mock import MagicMock, patch


def _reload_web_tools():
    import importlib
    import tools.web_tools as m
    return importlib.reload(m)


class TestCheckWebApiKeyRegistryFirst:
    def test_registry_provider_available_returns_true(self, monkeypatch):
        """If any registered plugin provider is available, return True without
        checking hardcoded backends."""
        available_provider = MagicMock()
        available_provider.is_available.return_value = True

        with patch("agent.web_search_registry.list_providers", return_value=[available_provider]):
            import tools.web_tools as wt
            result = wt.check_web_api_key()

        assert result is True
        available_provider.is_available.assert_called_once()

    def test_registry_provider_unavailable_falls_through(self, monkeypatch):
        """If no plugin provider is available, fall through to hardcoded backend check."""
        unavailable_provider = MagicMock()
        unavailable_provider.is_available.return_value = False

        with (
            patch("agent.web_search_registry.list_providers", return_value=[unavailable_provider]),
            patch("tools.web_tools._load_web_config", return_value={"backend": ""}),
            patch("tools.web_tools._is_backend_available", return_value=False),
        ):
            import tools.web_tools as wt
            result = wt.check_web_api_key()

        assert result is False

    def test_registry_import_error_falls_through(self):
        """If web_search_registry is missing entirely, fall through gracefully."""
        with (
            patch.dict(sys.modules, {"agent.web_search_registry": None}),
            patch("tools.web_tools._load_web_config", return_value={"backend": ""}),
            patch("tools.web_tools._is_backend_available", return_value=False),
        ):
            import tools.web_tools as wt
            result = wt.check_web_api_key()

        assert result is False

    def test_no_providers_falls_through(self):
        """Empty registry list falls through to hardcoded check."""
        with (
            patch("agent.web_search_registry.list_providers", return_value=[]),
            patch("tools.web_tools._load_web_config", return_value={"backend": "exa"}),
            patch("tools.web_tools._is_backend_available", return_value=True),
        ):
            import tools.web_tools as wt
            result = wt.check_web_api_key()

        assert result is True

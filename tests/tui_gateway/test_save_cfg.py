"""Tests for tui_gateway.server._save_cfg — atomic config persistence."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture()
def server_mod(tmp_path):
    """Import tui_gateway.server with a mocked hermes_home pointing at tmp_path."""
    import importlib
    import sys

    mock_hermes_home = tmp_path

    with patch.dict(
        "sys.modules",
        {
            "hermes_constants": MagicMock(
                get_hermes_home=MagicMock(return_value=mock_hermes_home),
                display_hermes_home=MagicMock(return_value=str(mock_hermes_home)),
            ),
            "hermes_cli.env_loader": MagicMock(),
            "hermes_cli.banner": MagicMock(),
            "hermes_state": MagicMock(),
        },
    ):
        mod = importlib.import_module("tui_gateway.server")
        # Override the module-level _hermes_home so _save_cfg uses tmp_path
        mod._hermes_home = mock_hermes_home
        yield mod, tmp_path
        # Reload to clear module-level state for subsequent tests
        try:
            importlib.reload(mod)
        except Exception:
            pass


class TestSaveCfg:
    def test_save_cfg_produces_parseable_yaml(self, server_mod):
        """_save_cfg output must be parseable by yaml.safe_load."""
        mod, tmp_path = server_mod
        cfg = {
            "model": "claude-opus-4-5",
            "tools": ["bash", "read"],
            "nested": {"key": "value"},
        }

        mod._save_cfg(cfg)

        config_path = tmp_path / "config.yaml"
        assert config_path.exists()
        parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert parsed == cfg

    def test_save_cfg_updates_cache(self, server_mod):
        """_save_cfg must update _cfg_cache to match the written data."""
        mod, tmp_path = server_mod
        cfg = {"key": "value", "count": 7}

        mod._save_cfg(cfg)

        assert mod._cfg_cache == cfg

    def test_save_cfg_updates_mtime(self, server_mod):
        """_save_cfg must set _cfg_mtime after writing."""
        mod, tmp_path = server_mod

        mod._save_cfg({"model": "claude-haiku-4-5"})

        assert mod._cfg_mtime is not None

    def test_save_cfg_is_atomic_on_failure(self, server_mod):
        """If atomic_yaml_write fails, original config.yaml is not truncated."""
        import utils

        mod, tmp_path = server_mod
        original_cfg = {"original": True}
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.safe_dump(original_cfg), encoding="utf-8")

        with patch.object(utils, "atomic_replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                mod._save_cfg({"new": True})

        # Original file must still be intact
        parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert parsed == original_cfg

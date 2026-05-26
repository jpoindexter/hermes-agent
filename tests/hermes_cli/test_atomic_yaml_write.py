"""Tests for utils.atomic_yaml_write — crash-safe YAML file writes."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from utils import atomic_yaml_write


class TestAtomicYamlWrite:
    def test_writes_valid_yaml(self, tmp_path):
        target = tmp_path / "data.yaml"
        data = {"key": "value", "nested": {"a": 1}}

        atomic_yaml_write(target, data)

        assert yaml.safe_load(target.read_text(encoding="utf-8")) == data

    def test_cleans_up_temp_file_on_baseexception(self, tmp_path):
        class SimulatedAbort(BaseException):
            pass

        target = tmp_path / "data.yaml"
        original = {"preserved": True}
        target.write_text(yaml.safe_dump(original), encoding="utf-8")

        with patch("utils.yaml.dump", side_effect=SimulatedAbort):
            with pytest.raises(SimulatedAbort):
                atomic_yaml_write(target, {"new": True})

        tmp_files = [f for f in tmp_path.iterdir() if ".tmp" in f.name]
        assert len(tmp_files) == 0
        assert yaml.safe_load(target.read_text(encoding="utf-8")) == original

    def test_appends_extra_content(self, tmp_path):
        target = tmp_path / "data.yaml"

        atomic_yaml_write(target, {"key": "value"}, extra_content="\n# comment\n")

        text = target.read_text(encoding="utf-8")
        assert "key: value" in text
        assert "# comment" in text

    def test_raises_and_does_not_corrupt_on_invalid_extra_content(self, tmp_path):
        """Validation step: temp file must be valid YAML before replacing original."""
        target = tmp_path / "data.yaml"
        original = {"preserved": True}
        target.write_text(yaml.safe_dump(original), encoding="utf-8")

        # extra_content with an unpaired colon produces a YAML parse error
        bad_extra = "\nbroken: : bad\n"

        with pytest.raises((ValueError, yaml.YAMLError)):
            atomic_yaml_write(target, {"new": "data"}, extra_content=bad_extra)

        # Original file must be untouched
        assert yaml.safe_load(target.read_text(encoding="utf-8")) == original

        # No temp files left behind
        tmp_files = [f for f in tmp_path.iterdir() if ".tmp" in f.name]
        assert len(tmp_files) == 0

    def test_valid_data_produces_parseable_output(self, tmp_path):
        """atomic_yaml_write output must always be parseable by yaml.safe_load."""
        target = tmp_path / "config.yaml"
        data = {
            "model": "claude-opus-4-5",
            "tools": ["bash", "read", "write"],
            "nested": {"key": "value", "count": 42},
        }

        atomic_yaml_write(target, data)

        parsed = yaml.safe_load(target.read_text(encoding="utf-8"))
        assert parsed == data

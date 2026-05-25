"""Regression guard: tool-name sanitization for the Codex Responses API.

The Responses API rejects function names that don't match ^[a-zA-Z0-9_-]+.
_sanitize_responses_name() must strip any char outside that set before the
name reaches the wire.
"""
from __future__ import annotations

import pytest


def _import_sanitize():
    from agent.codex_responses_adapter import _sanitize_responses_name
    return _sanitize_responses_name


class TestSanitizeResponsesName:
    def test_clean_name_unchanged(self):
        fn = _import_sanitize()
        assert fn("read_file") == "read_file"

    def test_dots_stripped(self):
        fn = _import_sanitize()
        assert fn("hermes.read_file") == "hermesread_file"

    def test_spaces_stripped(self):
        fn = _import_sanitize()
        assert fn("my tool name") == "mytoolname"

    def test_special_chars_stripped(self):
        fn = _import_sanitize()
        assert fn("tool@v2!") == "toolv2"

    def test_hyphens_and_underscores_kept(self):
        fn = _import_sanitize()
        assert fn("my-tool_v2") == "my-tool_v2"

    def test_empty_string(self):
        fn = _import_sanitize()
        assert fn("") == ""

    def test_all_invalid_chars(self):
        fn = _import_sanitize()
        assert fn("!!!") == ""

    def test_unicode_stripped(self):
        fn = _import_sanitize()
        # ó may decompose to t + combining accent; only ASCII alnum/_/- survive
        result = fn("tóol")
        assert result in ("tol", "tool")
        assert all(c.isascii() for c in result)

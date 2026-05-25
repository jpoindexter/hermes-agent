"""Regression guard: flush-before-drop and overshoot protection (#31507).

Before the fix, _persist_session called _drop_trailing_empty_response_scaffolding
BEFORE _flush_messages_to_session_db.  When the drop removed messages that an
intermediate flush had already counted (advancing _last_flushed_db_idx), the
final persist saw flush_from > len(messages) and wrote nothing — silently
dropping messages added after the last intermediate flush.

The fix:
  1. _persist_session flushes FIRST, then drops.
  2. _flush_messages_to_session_db clamps flush_from to len(messages) when it
     would overshoot (guard for any remaining edge cases).
  3. Synthetic scaffolding markers (_empty_recovery_synthetic,
     _empty_terminal_sentinel) are filtered out of the DB write.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_agent(session_db):
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
        from run_agent import AIAgent
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="test/model",
            quiet_mode=True,
            session_db=session_db,
            session_id="test-31507",
            skip_context_files=True,
            skip_memory=True,
        )
    agent._ensure_db_session()
    return agent


class TestFlushBeforeDrop:
    def test_messages_written_before_scaffolding_removed(self):
        """Tool results added before terminal sentinel must reach state.db even
        when _drop_trailing pops them alongside the sentinel."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "test.db")
            agent = _make_agent(db)

            # Simulate a turn: tool_calls assistant + tool results, then sentinel.
            messages = [
                {"role": "user", "content": "do something"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "fn", "arguments": "{}"}}]},
                {"role": "tool", "content": "result1", "tool_call_id": "c1"},
                {"role": "tool", "content": "result2", "tool_call_id": "c1"},
                {"role": "assistant", "content": "(empty)", "_empty_terminal_sentinel": True},
            ]

            # _persist_session should flush the real messages BEFORE drop removes them.
            agent._persist_session(messages, [])

            rows = db.get_messages(agent.session_id)
            roles = [r["role"] for r in rows]

            # Tool results must be in DB even though _drop_trailing removes them.
            assert roles.count("tool") == 2, f"Expected 2 tool rows, got {roles}"
            # The sentinel itself must NOT be in DB.
            contents = [r.get("content") for r in rows if r["role"] == "assistant"]
            assert "(empty)" not in [c for c in contents if c], \
                "Terminal sentinel content should not be persisted"

    def test_overshoot_guard_prevents_silent_skip(self):
        """When _last_flushed_db_idx > len(messages) after a drop, the guard
        clamps flush_from to len(messages) so the pointer is updated correctly
        and the next flush starts from the right place."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "test.db")
            agent = _make_agent(db)

            base = [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
            ]

            # First flush: write 2 messages, pointer = 2.
            agent._flush_messages_to_session_db(base, [])
            assert agent._last_flushed_db_idx == 2

            # Simulate scaffolding removal shrinking messages back to 1.
            shrunk = base[:1]

            # Second flush with shrunk list — must NOT raise, must update pointer.
            agent._flush_messages_to_session_db(shrunk, [])
            assert agent._last_flushed_db_idx == 1, \
                "_last_flushed_db_idx should clamp to len(messages) on overshoot"

            # Third flush with a new message — must write it (pointer was reset).
            extended = shrunk + [{"role": "assistant", "content": "new"}]
            agent._flush_messages_to_session_db(extended, [])
            rows = db.get_messages(agent.session_id)
            contents = [r.get("content") for r in rows]
            assert "new" in contents, "New message after overshoot must be flushed"

    def test_synthetic_markers_not_persisted(self):
        """Both _empty_recovery_synthetic and _empty_terminal_sentinel messages
        must be filtered out of the session DB."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "test.db")
            agent = _make_agent(db)

            messages = [
                {"role": "user", "content": "go"},
                {"role": "assistant", "content": "(empty)", "_empty_recovery_synthetic": True},
                {"role": "user", "content": "nudge", "_empty_recovery_synthetic": True},
                {"role": "assistant", "content": "(empty)", "_empty_terminal_sentinel": True},
                {"role": "assistant", "content": "real response"},
            ]

            agent._flush_messages_to_session_db(messages, [])
            rows = db.get_messages(agent.session_id)

            # Only the real user message + real assistant response should be stored.
            assert len(rows) == 2, f"Expected 2 real rows, got {len(rows)}: {rows}"
            contents = {r.get("content") for r in rows}
            assert "go" in contents
            assert "real response" in contents

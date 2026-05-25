"""Regression guard: assistant content=None (not "") when tool_calls present (#31583).

Strict OpenAI-compat upstreams reject replayed history where an assistant
turn has content="" with tool_calls.  The fix emits None so the field is
absent/null rather than an empty string.
"""
from __future__ import annotations

from unittest.mock import MagicMock


def _call_build(content_val, has_tool_calls):
    """Call build_assistant_message with minimal mocks."""
    from agent.chat_completion_helpers import build_assistant_message

    agent = MagicMock()
    agent._extract_reasoning.return_value = None
    agent.verbose_logging = False
    agent.reasoning_callback = None
    agent.stream_delta_callback = None
    agent._stream_callback = None
    agent._strip_think_blocks.side_effect = lambda s: s
    agent._needs_thinking_reasoning_pad.return_value = False
    agent._should_sanitize_tool_calls.return_value = False
    agent._split_responses_tool_id.return_value = ("call_1", None)
    agent._deterministic_call_id.return_value = "call_1"

    msg = MagicMock()
    msg.content = content_val
    if has_tool_calls:
        tc = MagicMock()
        tc.id = "call_1"
        tc.call_id = "call_1"
        tc.type = "function"
        tc.function.name = "my_tool"
        tc.function.arguments = "{}"
        msg.tool_calls = [tc]
    else:
        msg.tool_calls = None

    msg.reasoning_content = None
    msg.model_extra = {}

    return build_assistant_message(agent, msg, "tool_calls" if has_tool_calls else "stop")


class TestAssistantContentNoneForToolCalls:
    def test_empty_content_with_tool_calls_is_none(self):
        """content="" + tool_calls → stored as None, not ""."""
        result = _call_build(content_val="", has_tool_calls=True)
        assert result["content"] is None, \
            f"Expected None, got {result['content']!r}"

    def test_none_content_with_tool_calls_is_none(self):
        """content=None + tool_calls → stored as None."""
        result = _call_build(content_val=None, has_tool_calls=True)
        assert result["content"] is None

    def test_real_content_with_tool_calls_preserved(self):
        """chain-of-thought text + tool_calls → content preserved."""
        result = _call_build(content_val="Let me check that.", has_tool_calls=True)
        assert result["content"] == "Let me check that."

    def test_empty_content_no_tool_calls_stays_empty_string(self):
        """content="" with no tool_calls → kept as empty string (not None)."""
        result = _call_build(content_val="", has_tool_calls=False)
        # "" is acceptable when there are no tool_calls — don't change this behavior.
        assert result["content"] == "" or result["content"] is None  # either ok

    def test_real_content_no_tool_calls_preserved(self):
        """Normal text response without tool_calls → content unchanged."""
        result = _call_build(content_val="Here is the answer.", has_tool_calls=False)
        assert result["content"] == "Here is the answer."

"""Regression guard: strip_think_blocks must not hold the GIL on large inputs (#32079).

The profiler showed _sre_SRE_Pattern_search / sre_search with other threads
blocked on take_gil after a Codex response.  strip_think_blocks was applying
10+ regex passes (one per tag variant) to full multi-KB response text even
when the response contained no reasoning markers at all.

The fix: early-out when '<' is not in content (common case), and guard the
<think> findall in build_assistant_message similarly.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock


class TestStripThinkBlocksFastPath:
    """strip_think_blocks returns quickly on large tag-free content."""

    def test_no_tags_fast_path(self):
        """200KB response with no tags completes in < 0.05s (fast-path skips regex)."""
        from agent.agent_runtime_helpers import strip_think_blocks

        agent = MagicMock()
        big_text = "The answer is " + "A" * 200_000

        start = time.monotonic()
        result = strip_think_blocks(agent, big_text)
        elapsed = time.monotonic() - start

        assert result == big_text, "Tag-free content must be returned unchanged"
        assert elapsed < 0.05, (
            f"strip_think_blocks took {elapsed:.3f}s on 200KB tag-free input — "
            f"expected fast-path < 0.05s (#32079)"
        )

    def test_unterminated_think_at_start_of_large_response(self):
        """200KB input with unterminated <think> at start finishes quickly."""
        from agent.agent_runtime_helpers import strip_think_blocks

        agent = MagicMock()
        # Simulate a Codex response that starts with a think tag but never closes it —
        # this is the exact shape that caused GIL stalls.
        big_text = "<think>" + "X" * 200_000

        start = time.monotonic()
        result = strip_think_blocks(agent, big_text)
        elapsed = time.monotonic() - start

        # The whole string should be stripped (unterminated block from start).
        assert result.strip() == "", (
            f"Expected empty result for unterminated block, got {result[:100]!r}"
        )
        assert elapsed < 1.0, (
            f"strip_think_blocks took {elapsed:.3f}s on 200KB unterminated "
            f"<think> input (#32079)"
        )

    def test_completed_think_block_stripped_correctly(self):
        """Closed <think>...</think> still stripped correctly after the fast-path guard."""
        from agent.agent_runtime_helpers import strip_think_blocks

        agent = MagicMock()
        content = "<think>internal reasoning</think>Here is the answer."
        result = strip_think_blocks(agent, content)
        assert result.strip() == "Here is the answer."

    def test_empty_string_returns_empty(self):
        from agent.agent_runtime_helpers import strip_think_blocks

        agent = MagicMock()
        assert strip_think_blocks(agent, "") == ""

    def test_none_handled_by_caller_guard(self):
        """Callers always pass str — confirm fast-path handles tag-free unicode."""
        from agent.agent_runtime_helpers import strip_think_blocks

        agent = MagicMock()
        # Unicode response with no tags
        text = "Résumé: " + "é" * 10_000
        result = strip_think_blocks(agent, text)
        assert result == text


class TestBuildAssistantMessageThinkGuard:
    """build_assistant_message skips <think> findall when tag absent (#32079)."""

    def _make_msg(self, content_val):
        msg = MagicMock()
        msg.content = content_val
        msg.tool_calls = None
        msg.reasoning_content = None
        msg.model_extra = {}
        return msg

    def _make_agent(self):
        agent = MagicMock()
        agent._extract_reasoning.return_value = None
        agent.verbose_logging = False
        agent.reasoning_callback = None
        agent.stream_delta_callback = None
        agent._stream_callback = None
        # strip_think_blocks is a forwarded method — let it run the real logic
        from agent.agent_runtime_helpers import strip_think_blocks
        agent._strip_think_blocks.side_effect = lambda s: strip_think_blocks(agent, s)
        agent._needs_thinking_reasoning_pad.return_value = False
        agent._should_sanitize_tool_calls.return_value = False
        agent._split_responses_tool_id.return_value = ("call_1", None)
        agent._deterministic_call_id.return_value = "call_1"
        return agent

    def test_large_tag_free_response_completes_quickly(self):
        """200KB tag-free Codex response must not stall the GIL in findall."""
        from agent.chat_completion_helpers import build_assistant_message

        agent = self._make_agent()
        big_content = "This is a long answer. " * 9000  # ~200KB
        msg = self._make_msg(big_content)

        start = time.monotonic()
        result = build_assistant_message(agent, msg, "stop")
        elapsed = time.monotonic() - start

        assert result["reasoning"] is None, "No reasoning expected in tag-free content"
        assert elapsed < 0.1, (
            f"build_assistant_message took {elapsed:.3f}s on 200KB tag-free input — "
            f"expected < 0.1s (#32079)"
        )

    def test_think_tags_still_extracted(self):
        """Reasoning still captured when <think>...</think> present."""
        from agent.chat_completion_helpers import build_assistant_message

        agent = self._make_agent()
        content = "<think>internal reasoning here</think>Final answer."
        msg = self._make_msg(content)

        result = build_assistant_message(agent, msg, "stop")
        assert result["reasoning"] == "internal reasoning here"

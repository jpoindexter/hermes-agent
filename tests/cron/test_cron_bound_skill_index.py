"""Bug #32235 — Cron jobs with skills=[...] must scope the skill index.

When a cron job specifies ``skills: [web-crawl]``, the agent's system prompt
must only pre-advertise ``web-crawl`` in the skill index.  Unrelated skills
(e.g. freshrss) must not appear, so the model cannot mistake them for
in-scope tools.

When a cron job has no ``skills`` key, the full index is present (no
regression for the existing behaviour).

Three test surfaces:
1. ``_cron_bound_skill_names`` helper — normalisation logic
2. ``build_skills_system_prompt(bound_skill_names=[...])`` — prompt filtering
3. Integration via ``_build_job_prompt`` result content (skills content is
   already in the prompt; the system-prompt scoping is a separate concern
   verified in the prompt-builder unit tests above).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_skills_prompt_cache():
    """Prevent LRU cache bleed between tests."""
    from agent.prompt_builder import clear_skills_system_prompt_cache
    clear_skills_system_prompt_cache(clear_snapshot=True)
    yield
    clear_skills_system_prompt_cache(clear_snapshot=True)


@pytest.fixture
def skills_env(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with two skills planted: web-crawl and freshrss."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    skills_dir = hermes_home / "skills"
    skills_dir.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    # web-crawl skill
    wc_dir = skills_dir / "productivity" / "web-crawl"
    wc_dir.mkdir(parents=True)
    (wc_dir / "SKILL.md").write_text(
        "---\nname: web-crawl\ndescription: Crawl web pages\n---\n\nUse crawl_url().\n",
        encoding="utf-8",
    )

    # freshrss skill — must NOT appear when job binds only web-crawl
    rss_dir = skills_dir / "productivity" / "freshrss"
    rss_dir.mkdir(parents=True)
    (rss_dir / "SKILL.md").write_text(
        "---\nname: freshrss\ndescription: Manage FreshRSS feeds\n---\n\nUse freshrss_api().\n",
        encoding="utf-8",
    )

    return hermes_home


# ---------------------------------------------------------------------------
# _cron_bound_skill_names helper
# ---------------------------------------------------------------------------


class TestCronBoundSkillNames:
    def _fn(self):
        import cron.scheduler as sch
        return sch._cron_bound_skill_names

    def test_no_skills_returns_none(self):
        fn = self._fn()
        assert fn({}) is None

    def test_skills_list_returns_normalised(self):
        fn = self._fn()
        result = fn({"skills": ["web-crawl", "  freshrss  "]})
        assert result == ["web-crawl", "freshrss"]

    def test_skills_string_returns_single_element(self):
        fn = self._fn()
        result = fn({"skills": "web-crawl"})
        assert result == ["web-crawl"]

    def test_legacy_skill_singular(self):
        fn = self._fn()
        result = fn({"skill": "web-crawl"})
        assert result == ["web-crawl"]

    def test_empty_skills_list_returns_none(self):
        fn = self._fn()
        # An all-whitespace list normalises to empty → treat as no-skills
        result = fn({"skills": ["", "  "]})
        assert result is None

    def test_skills_takes_precedence_over_legacy_skill(self):
        fn = self._fn()
        result = fn({"skills": ["web-crawl"], "skill": "freshrss"})
        assert result == ["web-crawl"]


# ---------------------------------------------------------------------------
# build_skills_system_prompt filtering
# ---------------------------------------------------------------------------


class TestBuildSkillsSystemPromptBoundFilter:
    def test_full_index_when_no_bound(self, skills_env):
        from agent.prompt_builder import build_skills_system_prompt
        result = build_skills_system_prompt()
        assert "web-crawl" in result
        assert "freshrss" in result

    def test_bound_single_skill_omits_others(self, skills_env):
        from agent.prompt_builder import build_skills_system_prompt
        result = build_skills_system_prompt(bound_skill_names=["web-crawl"])
        assert "web-crawl" in result
        assert "freshrss" not in result

    def test_bound_empty_list_treated_as_no_filter(self, skills_env):
        """Passing an empty list must not wipe the whole index (same as None)."""
        from agent.prompt_builder import build_skills_system_prompt
        result = build_skills_system_prompt(bound_skill_names=[])
        # Empty list is falsy — full index shown
        assert "web-crawl" in result
        assert "freshrss" in result

    def test_bound_returns_empty_when_no_match(self, skills_env):
        """If bound names don't match any installed skill, index is empty."""
        from agent.prompt_builder import build_skills_system_prompt
        result = build_skills_system_prompt(bound_skill_names=["nonexistent-skill"])
        assert "web-crawl" not in result
        assert "freshrss" not in result

    def test_bound_multiple_skills(self, skills_env):
        from agent.prompt_builder import build_skills_system_prompt
        result = build_skills_system_prompt(bound_skill_names=["web-crawl", "freshrss"])
        assert "web-crawl" in result
        assert "freshrss" in result

    def test_cache_key_distinct_for_different_bounds(self, skills_env):
        """Different bound_skill_names must not hit the same cache entry."""
        from agent.prompt_builder import build_skills_system_prompt
        result_bound = build_skills_system_prompt(bound_skill_names=["web-crawl"])
        result_full = build_skills_system_prompt()
        assert "freshrss" not in result_bound
        assert "freshrss" in result_full

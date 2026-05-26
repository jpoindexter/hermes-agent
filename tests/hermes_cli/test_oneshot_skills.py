"""Tests for --skills / -s flag in hermes -z (oneshot) mode.

Bug #31548: hermes -z silently discarded the --skills flag because
run_oneshot() had no ``skills`` parameter and both main.py callsites
omitted it from the run_oneshot() invocation.
"""

from __future__ import annotations

import sys
import types


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_inner_run_agent(agent_captured: dict):
    """Minimal _run_agent replacement that records the skills_prompt it received."""

    def _inner(prompt, model=None, provider=None, toolsets=None,
                use_config_toolsets=True, skills_prompt=None):
        agent_captured["ephemeral_system_prompt"] = skills_prompt
        return "ok"

    return _inner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_oneshot_passes_skills_as_ephemeral_system_prompt(monkeypatch):
    """Skills must be built into a prompt and forwarded to _run_agent as skills_prompt."""
    from hermes_cli import oneshot as oneshot_mod
    import agent.skill_commands as sc_mod

    agent_captured: dict = {}
    SENTINEL = "SKILL CONTENT: my_skill instructions here"

    monkeypatch.setattr(oneshot_mod, "_run_agent", _make_inner_run_agent(agent_captured))
    # build_preloaded_skills_prompt is imported locally inside run_oneshot; patch
    # it on the source module so the local import picks up the stub.
    monkeypatch.setattr(
        sc_mod,
        "build_preloaded_skills_prompt",
        lambda skills, task_id=None: (SENTINEL, list(skills), []),
    )

    rc = oneshot_mod.run_oneshot("do X", skills="my_skill")

    assert rc == 0
    assert agent_captured.get("ephemeral_system_prompt") == SENTINEL


def test_oneshot_unknown_skill_returns_exit_2(monkeypatch, capsys):
    """Unknown skill names must produce a stderr message and return code 2.

    Error must surface BEFORE the devnull redirect so it actually reaches
    the terminal.
    """
    from hermes_cli import oneshot as oneshot_mod
    import agent.skill_commands as sc_mod

    monkeypatch.setattr(
        sc_mod,
        "build_preloaded_skills_prompt",
        lambda skills, task_id=None: ("", [], list(skills)),
    )

    rc = oneshot_mod.run_oneshot("do X", skills="nonexistent_skill")

    assert rc == 2
    err = capsys.readouterr().err
    assert "nonexistent_skill" in err
    assert "unknown skill" in err.lower()


def test_oneshot_no_skills_does_not_set_ephemeral_prompt(monkeypatch):
    """When --skills is not given, ephemeral_system_prompt must remain None."""
    from hermes_cli import oneshot as oneshot_mod

    agent_captured: dict = {}
    monkeypatch.setattr(oneshot_mod, "_run_agent", _make_inner_run_agent(agent_captured))

    rc = oneshot_mod.run_oneshot("do X")

    assert rc == 0
    assert agent_captured.get("ephemeral_system_prompt") is None


def test_main_passes_skills_to_run_oneshot(monkeypatch):
    """`hermes -z 'prompt' --skills my_skill` must forward skills to run_oneshot."""
    import hermes_cli.main as main_mod

    captured: dict = {}
    monkeypatch.setattr(
        sys, "argv",
        ["hermes", "-z", "do X", "--skills", "my_skill"],
    )
    # Prevent plugin discovery and shell-hook registration which would hit disk/network.
    monkeypatch.setattr(main_mod, "_prepare_agent_startup", lambda args: None)
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.oneshot",
        types.SimpleNamespace(
            run_oneshot=lambda prompt, **kwargs: captured.update(
                {"prompt": prompt, **kwargs}
            ) or 0
        ),
    )

    try:
        main_mod.main()
    except SystemExit:
        pass

    assert captured.get("skills") == ["my_skill"]


def test_parse_skills_argument_comma_separated():
    """_parse_skills_argument must split comma-separated names and strip whitespace."""
    from hermes_cli.oneshot import _parse_skills_argument

    assert _parse_skills_argument("a,b,c") == ["a", "b", "c"]
    assert _parse_skills_argument(["a,b", "c"]) == ["a", "b", "c"]
    assert _parse_skills_argument(None) == []
    assert _parse_skills_argument("") == []


def test_parse_skills_argument_deduplicates():
    """Duplicate skill names must be dropped, preserving first-seen order."""
    from hermes_cli.oneshot import _parse_skills_argument

    result = _parse_skills_argument(["alpha,beta", "alpha"])
    assert result == ["alpha", "beta"]

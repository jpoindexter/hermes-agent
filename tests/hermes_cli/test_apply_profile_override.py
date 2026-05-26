"""Regression tests for _apply_profile_override HERMES_HOME guard (issue #22502).

When HERMES_HOME is set to the hermes root (e.g. systemd hardcodes
HERMES_HOME=/root/.hermes), _apply_profile_override must still read
active_profile and update HERMES_HOME to the profile directory.

When HERMES_HOME is already a profile directory (.../profiles/<name>),
_apply_profile_override must trust it and return without re-reading
active_profile (child-process inheritance contract).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def _run_apply_profile_override(
    tmp_path, monkeypatch, *, hermes_home: str | None, active_profile: str | None,
    argv: list[str] | None = None,
):
    """Run _apply_profile_override in isolation.

    Returns the value of os.environ["HERMES_HOME"] after the call,
    or None if unset.
    """
    hermes_root = tmp_path / ".hermes"
    hermes_root.mkdir(parents=True, exist_ok=True)

    if active_profile is not None:
        (hermes_root / "active_profile").write_text(active_profile)

    if active_profile and active_profile != "default":
        (hermes_root / "profiles" / active_profile).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    if hermes_home is not None:
        monkeypatch.setenv("HERMES_HOME", hermes_home)
    else:
        monkeypatch.delenv("HERMES_HOME", raising=False)

    monkeypatch.setattr(sys, "argv", argv or ["hermes", "gateway", "start"])

    from hermes_cli.main import _apply_profile_override
    _apply_profile_override()

    return os.environ.get("HERMES_HOME")


class TestApplyProfileOverrideHermesHomeGuard:
    """Regression guard for issue #22502.

    Verifies that HERMES_HOME pointing to the hermes root does NOT suppress
    the active_profile check, while HERMES_HOME already pointing to a
    profile directory IS trusted as-is.
    """

    def test_hermes_home_at_root_with_active_profile_is_redirected(
        self, tmp_path, monkeypatch
    ):
        """HERMES_HOME=/root/.hermes + active_profile=coder must redirect
        HERMES_HOME to .../profiles/coder.

        Bug scenario from #22502: systemd sets HERMES_HOME to the hermes root
        and the user switches to a profile via `hermes profile use`.
        Before the fix, the guard returned early and active_profile was ignored.
        """
        hermes_root = tmp_path / ".hermes"
        hermes_root.mkdir(parents=True, exist_ok=True)

        result = _run_apply_profile_override(
            tmp_path,
            monkeypatch,
            hermes_home=str(hermes_root),
            active_profile="coder",
        )

        assert result is not None, "HERMES_HOME must be set after profile redirect"
        assert "profiles" in result, (
            f"Expected HERMES_HOME to point into profiles/ dir, got: {result!r}"
        )
        assert result.endswith("coder"), (
            f"Expected HERMES_HOME to end with 'coder', got: {result!r}"
        )

    def test_hermes_home_already_profile_dir_is_trusted(self, tmp_path, monkeypatch):
        """HERMES_HOME=.../profiles/coder must not be overridden even when
        active_profile says something different.

        Preserves the child-process inheritance contract: a subprocess spawned
        with HERMES_HOME already set to a specific profile must stay in that
        profile.
        """
        hermes_root = tmp_path / ".hermes"
        profile_dir = hermes_root / "profiles" / "coder"
        profile_dir.mkdir(parents=True, exist_ok=True)

        (hermes_root / "active_profile").write_text("other")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("HERMES_HOME", str(profile_dir))
        monkeypatch.setattr(sys, "argv", ["hermes", "gateway", "start"])

        from hermes_cli.main import _apply_profile_override
        _apply_profile_override()

        assert os.environ.get("HERMES_HOME") == str(profile_dir), (
            "HERMES_HOME must remain unchanged when already pointing to a profile dir"
        )

    def test_hermes_home_unset_reads_active_profile(self, tmp_path, monkeypatch):
        """Classic case: HERMES_HOME unset + active_profile=coder must set
        HERMES_HOME to the profile directory (existing behaviour must not regress).
        """
        result = _run_apply_profile_override(
            tmp_path,
            monkeypatch,
            hermes_home=None,
            active_profile="coder",
        )

        assert result is not None
        assert "coder" in result

    def test_hermes_home_unset_default_profile_no_redirect(self, tmp_path, monkeypatch):
        """active_profile=default must not redirect HERMES_HOME."""
        hermes_root = tmp_path / ".hermes"
        hermes_root.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setattr(sys, "argv", ["hermes", "gateway", "start"])
        (hermes_root / "active_profile").write_text("default")

        from hermes_cli.main import _apply_profile_override
        _apply_profile_override()

        assert os.environ.get("HERMES_HOME") is None


class TestCronCreateEditProfileFlag:
    """Bug #32046 / #32045 — cron create/edit --profile must NOT redirect HERMES_HOME.

    The --profile flag on 'hermes cron create/edit' is a job-level option that
    sets the profile field on the job record.  It must not cause _apply_profile_override
    to switch the process's HERMES_HOME, which would write the job to the profile's
    cron directory instead of the root jobs.json.
    """

    def _run(self, tmp_path, monkeypatch, argv: list[str]) -> str | None:
        hermes_root = tmp_path / ".hermes"
        hermes_root.mkdir(parents=True, exist_ok=True)
        profile_dir = hermes_root / "profiles" / "support"
        profile_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setattr(sys, "argv", argv)

        from hermes_cli.main import _apply_profile_override
        _apply_profile_override()

        return os.environ.get("HERMES_HOME")

    def test_cron_create_profile_does_not_redirect_hermes_home(
        self, tmp_path, monkeypatch
    ):
        result = self._run(
            tmp_path,
            monkeypatch,
            argv=["hermes", "cron", "create", "--prompt", "hi", "--schedule", "daily", "--profile", "support"],
        )
        assert result is None, (
            f"cron create --profile must not switch HERMES_HOME; got {result!r}"
        )

    def test_cron_add_profile_does_not_redirect_hermes_home(
        self, tmp_path, monkeypatch
    ):
        result = self._run(
            tmp_path,
            monkeypatch,
            argv=["hermes", "cron", "add", "--prompt", "hi", "--schedule", "daily", "--profile", "support"],
        )
        assert result is None, (
            f"cron add --profile must not switch HERMES_HOME; got {result!r}"
        )

    def test_cron_edit_profile_does_not_redirect_hermes_home(
        self, tmp_path, monkeypatch
    ):
        result = self._run(
            tmp_path,
            monkeypatch,
            argv=["hermes", "cron", "edit", "abc123", "--profile", "support"],
        )
        assert result is None, (
            f"cron edit --profile must not switch HERMES_HOME; got {result!r}"
        )

    def test_top_level_profile_flag_still_redirects_hermes_home(
        self, tmp_path, monkeypatch
    ):
        """Sanity check: hermes --profile support cron list should still redirect."""
        result = self._run(
            tmp_path,
            monkeypatch,
            argv=["hermes", "--profile", "support", "cron", "list"],
        )
        assert result is not None and "support" in result, (
            f"Top-level --profile must still redirect HERMES_HOME; got {result!r}"
        )

    def test_cron_create_with_profile_flag_profile_name_left_in_argv(
        self, tmp_path, monkeypatch
    ):
        """After _apply_profile_override runs, --profile <name> must remain in sys.argv
        so argparse can pick it up as the job's profile field."""
        hermes_root = tmp_path / ".hermes"
        hermes_root.mkdir(parents=True, exist_ok=True)
        (hermes_root / "profiles" / "support").mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        argv_orig = ["hermes", "cron", "create", "--prompt", "hi", "--schedule", "daily", "--profile", "support"]
        monkeypatch.setattr(sys, "argv", list(argv_orig))

        from hermes_cli.main import _apply_profile_override
        _apply_profile_override()

        assert "--profile" in sys.argv, "--profile must remain in sys.argv for argparse"
        assert "support" in sys.argv, "profile name must remain in sys.argv for argparse"

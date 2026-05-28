"""Tests for CLI /agents and /tasks commands (bug #32477).

Verifies that both commands are registered, alias-resolved, dispatched, and
produce output — since the bug report claimed no output and no debug log entry.
"""

from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli() -> HermesCLI:
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = "sess-agents-test"
    cli_obj._pending_input = MagicMock()
    cli_obj._app = None
    cli_obj._agent_running = False
    return cli_obj


def _run_cmd(cli_obj: HermesCLI, cmd: str) -> list[str]:
    """Run a command and capture all _cprint output lines."""
    output: list[str] = []
    with patch("cli._cprint", side_effect=lambda x: output.append(x)):
        with patch("tools.process_registry.process_registry") as mock_reg:
            mock_reg.list_sessions.return_value = []
            cli_obj.process_command(cmd)
    return output


def test_agents_command_produces_output():
    """``/agents`` emits at least one line (running-processes count)."""
    cli_obj = _make_cli()
    output = _run_cmd(cli_obj, "/agents")
    assert output, "/agents produced no output"


def test_tasks_alias_resolves_to_agents():
    """``/tasks`` is an alias of ``/agents`` and must produce identical output."""
    cli_obj_a = _make_cli()
    cli_obj_t = _make_cli()

    output_agents = _run_cmd(cli_obj_a, "/agents")
    output_tasks = _run_cmd(cli_obj_t, "/tasks")

    # Both should produce the same number of lines with the same content.
    assert output_agents == output_tasks, (
        f"/tasks output differed from /agents output.\n"
        f"/agents: {output_agents}\n/tasks:  {output_tasks}"
    )


def test_agents_command_shows_running_count_when_empty():
    """/agents shows '0' running processes when the registry is empty."""
    cli_obj = _make_cli()
    output = _run_cmd(cli_obj, "/agents")
    combined = " ".join(output)
    assert "0" in combined, f"Expected '0' in output, got: {combined}"


def test_agents_command_shows_running_process():
    """/agents lists a running process when one exists in the registry."""
    cli_obj = _make_cli()
    output: list[str] = []
    with patch("cli._cprint", side_effect=lambda x: output.append(x)):
        with patch("tools.process_registry.process_registry") as mock_reg:
            mock_reg.list_sessions.return_value = [
                {
                    "session_id": "bg-001",
                    "status": "running",
                    "command": "run something",
                    "uptime_seconds": 42,
                }
            ]
            with patch(
                "tools.process_registry.format_uptime_short",
                return_value="42s",
            ):
                cli_obj.process_command("/agents")

    combined = " ".join(output)
    assert "bg-001" in combined, f"Expected session id 'bg-001' in output, got: {combined}"


def test_agents_command_shows_agent_idle_status():
    """/agents reports the agent as idle when not running."""
    cli_obj = _make_cli()
    cli_obj._agent_running = False
    output = _run_cmd(cli_obj, "/agents")
    combined = " ".join(output)
    assert "idle" in combined, f"Expected 'idle' in output, got: {combined}"


def test_agents_command_shows_agent_running_status():
    """/agents reports the agent as running when active."""
    cli_obj = _make_cli()
    cli_obj._agent_running = True
    output = _run_cmd(cli_obj, "/agents")
    combined = " ".join(output)
    assert "running" in combined, f"Expected 'running' in output, got: {combined}"


def test_tasks_command_produces_output_with_active_agent():
    """``/tasks`` returns non-empty output when the agent is set."""
    cli_obj = _make_cli()
    cli_obj._agent_running = True
    output = _run_cmd(cli_obj, "/tasks")
    assert output, "/tasks produced no output when agent is active"

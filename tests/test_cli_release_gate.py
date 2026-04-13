import importlib
import sqlite3
import subprocess
from types import SimpleNamespace


def test_release_gate_fails_on_schema_preflight(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    console_module = importlib.import_module("academic_agent_team.cli.console")

    def _raise_runtime_error(_db_path):
        raise RuntimeError("Detected legacy sessions.db schema missing columns")

    monkeypatch.setattr(console_module, "connect", _raise_runtime_error)

    rc = console_module.main(["release-gate", "--skip-smoke", "--skip-regression"])
    assert rc == 1


def test_release_gate_success_with_stubbed_smoke_and_regression(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    console_module = importlib.import_module("academic_agent_team.cli.console")
    monkeypatch.setattr(console_module, "connect", lambda _db_path: sqlite3.connect(":memory:"))

    async def _fake_run_pipeline_v2(*args, **kwargs):
        del args, kwargs
        return SimpleNamespace(session_id="v2-session-id")

    monkeypatch.setattr(console_module, "run_pipeline_v2", _fake_run_pipeline_v2)
    monkeypatch.setattr(console_module, "run_mock_pipeline", lambda **kwargs: "legacy-session-id")

    recorded = {}

    def _fake_subprocess_run(cmd, cwd, text, capture_output):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd
        recorded["text"] = text
        recorded["capture_output"] = capture_output
        return subprocess.CompletedProcess(cmd, 0, stdout="3 passed", stderr="")

    monkeypatch.setattr(console_module.subprocess, "run", _fake_subprocess_run)

    rc = console_module.main(["release-gate"])
    assert rc == 0
    assert "tests" in recorded["cmd"]
    assert recorded["cwd"] == tmp_path


def test_release_gate_blocks_on_regression_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    console_module = importlib.import_module("academic_agent_team.cli.console")
    monkeypatch.setattr(console_module, "connect", lambda _db_path: sqlite3.connect(":memory:"))

    def _fake_subprocess_run(cmd, cwd, text, capture_output):
        del cmd, cwd, text, capture_output
        return subprocess.CompletedProcess(["pytest"], 1, stdout="1 failed", stderr="boom")

    monkeypatch.setattr(console_module.subprocess, "run", _fake_subprocess_run)

    rc = console_module.main(["release-gate", "--skip-smoke"])
    assert rc == 1

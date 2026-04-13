import sqlite3

from academic_agent_team.cli.console import main
from academic_agent_team.storage.db import get_session_summary, list_sessions


def _latest_session_id(db_path):
    conn = sqlite3.connect(db_path)
    rows = list_sessions(conn, limit=1)
    conn.close()
    assert rows, "no sessions persisted"
    return rows[0]["id"]


def test_cli_start_v2_autopilot_persists_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_DETECT_MOCK", "true")
    monkeypatch.setenv("CNKI_MOCK", "true")
    monkeypatch.setenv("CITATION_MOCK", "true")

    rc = main(
        [
            "start",
            "--mock",
            "--engine",
            "v2",
            "--mode",
            "autopilot",
            "--topic",
            "CLI v2 autopilot 测试",
            "--journal",
            "中文核心",
            "--no-interactive",
        ]
    )
    assert rc == 0

    db_path = tmp_path / "session_store" / "sessions.db"
    assert db_path.exists()

    session_id = _latest_session_id(db_path)
    conn = sqlite3.connect(db_path)
    summary = get_session_summary(conn, session_id)
    conn.close()

    assert summary["run_mode"] == "autopilot"
    assert summary["stage"] == "export"
    assert summary["status"] == "completed"
    assert summary["artifact_count"] >= 6
    assert summary["message_count"] >= 6


def test_cli_start_v2_manual_persists_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_DETECT_MOCK", "true")
    monkeypatch.setenv("CNKI_MOCK", "true")
    monkeypatch.setenv("CITATION_MOCK", "true")

    rc = main(
        [
            "start",
            "--mock",
            "--engine",
            "v2",
            "--mode",
            "manual",
            "--topic",
            "CLI v2 manual 测试",
            "--journal",
            "中文核心",
            "--no-interactive",
        ]
    )
    assert rc == 0

    db_path = tmp_path / "session_store" / "sessions.db"
    assert db_path.exists()

    session_id = _latest_session_id(db_path)
    conn = sqlite3.connect(db_path)
    summary = get_session_summary(conn, session_id)
    conn.close()

    assert summary["run_mode"] == "manual"
    assert summary["stage"] == "export"
    assert summary["status"] == "completed"
    assert summary["artifact_count"] >= 6
    assert summary["message_count"] >= 6

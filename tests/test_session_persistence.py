import sqlite3

from academic_agent_team.pipeline import run_mock_pipeline
from academic_agent_team.storage.db import get_session_summary


def test_run_mock_pipeline_persists_session(tmp_path):
    session_id = run_mock_pipeline(base_dir=tmp_path, topic="测试课题", journal="中文核心")

    db_path = tmp_path / "session_store" / "sessions.db"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    summary = get_session_summary(conn, session_id)
    conn.close()

    assert summary["status"] == "completed"
    assert summary["artifact_count"] >= 5
    assert summary["message_count"] >= 5

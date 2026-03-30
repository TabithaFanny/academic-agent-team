import sqlite3

from academic_agent_team.pipeline import run_mock_pipeline
from academic_agent_team.storage.db import get_session_summary


def test_cost_tracking_exists(tmp_path):
    session_id = run_mock_pipeline(base_dir=tmp_path, topic="测试", journal="中文核心")
    conn = sqlite3.connect(tmp_path / "session_store" / "sessions.db")
    summary = get_session_summary(conn, session_id)
    conn.close()

    assert summary["total_cost_cny"] == 0.0

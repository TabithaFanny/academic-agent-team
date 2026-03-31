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


def test_run_autogen_pipeline_persists_session(tmp_path):
    """AutoGen GraphFlow pipeline（mock 模式）正确持久化 session。"""
    import asyncio
    from academic_agent_team.pipeline_real import run_autogen_pipeline

    session_id = asyncio.run(run_autogen_pipeline(
        base_dir=tmp_path,
        topic="大模型在学术写作中的应用",
        journal="中文核心",
        use_mock=True,
        max_messages=10,
    ))

    db_path = tmp_path / "session_store" / "sessions.db"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    summary = get_session_summary(conn, session_id)
    conn.close()

    assert summary is not None
    # AutoGen team 流式运行，正常终止后 session 应完成
    assert summary["status"] in ("completed", "running")
    # 至少有一些 artifact（topic_done 或 literature_done）
    assert summary["artifact_count"] >= 1


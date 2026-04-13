import sqlite3

from academic_agent_team.storage.db import (
    connect,
    detect_missing_session_columns,
    migrate_legacy_sessions_schema,
)


def _create_legacy_sessions_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE sessions (
            id           TEXT PRIMARY KEY,
            topic        TEXT NOT NULL,
            journal_type TEXT NOT NULL DEFAULT '中文核心',
            language     TEXT NOT NULL DEFAULT 'zh',
            model_config TEXT,
            stage        TEXT NOT NULL DEFAULT 'topic',
            status       TEXT NOT NULL DEFAULT 'active',
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def test_detect_missing_columns_for_legacy_schema(tmp_path):
    db_path = tmp_path / "sessions.db"
    _create_legacy_sessions_db(db_path)
    conn = sqlite3.connect(db_path)
    missing = detect_missing_session_columns(conn)
    conn.close()
    assert missing == ["budget_cap_cny", "run_mode"]


def test_migrate_legacy_sessions_schema_then_connect_passes(tmp_path):
    db_path = tmp_path / "sessions.db"
    _create_legacy_sessions_db(db_path)

    conn = sqlite3.connect(db_path)
    applied = migrate_legacy_sessions_schema(conn)
    missing = detect_missing_session_columns(conn)
    conn.close()

    assert set(applied) == {"run_mode", "budget_cap_cny"}
    assert missing == []

    # connect() should pass once legacy schema is migrated
    conn2 = connect(db_path)
    conn2.close()

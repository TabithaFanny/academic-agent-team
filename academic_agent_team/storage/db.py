from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    topic        TEXT NOT NULL,
    journal_type TEXT NOT NULL DEFAULT '中文核心',
    language     TEXT NOT NULL DEFAULT 'zh',
    model_config TEXT,
    stage        TEXT NOT NULL DEFAULT 'topic',
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id                 TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES sessions(id),
    sender             TEXT NOT NULL,
    receiver           TEXT NOT NULL,
    stage              TEXT NOT NULL,
    content            TEXT NOT NULL,
    metadata           TEXT,
    is_human_interrupt BOOLEAN DEFAULT 0,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    stage         TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    content       TEXT NOT NULL,
    is_stale      BOOLEAN DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cost_log (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    agent         TEXT NOT NULL,
    model_id      TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_cny      REAL NOT NULL,
    stage         TEXT NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def create_session(
    conn: sqlite3.Connection,
    topic: str,
    journal_type: str,
    language: str,
    model_config: dict,
) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO sessions (id, topic, journal_type, language, model_config, stage, status)
        VALUES (?, ?, ?, ?, ?, 'topic', 'active')
        """,
        (session_id, topic, journal_type, language, json.dumps(model_config, ensure_ascii=False)),
    )
    conn.commit()
    return session_id


def update_session_stage(conn: sqlite3.Connection, session_id: str, stage: str, status: str = "active") -> None:
    conn.execute(
        """
        UPDATE sessions
        SET stage = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (stage, status, session_id),
    )
    conn.commit()


def insert_message(
    conn: sqlite3.Connection,
    session_id: str,
    sender: str,
    receiver: str,
    stage: str,
    content: str,
    metadata: dict,
    is_human_interrupt: bool = False,
) -> None:
    conn.execute(
        """
        INSERT INTO messages (id, session_id, sender, receiver, stage, content, metadata, is_human_interrupt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            session_id,
            sender,
            receiver,
            stage,
            content,
            json.dumps(metadata, ensure_ascii=False),
            int(is_human_interrupt),
        ),
    )
    conn.commit()


def insert_artifact(
    conn: sqlite3.Connection,
    session_id: str,
    stage: str,
    artifact_type: str,
    content: str,
) -> None:
    conn.execute(
        """
        INSERT INTO artifacts (id, session_id, stage, artifact_type, content)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), session_id, stage, artifact_type, content),
    )
    conn.commit()


def insert_cost(
    conn: sqlite3.Connection,
    session_id: str,
    agent: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cost_cny: float,
    stage: str,
) -> None:
    conn.execute(
        """
        INSERT INTO cost_log (id, session_id, agent, model_id, input_tokens, output_tokens, cost_cny, stage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), session_id, agent, model_id, input_tokens, output_tokens, cost_cny, stage),
    )
    conn.commit()


def get_session_summary(conn: sqlite3.Connection, session_id: str) -> dict:
    row = conn.execute(
        "SELECT id, topic, journal_type, language, stage, status, created_at, updated_at FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"session not found: {session_id}")

    msg_count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?",
        (session_id,),
    ).fetchone()[0]
    artifact_count = conn.execute(
        "SELECT COUNT(*) FROM artifacts WHERE session_id = ?",
        (session_id,),
    ).fetchone()[0]
    total_cost = conn.execute(
        "SELECT COALESCE(SUM(cost_cny), 0.0) FROM cost_log WHERE session_id = ?",
        (session_id,),
    ).fetchone()[0]

    return {
        "id": row[0],
        "topic": row[1],
        "journal_type": row[2],
        "language": row[3],
        "stage": row[4],
        "status": row[5],
        "created_at": row[6],
        "updated_at": row[7],
        "message_count": msg_count,
        "artifact_count": artifact_count,
        "total_cost_cny": float(total_cost),
    }

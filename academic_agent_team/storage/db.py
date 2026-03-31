from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import sqlite3


SCHEMA_SQL = """
-- sessions 表
CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    topic        TEXT NOT NULL,
    journal_type TEXT NOT NULL DEFAULT '中文核心',
    language     TEXT NOT NULL DEFAULT 'zh',
    model_config TEXT,
    run_mode     TEXT NOT NULL DEFAULT 'autopilot',  -- autopilot|manual
    stage        TEXT NOT NULL DEFAULT 'topic',
    status       TEXT NOT NULL DEFAULT 'active',      -- active|paused|completed|failed
    budget_cap_cny REAL DEFAULT 35.0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- messages 表（每条 Agent/人类消息）
CREATE TABLE IF NOT EXISTS messages (
    id                 TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES sessions(id),
    sender             TEXT NOT NULL,         -- advisor|researcher|writer|reviewer|polisher|human
    receiver           TEXT NOT NULL,          -- 目标 agent 名称，或 "broadcast"
    stage              TEXT NOT NULL,
    content            TEXT NOT NULL,
    metadata           TEXT,                   -- JSON: {tokens, cost_cny, model_id, latency_ms}
    is_human_interrupt INTEGER DEFAULT 0,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- artifacts 表（每个 stage 的结构化产物）
CREATE TABLE IF NOT EXISTS artifacts (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    stage         TEXT NOT NULL,
    artifact_type TEXT NOT NULL,              -- topic_report|literature_matrix|section_draft|...
    content       TEXT NOT NULL,
    is_stale      INTEGER DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- versions 表（快照，用于 rollback/goto）
CREATE TABLE IF NOT EXISTS versions (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    stage        TEXT NOT NULL,
    version_num  INTEGER NOT NULL,
    full_content TEXT NOT NULL,                -- 当前阶段论文全文快照（Markdown）
    metadata     TEXT,                         -- JSON: {word_count, total_cost_cny, model_used_map}
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, stage, version_num)
);

-- raw_responses 表（LLM 原始输出，用于审计）
CREATE TABLE IF NOT EXISTS raw_responses (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    agent         TEXT NOT NULL,
    stage         TEXT NOT NULL,
    content       TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    model_id      TEXT,
    cost_cny      REAL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- cost_log 表（每笔 API 调用的费用）
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

-- 索引（PRD 7.8 规格）
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_session_stage ON artifacts(session_id, stage);
CREATE INDEX IF NOT EXISTS idx_versions_session ON versions(session_id, version_num);
CREATE INDEX IF NOT EXISTS idx_cost_session ON cost_log(session_id);
CREATE INDEX IF NOT EXISTS idx_raw_responses_session ON raw_responses(session_id);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA_SQL)
    # 旧 schema（缺列）不会被 CREATE TABLE IF NOT EXISTS 自动修复；此处做显式检测。
    required_session_cols = {"id", "topic", "journal_type", "language", "model_config", "run_mode", "stage", "status", "budget_cap_cny"}
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
    }
    missing_cols = required_session_cols - cols
    if missing_cols:
        raise RuntimeError(
            "Detected legacy sessions.db schema missing columns: "
            f"{sorted(missing_cols)}. "
            "Data migration strategy requires explicit approval; "
            "use a fresh DB path for now."
        )
    conn.commit()
    return conn


def create_session(
    conn: sqlite3.Connection,
    topic: str,
    journal_type: str,
    language: str,
    model_config: dict,
    run_mode: str = "autopilot",
    budget_cap_cny: float = 35.0,
) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO sessions
            (id, topic, journal_type, language, model_config, run_mode, stage, status, budget_cap_cny)
        VALUES (?, ?, ?, ?, ?, ?, 'topic', 'active', ?)
        """,
        (
            session_id,
            topic,
            journal_type,
            language,
            json.dumps(model_config, ensure_ascii=False),
            run_mode,
            budget_cap_cny,
        ),
    )
    conn.commit()
    return session_id


def update_session_stage(
    conn: sqlite3.Connection,
    session_id: str,
    stage: str,
    status: str = "active",
) -> None:
    conn.execute(
        """
        UPDATE sessions
        SET stage = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (stage, status, session_id),
    )
    conn.commit()


def update_session_run_mode(conn: sqlite3.Connection, session_id: str, run_mode: str) -> None:
    cur = conn.execute(
        "UPDATE sessions SET run_mode = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (run_mode, session_id),
    )
    if cur.rowcount == 0:
        raise KeyError(f"session not found: {session_id}")
    conn.commit()


def update_session_model_config(
    conn: sqlite3.Connection,
    session_id: str,
    model_config: dict,
) -> None:
    cur = conn.execute(
        """
        UPDATE sessions
        SET model_config = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (json.dumps(model_config, ensure_ascii=False), session_id),
    )
    if cur.rowcount == 0:
        raise KeyError(f"session not found: {session_id}")
    conn.commit()


def insert_message(
    conn: sqlite3.Connection,
    session_id: str,
    sender: str,
    receiver: str,
    stage: str,
    content: str,
    metadata: dict | None = None,
    is_human_interrupt: bool = False,
) -> str:
    msg_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO messages
            (id, session_id, sender, receiver, stage, content, metadata, is_human_interrupt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            msg_id,
            session_id,
            sender,
            receiver,
            stage,
            content,
            json.dumps(metadata or {}, ensure_ascii=False),
            int(is_human_interrupt),
        ),
    )
    conn.commit()
    return msg_id


def insert_artifact(
    conn: sqlite3.Connection,
    session_id: str,
    stage: str,
    artifact_type: str,
    content: str,
    is_stale: bool = False,
) -> str:
    art_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO artifacts (id, session_id, stage, artifact_type, content, is_stale)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (art_id, session_id, stage, artifact_type, content, int(is_stale)),
    )
    conn.commit()
    return art_id


def mark_artifacts_stale_from_stage(
    conn: sqlite3.Connection, session_id: str, from_stage: str
) -> None:
    """Mark all artifacts from from_stage onwards as stale (used after goto/rollback)."""
    STAGE_ORDER = [
        "topic_done",
        "literature_done",
        "writing_done",
        "review_done",
        "polish_done",
        "export",
    ]
    stage_aliases = {
        "topic": "topic_done",
        "literature": "literature_done",
        "writing": "writing_done",
        "review": "review_done",
        "polish": "polish_done",
    }
    normalized_stage = stage_aliases.get(from_stage, from_stage)
    try:
        idx = STAGE_ORDER.index(normalized_stage)
    except ValueError:
        idx = 0
    stale_stages = STAGE_ORDER[idx:]
    placeholders = ",".join("?" * len(stale_stages))
    conn.execute(
        f"UPDATE artifacts SET is_stale = 1 WHERE session_id = ? AND stage IN ({placeholders})",
        [session_id] + stale_stages,
    )
    conn.commit()


def insert_version(
    conn: sqlite3.Connection,
    session_id: str,
    stage: str,
    full_content: str,
    metadata: dict,
) -> str:
    """Insert a new version snapshot. Increments version_num for this (session_id, stage)."""
    # Get next version number
    row = conn.execute(
        "SELECT COALESCE(MAX(version_num), 0) FROM versions WHERE session_id = ? AND stage = ?",
        (session_id, stage),
    ).fetchone()
    next_num = (row[0] or 0) + 1

    version_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO versions (id, session_id, stage, version_num, full_content, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            session_id,
            stage,
            next_num,
            full_content,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    conn.commit()
    return version_id


def get_latest_version(
    conn: sqlite3.Connection, session_id: str, stage: str
) -> dict | None:
    row = conn.execute(
        """
        SELECT id, stage, version_num, full_content, metadata, created_at
        FROM versions
        WHERE session_id = ? AND stage = ?
        ORDER BY version_num DESC
        LIMIT 1
        """,
        (session_id, stage),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "stage": row[1],
        "version_num": row[2],
        "full_content": row[3],
        "metadata": json.loads(row[4]) if row[4] else {},
        "created_at": row[5],
    }


def get_all_versions(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, stage, version_num, full_content, metadata, created_at
        FROM versions
        WHERE session_id = ?
        ORDER BY version_num ASC
        """,
        (session_id,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "stage": r[1],
            "version_num": r[2],
            "full_content": r[3],
            "metadata": json.loads(r[4]) if r[4] else {},
            "created_at": r[5],
        }
        for r in rows
    ]


def insert_raw_response(
    conn: sqlite3.Connection,
    session_id: str,
    agent: str,
    stage: str,
    content: str,
    model_id: str | None = None,
    cost_cny: float | None = None,
) -> str:
    """Store raw LLM response with SHA256 for audit trail."""
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    resp_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO raw_responses (id, session_id, agent, stage, content, content_sha256, model_id, cost_cny)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (resp_id, session_id, agent, stage, content, sha, model_id, cost_cny),
    )
    conn.commit()
    return resp_id


def insert_cost(
    conn: sqlite3.Connection,
    session_id: str,
    agent: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cost_cny: float,
    stage: str,
) -> str:
    cost_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO cost_log (id, session_id, agent, model_id, input_tokens, output_tokens, cost_cny, stage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cost_id, session_id, agent, model_id, input_tokens, output_tokens, cost_cny, stage),
    )
    conn.commit()
    return cost_id


def get_session_summary(conn: sqlite3.Connection, session_id: str) -> dict:
    row = conn.execute(
        """
        SELECT id, topic, journal_type, language, run_mode, stage, status,
               budget_cap_cny, created_at, updated_at
        FROM sessions WHERE id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"session not found: {session_id}")

    msg_count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    artifact_count = conn.execute(
        "SELECT COUNT(*) FROM artifacts WHERE session_id = ?", (session_id,)
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
        "run_mode": row[4],
        "stage": row[5],
        "status": row[6],
        "budget_cap_cny": row[7],
        "created_at": row[8],
        "updated_at": row[9],
        "message_count": msg_count,
        "artifact_count": artifact_count,
        "total_cost_cny": float(total_cost),
    }


def list_sessions(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, topic, journal_type, run_mode, stage, status, created_at, updated_at
        FROM sessions
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "topic": r[1],
            "journal_type": r[2],
            "run_mode": r[3],
            "stage": r[4],
            "status": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }
        for r in rows
    ]

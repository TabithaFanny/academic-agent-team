from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path


# ─── Schema ────────────────────────────────────────────────────────────────────
# 对齐 PRD Section 7.8
SCHEMA_SQL = """
-- sessions 表：新增 run_mode 列（兼容旧 DB，用 ALTER TABLE）
CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    topic        TEXT NOT NULL,
    journal_type TEXT NOT NULL DEFAULT '中文核心',
    language     TEXT NOT NULL DEFAULT 'zh',
    model_config TEXT,
    run_mode     TEXT NOT NULL DEFAULT 'autopilot',
    stage        TEXT NOT NULL DEFAULT 'topic',
    status       TEXT NOT NULL DEFAULT 'active',
    budget_cap_cny REAL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- messages 表：新增 content_sha256 列
CREATE TABLE IF NOT EXISTS messages (
    id                 TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES sessions(id),
    sender             TEXT NOT NULL,
    receiver           TEXT NOT NULL,
    stage              TEXT NOT NULL,
    content            TEXT NOT NULL,
    content_sha256     TEXT,
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

-- versions 表：快照（PRD 7.8 新增，支撑 goto/rollback/resume）
CREATE TABLE IF NOT EXISTS versions (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    stage         TEXT NOT NULL,
    version_num   INTEGER NOT NULL,
    full_content  TEXT NOT NULL,
    metadata      TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- raw_responses 表：原始 LLM 响应（PRD 7.8 新增，含 sha256 防篡改）
CREATE TABLE IF NOT EXISTS raw_responses (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    agent         TEXT NOT NULL,
    stage         TEXT NOT NULL,
    content       TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
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

-- 索引（PRD 7.8，对齐生产性能要求）
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_versions_session   ON versions(session_id, version_num);
CREATE UNIQUE INDEX  IF NOT EXISTS uniq_versions_stage
    ON versions(session_id, stage, version_num);
CREATE INDEX IF NOT EXISTS idx_raw_responses_session ON raw_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_session ON cost_log(session_id);
"""

# migration 用于旧 DB 已有 sessions 表时追加新列
MIGRATION_SQL = """
ALTER TABLE sessions ADD COLUMN run_mode TEXT NOT NULL DEFAULT 'autopilot';
ALTER TABLE sessions ADD COLUMN budget_cap_cny REAL;
ALTER TABLE messages ADD COLUMN content_sha256 TEXT;
"""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _connect_raw(db_path: Path) -> sqlite3.Connection:
    """内部：创建连接但不执行 schema（用于 migration）。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def connect(db_path: Path) -> sqlite3.Connection:
    """连接 DB，执行 schema 初始化和 migration。"""
    conn = _connect_raw(db_path)

    # 建表 + 索引
    conn.executescript(SCHEMA_SQL)

    # 迁移旧 DB（如果 sessions 表已存在但缺列）
    existing_cols = {
        r[1]
        for r in conn.execute(
            "PRAGMA table_info(sessions)"
        ).fetchall()
    }
    if "run_mode" not in existing_cols:
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN run_mode TEXT NOT NULL DEFAULT 'autopilot'")
        except sqlite3.OperationalError:
            pass  # 已有该列
    if "budget_cap_cny" not in existing_cols:
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN budget_cap_cny REAL")
        except sqlite3.OperationalError:
            pass
    existing_msg_cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()}
    if "content_sha256" not in existing_msg_cols:
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN content_sha256 TEXT")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    return conn


# ─── Sessions ─────────────────────────────────────────────────────────────────

def create_session(
    conn: sqlite3.Connection,
    topic: str,
    journal_type: str,
    language: str,
    model_config: dict,
    run_mode: str = "autopilot",
    budget_cap_cny: float | None = None,
) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO sessions (id, topic, journal_type, language, model_config,
                              run_mode, budget_cap_cny, stage, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'topic', 'active')
        """,
        (
            session_id, topic, journal_type, language,
            json.dumps(model_config, ensure_ascii=False),
            run_mode, budget_cap_cny,
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
        "UPDATE sessions SET stage = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (stage, status, session_id),
    )
    conn.commit()


def update_session_run_mode(conn: sqlite3.Connection, session_id: str, run_mode: str) -> None:
    conn.execute(
        "UPDATE sessions SET run_mode = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (run_mode, session_id),
    )
    conn.commit()


def get_session(conn: sqlite3.Connection, session_id: str) -> dict | None:
    row = conn.execute(
        """SELECT id, topic, journal_type, language, model_config, run_mode,
                  stage, status, budget_cap_cny, created_at, updated_at
           FROM sessions WHERE id = ?""",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    cols = ["id","topic","journal_type","language","model_config","run_mode",
            "stage","status","budget_cap_cny","created_at","updated_at"]
    result = dict(zip(cols, row))
    if result["model_config"]:
        result["model_config"] = json.loads(result["model_config"])
    return result


# ─── Messages ─────────────────────────────────────────────────────────────────

def insert_message(
    conn: sqlite3.Connection,
    session_id: str,
    sender: str,
    receiver: str,
    stage: str,
    content: str,
    metadata: dict,
    is_human_interrupt: bool = False,
) -> str:
    msg_id = str(uuid.uuid4())
    sha = _sha256(content)
    conn.execute(
        """
        INSERT INTO messages (id, session_id, sender, receiver, stage,
                              content, content_sha256, metadata, is_human_interrupt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            msg_id, session_id, sender, receiver, stage,
            content, sha,
            json.dumps(metadata, ensure_ascii=False),
            int(is_human_interrupt),
        ),
    )
    conn.commit()
    return msg_id


def get_messages(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, sender, receiver, stage, content, metadata, is_human_interrupt, created_at "
        "FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    cols = ["id","sender","receiver","stage","content","metadata","is_human_interrupt","created_at"]
    result = []
    for row in rows:
        d = dict(zip(cols, row))
        d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
        d["is_human_interrupt"] = bool(d["is_human_interrupt"])
        result.append(d)
    return result


# ─── Artifacts ────────────────────────────────────────────────────────────────

def insert_artifact(
    conn: sqlite3.Connection,
    session_id: str,
    stage: str,
    artifact_type: str,
    content: str,
) -> str:
    art_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO artifacts (id, session_id, stage, artifact_type, content) VALUES (?, ?, ?, ?, ?)",
        (art_id, session_id, stage, artifact_type, content),
    )
    conn.commit()
    return art_id


def mark_artifacts_stale(conn: sqlite3.Connection, session_id: str, stage: str) -> int:
    """将 session_id 中 stage 之后的所有 artifacts 标记为 stale。"""
    cursor = conn.execute(
        "UPDATE artifacts SET is_stale = 1 "
        "WHERE session_id = ? AND stage >= ? AND is_stale = 0",
        (session_id, stage),
    )
    conn.commit()
    return cursor.rowcount


def mark_artifacts_stale_from_stage(conn: sqlite3.Connection, session_id: str, from_stage: str) -> None:
    """
    按 STAGE_ORDER 将 from_stage 及之后阶段的所有 artifacts 标记为 stale。
    用于 goto/rollback 后的一致性清理。
    """
    STAGE_ORDER = ("topic", "literature", "writing", "review", "polish", "export")
    try:
        idx = STAGE_ORDER.index(from_stage)
    except ValueError:
        idx = 0
    stale_stages = STAGE_ORDER[idx:]
    placeholders = ",".join("?" * len(stale_stages))
    conn.execute(
        f"UPDATE artifacts SET is_stale = 1 WHERE session_id = ? AND stage IN ({placeholders})",
        [session_id] + list(stale_stages),
    )
    conn.commit()


def get_latest_artifact(
    conn: sqlite3.Connection, session_id: str, stage: str
) -> dict | None:
    row = conn.execute(
        "SELECT id, artifact_type, content, is_stale, created_at "
        "FROM artifacts WHERE session_id = ? AND stage = ? ORDER BY created_at DESC LIMIT 1",
        (session_id, stage),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(["id","artifact_type","content","is_stale","created_at"], row))


# ─── Versions ─────────────────────────────────────────────────────────────────

def insert_version(
    conn: sqlite3.Connection,
    session_id: str,
    stage: str,
    full_content: str,
    metadata: dict,
) -> tuple[str, int]:
    """插入快照，返回 (version_id, version_num)。"""
    # 获取当前最大 version_num
    row = conn.execute(
        "SELECT COALESCE(MAX(version_num), 0) FROM versions WHERE session_id = ? AND stage = ?",
        (session_id, stage),
    ).fetchone()
    version_num = (row[0] or 0) + 1

    vid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO versions (id, session_id, stage, version_num, full_content, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (vid, session_id, stage, version_num, full_content, json.dumps(metadata, ensure_ascii=False)),
    )
    conn.commit()
    return vid, version_num


def get_version(
    conn: sqlite3.Connection, session_id: str, stage: str, version_num: int
) -> dict | None:
    row = conn.execute(
        "SELECT id, full_content, metadata, created_at FROM versions "
        "WHERE session_id = ? AND stage = ? AND version_num = ?",
        (session_id, stage, version_num),
    ).fetchone()
    if row is None:
        return None
    d = dict(zip(["id","full_content","metadata","created_at"], row))
    d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
    return d


def get_all_versions(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, stage, version_num, metadata, created_at FROM versions "
        "WHERE session_id = ? ORDER BY stage, version_num",
        (session_id,),
    ).fetchall()
    cols = ["id","stage","version_num","metadata","created_at"]
    result = []
    for row in rows:
        d = dict(zip(cols, row))
        d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
        result.append(d)
    return result


# ─── Raw Responses ────────────────────────────────────────────────────────────

def insert_raw_response(
    conn: sqlite3.Connection,
    session_id: str,
    agent: str,
    stage: str,
    content: str,
    model_id: str | None = None,
    cost_cny: float | None = None,
) -> str:
    rid = str(uuid.uuid4())
    sha = _sha256(content)
    conn.execute(
        "INSERT INTO raw_responses (id, session_id, agent, stage, content, content_sha256) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (rid, session_id, agent, stage, content, sha),
    )
    conn.commit()
    return rid


def verify_raw_response(conn: sqlite3.Connection, response_id: str) -> bool:
    row = conn.execute(
        "SELECT content, content_sha256 FROM raw_responses WHERE id = ?",
        (response_id,),
    ).fetchone()
    if row is None:
        return False
    return _sha256(row[0]) == row[1]


# ─── Cost ─────────────────────────────────────────────────────────────────────

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
    cid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO cost_log (id, session_id, agent, model_id, input_tokens, output_tokens, cost_cny, stage) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (cid, session_id, agent, model_id, input_tokens, output_tokens, cost_cny, stage),
    )
    conn.commit()
    return cid


def get_session_cost_summary(conn: sqlite3.Connection, session_id: str) -> dict:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_cny), 0.0), COUNT(*) FROM cost_log WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    by_agent = conn.execute(
        "SELECT agent, SUM(cost_cny), SUM(input_tokens), SUM(output_tokens) "
        "FROM cost_log WHERE session_id = ? GROUP BY agent",
        (session_id,),
    ).fetchall()
    return {
        "total_cny": round(float(row[0]), 6),
        "call_count": row[1],
        "by_agent": {
            r[0]: {"cost_cny": round(float(r[1]), 6), "input_tokens": r[2], "output_tokens": r[3]}
            for r in by_agent
        },
    }


def get_latest_version(conn: sqlite3.Connection, session_id: str, stage: str) -> dict | None:
    """获取指定 stage 的最新版本快照。"""
    row = conn.execute(
        "SELECT id, full_content, metadata, version_num, created_at "
        "FROM versions WHERE session_id = ? AND stage = ? ORDER BY version_num DESC LIMIT 1",
        (session_id, stage),
    ).fetchone()
    if row is None:
        return None
    d = dict(zip(["id", "full_content", "metadata", "version_num", "created_at"], row))
    d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
    return d


# ─── Summary ──────────────────────────────────────────────────────────────────

def list_sessions(
    conn: sqlite3.Connection,
    limit: int = 50,
    status: str | None = None,
) -> list[dict]:
    """列出 sessions，支持按 status 过滤。"""
    if status:
        rows = conn.execute(
            """SELECT id, topic, journal_type, language, run_mode, stage, status,
                      budget_cap_cny, created_at, updated_at
               FROM sessions WHERE status = ? ORDER BY updated_at DESC LIMIT ?""",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, topic, journal_type, language, run_mode, stage, status,
                      budget_cap_cny, created_at, updated_at
               FROM sessions ORDER BY updated_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    cols = ["id", "topic", "journal_type", "language", "run_mode",
            "stage", "status", "budget_cap_cny", "created_at", "updated_at"]
    return [dict(zip(cols, row)) for row in rows]


def get_session_summary(conn: sqlite3.Connection, session_id: str) -> dict:
    row = conn.execute(
        """SELECT id, topic, journal_type, language, run_mode, stage, status,
                  budget_cap_cny, created_at, updated_at
           FROM sessions WHERE id = ?""",
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
    version_count = conn.execute(
        "SELECT COUNT(*) FROM versions WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    cost_row = conn.execute(
        "SELECT COALESCE(SUM(cost_cny), 0.0) FROM cost_log WHERE session_id = ?",
        (session_id,),
    ).fetchone()

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
        "version_count": version_count,
        "total_cost_cny": float(cost_row[0]),
    }

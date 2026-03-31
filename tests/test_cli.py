"""
tests/test_cli.py

验证 CLI 命令行接口：
- paper-team start --mock → 成功（legacy mock pipeline）
- paper-team start --real --engine autogen --mock → 成功（AutoGen pipeline，mock 模式）
- paper-team list/status/cost 等辅助命令
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from academic_agent_team.cli.console import build_parser, main
from academic_agent_team.storage.db import get_session_summary


def _isolate_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    隔离 CLI 的 DB 路径：
    - patch console._db_path() 使其返回隔离的 db_path
    - patch Path.cwd() 使 run_mock_pipeline 使用相同路径

    返回隔离后的 db_path。
    """
    from academic_agent_team.cli import console
    db_path = tmp_path / "session_store" / "sessions.db"
    # patch _db_path 返回隔离路径
    monkeypatch.setattr(console, "_db_path", lambda _: db_path)
    # patch Path.cwd 使返回 tmp_path（避免 /var ↔ /private/var symlink 差异）
    # 注意：tmp_path 本身不被 resolve，以匹配 Path.cwd() 在 os.chdir 后的行为
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    return db_path


def test_start_mock_creates_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """paper-team start --mock 创建 session 并写入 DB。"""
    db_path = _isolate_db(tmp_path, monkeypatch)

    exit_code = main(["start", "--mock", "--topic", "测试课题", "--journal", "中文核心"])
    assert exit_code == 0

    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, topic, status FROM sessions").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][1] == "测试课题"
    assert rows[0][2] == "completed"


def test_start_autogen_mock_creates_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """paper-team start --mock --engine autogen 使用 AutoGen GraphFlow mock 运行。"""
    db_path = _isolate_db(tmp_path, monkeypatch)

    exit_code = main([
        "start",
        "--mock",
        "--engine", "autogen",
        "--topic", "大模型在学术写作中的应用",
        "--journal", "IEEE Trans",
    ])
    assert exit_code == 0

    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, topic, status FROM sessions").fetchall()
    conn.close()
    assert len(rows) == 1
    session_id = rows[0][0]
    summary = get_session_summary(sqlite3.connect(db_path), session_id)
    assert summary["status"] in ("completed", "running")


def test_list_shows_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """paper-team list 在有 session 时列出记录。"""
    _isolate_db(tmp_path, monkeypatch)
    main(["start", "--mock", "--topic", "测试", "--journal", "中文核心"])

    exit_code = main(["list"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "测试" in out


def test_status_shows_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """paper-team status 显示 session 摘要。"""
    db_path = _isolate_db(tmp_path, monkeypatch)
    main(["start", "--mock", "--topic", "测试状态", "--journal", "CCF-A"])

    conn = sqlite3.connect(db_path)
    session_id = conn.execute("SELECT id FROM sessions LIMIT 1").fetchone()[0]
    conn.close()

    exit_code = main(["status", session_id])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Session:" in out
    assert "测试状态" in out


def test_status_unknown_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """paper-team status 对未知 session 返回非零。"""
    _isolate_db(tmp_path, monkeypatch)
    exit_code = main(["status", "00000000-0000-0000-0000-000000000000"])
    assert exit_code == 1


def test_role_show_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """paper-team role show 显示默认角色配置。"""
    _isolate_db(tmp_path, monkeypatch)
    exit_code = main(["role", "show"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "advisor" in out
    assert "researcher" in out


def test_start_real_without_key_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """paper-team start --real 无 API key 时正确报错（非阻塞式）。"""
    _isolate_db(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    exit_code = main(["start", "--real", "--engine", "sequential", "--topic", "测试", "--journal", "中文核心"])
    assert exit_code == 1
    out = capsys.readouterr().err
    assert "API key" in out


def test_start_real_autogen_uses_mock_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """paper-team start --real --engine autogen 无 API key 时自动降级到 MockClient，成功完成。"""
    db_path = _isolate_db(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    # AutoGen pipeline fallback 到 mock，全程无需真实 API key
    exit_code = main(["start", "--real", "--engine", "autogen", "--topic", "测试", "--journal", "中文核心"])
    assert exit_code == 0

    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, topic, status FROM sessions").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][1] == "测试"


def test_list_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """paper-team list 在 DB 存在但无 session 时提示空列表。"""
    db_path = _isolate_db(tmp_path, monkeypatch)
    # 通过 connect() 初始化 schema（确保 DB 和表结构存在，但无任何 session）
    from academic_agent_team.storage.db import connect
    conn = connect(db_path)
    conn.close()
    exit_code = main(["list"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "No sessions found" in out


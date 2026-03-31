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


def _isolate_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    隔离 CLI 的 DB 路径：让 _db_path() 使用 tmp_path 而非 cwd。
    原因：macOS 上 /var/folders ↔ /private/var/folders symlink 导致
    monkeypatch.chdir(tmp_path) 后 Path.cwd() 返回未归一化的路径，
    与 tmp_path 对象不相等（/var ≠ /private/var）。
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SESSION_DB", str(tmp_path / "session_store" / "sessions.db"))


def test_start_mock_creates_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """paper-team start --mock 创建 session 并写入 DB。"""
    _isolate_db(tmp_path, monkeypatch)

    exit_code = main(["start", "--mock", "--topic", "测试课题", "--journal", "中文核心"])
    assert exit_code == 0

    db_path = tmp_path / "session_store" / "sessions.db"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, topic, status FROM sessions").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][1] == "测试课题"
    assert rows[0][2] == "completed"


def test_start_autogen_mock_creates_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """paper-team start --mock --engine autogen 使用 AutoGen GraphFlow mock 运行。"""
    _isolate_db(tmp_path, monkeypatch)

    exit_code = main([
        "start",
        "--mock",
        "--engine", "autogen",
        "--topic", "大模型在学术写作中的应用",
        "--journal", "IEEE Trans",
    ])
    assert exit_code == 0

    db_path = tmp_path / "session_store" / "sessions.db"
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
    _isolate_db(tmp_path, monkeypatch)
    main(["start", "--mock", "--topic", "测试状态", "--journal", "CCF-A"])

    db_path = tmp_path / "session_store" / "sessions.db"
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


from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from academic_agent_team.pipeline import run_mock_pipeline
from academic_agent_team.session_logger import SessionLogger
from academic_agent_team.storage.db import get_session_summary


def _session_db_path(base_dir: Path) -> Path:
    env_path = base_dir / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key.strip() == "SESSION_DB":
                return (base_dir / val.strip()).resolve()
    return (base_dir / "session_store" / "sessions.db").resolve()


def _cmd_start(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    if not args.mock:
        print("Only --mock mode is implemented in this MVP scaffold.", file=sys.stderr)
        return 2

    topic = args.topic or "测试课题"
    journal = args.journal or "中文核心"
    session_id = run_mock_pipeline(base_dir=base_dir, topic=topic, journal=journal)
    print(f"Session started and completed in mock mode: {session_id}")
    print(f"Output directory: {base_dir / 'output' / session_id}")
    return 0


def _cmd_debug(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    db_path = _session_db_path(base_dir)
    if not db_path.exists():
        print(f"Session DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    try:
        summary = get_session_summary(conn, args.session_id)
    except KeyError:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        conn.close()
        return 1

    log_path = base_dir / "session_store" / "logs" / f"{args.session_id}.log"
    logger = SessionLogger(log_path)
    tail_events = list(logger.tail(limit=5))
    conn.close()

    print("Session Summary")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Recent Events")
    print(json.dumps(tail_events, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-team")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Run a new session")
    start.add_argument("--mock", action="store_true", help="Run with mock LLM calls")
    start.add_argument("--topic", help="Research topic")
    start.add_argument("--journal", help="Target journal")
    start.add_argument("--no-interactive", action="store_true", help="Compatibility flag")
    start.set_defaults(func=_cmd_start)

    debug = sub.add_parser("debug", help="Show session debug summary")
    debug.add_argument("session_id", help="Session ID")
    debug.set_defaults(func=_cmd_debug)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

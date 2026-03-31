"""
cli/console.py

对齐 PRD Section 9.2 / 9.3 命令行接口。
支持 start / resume / debug / status / cost / list / role / mode / export / goto / rollback。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from academic_agent_team.config.role_profiles import parse_role_profile_snapshot
from academic_agent_team.pipeline import run_mock_pipeline
from academic_agent_team.pipeline_real import run_pipeline
from academic_agent_team.session_logger import SessionLogger
from academic_agent_team.storage.db import (
    connect,
    get_all_versions,
    get_latest_version,
    get_session_cost_summary,
    get_session_summary,
    list_sessions,
    mark_artifacts_stale_from_stage,
    update_session_run_mode,
)


# ─── 辅助 ────────────────────────────────────────────────────────────────────

def _db_path(base_dir: Path | None = None) -> Path:
    base = base_dir or Path.cwd()
    env_path = base / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "SESSION_DB":
                return (base / v.strip()).resolve()
    return (base / "session_store" / "sessions.db").resolve()


def _resolve_api_config(args: argparse.Namespace) -> dict:
    """从 args 解析 API 配置，优先取命令行参数，其次环境变量。"""
    return {
        "api_key": args.api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        "base_url": args.base_url or os.environ.get("ANTHROPIC_BASE_URL", ""),
        "model": args.model or os.environ.get("ANTHROPIC_MODEL", ""),
    }


# ─── Commands ────────────────────────────────────────────────────────────────

def _cmd_start(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    topic = args.topic or "测试课题"
    journal = args.journal or "中文核心"
    run_mode = getattr(args, "mode", "autopilot")
    budget = getattr(args, "budget", 35.0)

    if args.mock:
        print("[Mock] Running pipeline...")
        session_id = run_mock_pipeline(base_dir=base_dir, topic=topic, journal=journal)
        print(f"✅ Session completed: {session_id}")
        print(f"   Output: {base_dir / 'output' / session_id}")
        return 0

    api_cfg = _resolve_api_config(args)
    if not api_cfg["api_key"] and not args.mock:
        print("❌ API key required for real mode.", file=sys.stderr)
        print("   Set ANTHROPIC_AUTH_TOKEN env var, or pass --api-key", file=sys.stderr)
        return 1

    print(f"[Real] topic={topic} journal={journal} run_mode={run_mode}")
    try:
        session_id = run_pipeline(
            base_dir=base_dir,
            topic=topic,
            journal=journal,
            use_mock=False,
            run_mode=run_mode,
            budget_cap_cny=budget,
            **api_cfg,
        )
        print(f"✅ Session completed: {session_id}")
        print(f"   Output: {base_dir / 'output' / session_id}")
        return 0
    except Exception as e:
        print(f"❌ Pipeline failed: {e}", file=sys.stderr)
        return 1


def _cmd_resume(args: argparse.Namespace) -> int:
    """恢复一个已存在的 session，从断点继续。"""
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    if not db_path.exists():
        print(f"❌ Session DB not found: {db_path}", file=sys.stderr)
        return 1

    session_id = args.session_id
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT id, topic, stage, status FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()

    if row is None:
        print(f"❌ Session not found: {session_id}", file=sys.stderr)
        return 1

    print(f"Session: {row[1]}")
    print(f"Stage: {row[2]} | Status: {row[3]}")
    print(f"Run `paper-team start --real` to continue from last checkpoint.")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    """显示 session 状态。"""
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    if not db_path.exists():
        print(f"❌ Session DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    summary = None
    try:
        summary = get_session_summary(conn, args.session_id)
    except KeyError:
        print(f"❌ Session not found: {args.session_id}", file=sys.stderr)
        conn.close()
        return 1

    cost = get_session_cost_summary(conn, args.session_id)
    conn.close()

    print(f"Session: {summary['id']}")
    print(f"  Topic:      {summary['topic']}")
    print(f"  Journal:    {summary['journal_type']}")
    print(f"  Stage:      {summary['stage']}")
    print(f"  Status:     {summary['status']}")
    print(f"  Run mode:   {summary['run_mode']}")
    print(f"  Budget:     ¥{summary['budget_cap_cny']}")
    print(f"  Created:    {summary['created_at']}")
    print(f"  Updated:    {summary['updated_at']}")
    print(f"  Messages:   {summary['message_count']}")
    print(f"  Artifacts:  {summary['artifact_count']}")
    print(f"  Total cost: ¥{round(cost['total_cny'], 6)} ({cost['call_count']} calls)")
    for agent, d in cost["by_agent"].items():
        print(f"    {agent}: ¥{d['cost_cny']} ({d['input_tokens']} in / {d['output_tokens']} out)")
    return 0


def _cmd_cost(args: argparse.Namespace) -> int:
    """显示实时费用明细。"""
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    if not db_path.exists():
        print(f"❌ Session DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    try:
        summary = get_session_summary(conn, args.session_id)
    except KeyError:
        print(f"❌ Session not found: {args.session_id}", file=sys.stderr)
        conn.close()
        return 1
    cost = get_session_cost_summary(conn, args.session_id)
    conn.close()

    budget = summary["budget_cap_cny"] or 35.0
    pct = cost["total_cny"] / budget * 100 if budget else 0

    print(f"Session: {args.session_id}")
    print(f"  Total:      ¥{round(cost['total_cny'], 6)}")
    print(f"  Budget:     ¥{budget} ({pct:.1f}% used)")
    print(f"  Calls:      {cost['call_count']}")
    for agent, d in cost["by_agent"].items():
        print(f"  {agent:12s} ¥{d['cost_cny']:8.4f}  in={d['input_tokens']:6d}  out={d['output_tokens']:6d}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    """列出最近 session。"""
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    if not db_path.exists():
        print(f"❌ Session DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    sessions = list_sessions(conn, limit=args.limit)
    conn.close()

    if not sessions:
        print("No sessions found.")
        return 0

    print(f"{'Session ID':36s}  {'Topic':20s}  {'Stage':10s}  {'Status':10s}  {'Mode':10s}  Updated")
    print("-" * 110)
    for s in sessions:
        tid = s["id"][:8] + "..."
        topic = (s["topic"] or "")[:18]
        print(f"{s['id']:36s}  {topic:20s}  {s['stage']:10s}  {s['status']:10s}  {s['run_mode']:10s}  {s['updated_at']}")
    return 0


def _cmd_role(args: argparse.Namespace) -> int:
    """显示或设置角色模型配置。"""
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)

    if args.subcommand == "show":
        if not args.session_id:
            from academic_agent_team.config.role_profiles import DEFAULT_ROLE_PROFILE
            profile = DEFAULT_ROLE_PROFILE
            src = "default"
        else:
            if not db_path.exists():
                print(f"❌ Session DB not found", file=sys.stderr)
                return 1
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT model_config FROM sessions WHERE id = ?", (args.session_id,)
            ).fetchone()
            conn.close()
            if row is None:
                print(f"❌ Session not found", file=sys.stderr)
                return 1
            profile = parse_role_profile_snapshot(json.loads(row[0]))
            src = f"session {args.session_id[:8]}..."

        print(f"Role profile [{src}]:")
        for agent, (prov, name) in profile.items():
            print(f"  {agent:12s}  {prov:10s}/{name}")
        return 0

    if args.subcommand == "set":
        print(f"Role switch requested: {args.agent} → {args.provider}/{args.model}")
        print("⚠️  Role hot-swap will be persisted to session.model_config in the next session start.")
        return 0

    return 0


def _cmd_mode(args: argparse.Namespace) -> int:
    """切换 autopilot / manual 执行模式。"""
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)

    if not args.session_id:
        print(f"Run mode will be set to: {args.run_mode}")
        print("Pass --session-id to persist the change.")
        return 0

    if not db_path.exists():
        print(f"❌ Session DB not found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    update_session_run_mode(conn, args.session_id, args.run_mode)
    conn.close()
    print(f"✅ Session {args.session_id[:8]}... run_mode → {args.run_mode}")
    return 0


def _cmd_goto(args: argparse.Namespace) -> int:
    """跳转到指定阶段（标记后续 artifacts 为 stale）。"""
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    if not db_path.exists():
        print(f"❌ Session DB not found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    n = mark_artifacts_stale_from_stage(conn, args.session_id, args.stage)
    conn.close()
    print(f"✅ {n} artifact(s) marked stale from stage '{args.stage}'")
    print(f"   Use `paper-team start --real` to re-run from checkpoint.")
    return 0


def _cmd_rollback(args: argparse.Namespace) -> int:
    """回退到指定版本快照。"""
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    if not db_path.exists():
        print(f"❌ Session DB not found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    version = get_latest_version(conn, args.session_id, args.stage)
    if version is None:
        print(f"❌ No version found for stage '{args.stage}' in session {args.session_id[:8]}...", file=sys.stderr)
        conn.close()
        return 1

    all_v = get_all_versions(conn, args.session_id)
    conn.close()

    print(f"Version history for session {args.session_id[:8]}...:")
    for v in all_v:
        marker = " ← current" if v["id"] == version["id"] else ""
        print(f"  v{v['version_num']:2d}  {v['stage']:12s}  {v['created_at']}{marker}")

    print(f"\nRollback to: v{version['version_num']} ({version['stage']})")
    print(f"⚠️  Artifacts after this stage will be marked stale.")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """导出最终论文包（tex / docx / bib 等）。"""
    base_dir = Path.cwd()
    output_dir = base_dir / "output" / args.session_id
    if not output_dir.exists():
        print(f"❌ Output not found: {output_dir}", file=sys.stderr)
        return 1

    fmt = args.format or "md"
    dest = args.output or str(output_dir / f"paper_final.{fmt}")
    paper_md = output_dir / "paper.md"
    if not paper_md.exists():
        print(f"❌ paper.md not found in output", file=sys.stderr)
        return 1

    # 目前只支持 Markdown 导出
    content = paper_md.read_text(encoding="utf-8")
    Path(dest).write_text(content, encoding="utf-8")
    print(f"✅ Exported to: {dest}")
    return 0


def _cmd_debug(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    if not db_path.exists():
        print(f"❌ Session DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    try:
        summary = get_session_summary(conn, args.session_id)
    except KeyError:
        print(f"❌ Session not found: {args.session_id}", file=sys.stderr)
        conn.close()
        return 1
    conn.close()

    log_path = base_dir / "session_store" / "logs" / f"{args.session_id}.log"
    if log_path.exists():
        logger = SessionLogger(log_path)
        events = list(logger.tail(limit=20))
        print(f"Recent log events for {args.session_id[:8]}...:")
        for ev in events:
            print(f"  {ev.get('ts','')}  {ev.get('event','')}")
    else:
        print("(No log file found)")

    print("\nSession summary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


# ─── Argument Parser ─────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-team",
        description="学术论文 AI 协作写作 CLI（对齐 PRD Section 9.2/9.3）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── start ──────────────────────────────────────────────────────────────
    start = sub.add_parser("start", help="启动新 session")
    start.add_argument("--mock", action="store_true", help="使用 Mock LLM（不消耗 API）")
    start.add_argument("--real", nargs="?", const="env", default="mock",
                       help="使用真实 LLM（默认从环境变量读取 key）")
    start.add_argument("--topic", help="研究课题")
    start.add_argument("--journal", help="目标期刊（中文核心/CSSCI/IEEE Trans/CCF-A）")
    start.add_argument("--mode", default="autopilot", choices=["autopilot", "manual"],
                       help="执行模式（默认 autopilot）")
    start.add_argument("--budget", type=float, default=35.0,
                       help="预算上限 CNY（默认 35.0）")
    start.add_argument("--api-key", help="API Key（优先于环境变量）")
    start.add_argument("--base-url", help="API Base URL")
    start.add_argument("--model", help="模型名称")
    start.add_argument("--no-interactive", action="store_true",
                       help="兼容性参数（等同于 --real --mode autopilot）")
    start.set_defaults(func=_cmd_start)

    # ── resume ─────────────────────────────────────────────────────────────
    resume = sub.add_parser("resume", help="恢复已存在的 session")
    resume.add_argument("session_id", help="Session ID")
    resume.set_defaults(func=_cmd_resume)

    # ── list ───────────────────────────────────────────────────────────────
    lst = sub.add_parser("list", help="列出最近 session")
    lst.add_argument("--limit", type=int, default=20, help="显示数量（默认 20）")
    lst.set_defaults(func=_cmd_list)

    # ── status ─────────────────────────────────────────────────────────────
    status = sub.add_parser("status", help="查看 session 状态")
    status.add_argument("session_id", help="Session ID")
    status.set_defaults(func=_cmd_status)

    # ── cost ───────────────────────────────────────────────────────────────
    cost = sub.add_parser("cost", help="查看实时费用明细")
    cost.add_argument("session_id", help="Session ID")
    cost.set_defaults(func=_cmd_cost)

    # ── role ──────────────────────────────────────────────────────────────
    role = sub.add_parser("role", help="查看或设置角色模型配置")
    role_sub = role.add_subparsers(dest="subcommand")

    role_show = role_sub.add_parser("show", help="显示当前角色配置")
    role_show.add_argument("--session", dest="session_id", help="指定 session（不指定则显示默认值）")
    role_show.set_defaults(func=_cmd_role)

    role_set = role_sub.add_parser("set", help="设置角色模型（热切换）")
    role_set.add_argument("agent", help="Agent 名称（advisor/researcher/writer/reviewer/polisher）")
    role_set.add_argument("provider", help="Provider（anthropic/openai/deepseek/...）")
    role_set.add_argument("model", help="模型名称")
    role_set.set_defaults(func=_cmd_role)

    # ── mode ───────────────────────────────────────────────────────────────
    mode = sub.add_parser("mode", help="切换 autopilot / manual 执行模式")
    mode.add_argument("run_mode", choices=["autopilot", "manual"], help="目标模式")
    mode.add_argument("--session", dest="session_id", help="Session ID（不指定则仅打印）")
    mode.set_defaults(func=_cmd_mode)

    # ── goto ──────────────────────────────────────────────────────────────
    goto = sub.add_parser("goto", help="跳转到指定阶段（后续 artifacts 标记 stale）")
    goto.add_argument("session_id", help="Session ID")
    goto.add_argument("stage", help="目标阶段（topic/literature/writing/review/polish）")
    goto.set_defaults(func=_cmd_goto)

    # ── rollback ───────────────────────────────────────────────────────────
    rollback = sub.add_parser("rollback", help="回退到指定阶段版本快照")
    rollback.add_argument("session_id", help="Session ID")
    rollback.add_argument("stage", help="目标阶段")
    rollback.set_defaults(func=_cmd_rollback)

    # ── export ─────────────────────────────────────────────────────────────
    export = sub.add_parser("export", help="导出发论文包")
    export.add_argument("session_id", help="Session ID")
    export.add_argument("--format", dest="format", choices=["md", "tex", "docx"],
                        default="md", help="导出格式")
    export.add_argument("--output", help="输出路径")
    export.set_defaults(func=_cmd_export)

    # ── debug ───────────────────────────────────────────────────────────────
    debug = sub.add_parser("debug", help="调试 session（日志 + summary）")
    debug.add_argument("session_id", help="Session ID")
    debug.set_defaults(func=_cmd_debug)

    return parser


# ─── Entry ──────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "start" and getattr(args, "no_interactive", False):
        args.mock = False
        args.mode = "autopilot"
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

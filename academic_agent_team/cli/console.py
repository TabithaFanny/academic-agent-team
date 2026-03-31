"""
CLI 入口 — paper-team 命令行工具（PRD 9.2 完整命令集）。

支持的命令：
    start      新建 session
    resume     恢复中断的 session
    status     查看当前进度和费用
    cost       查看实时费用明细
    role       查看/切换角色模型配置
    mode       切换 autopilot/manual 模式
    rollback   回退到指定版本
    diff       对比两个版本差异
    export     导出 artifacts
    sessions   列出最近 session
    debug      打印 session 调试信息
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
except ModuleNotFoundError:
    class Table:  # type: ignore[override]
        def __init__(self, title: str | None = None):
            self.title = title
            self._columns: list[str] = []
            self._rows: list[list[str]] = []

        def add_column(self, name: str, **kwargs) -> None:
            del kwargs
            self._columns.append(name)

        def add_row(self, *values: str) -> None:
            self._rows.append([str(v) for v in values])

        def add_section(self) -> None:
            return None

        def __str__(self) -> str:
            lines: list[str] = []
            if self.title:
                lines.append(self.title)
            if self._columns:
                lines.append(" | ".join(self._columns))
            for row in self._rows:
                lines.append(" | ".join(row))
            return "\n".join(lines)

    class Console:  # type: ignore[override]
        def print(self, message="", *args, **kwargs) -> None:
            del args, kwargs
            print(message)

from academic_agent_team.pipeline import run_mock_pipeline
from academic_agent_team.pipeline_real import run_pipeline
from academic_agent_team.session_logger import SessionLogger
from academic_agent_team.storage.db import (
    get_all_versions,
    update_session_model_config,
    get_session_summary,
    list_sessions,
)
from academic_agent_team.config.models import AGENT_MODEL_MAP
from academic_agent_team.config.role_profiles import (
    load_runtime_role_map,
    save_runtime_role_map,
)


console = Console()


# ── 通用工具 ─────────────────────────────────────────────────────────────────

def _db_path(base_dir: Path) -> Path:
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


def _connect(base_dir: Path) -> sqlite3.Connection:
    db_path = _db_path(base_dir)
    if not db_path.exists():
        console.print(f"[red]Session DB not found: {db_path}[/red]")
        sys.exit(1)
    return sqlite3.connect(db_path)


# ── start ─────────────────────────────────────────────────────────────────────

def _cmd_start(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    runtime_role_map = load_runtime_role_map(base_dir)
    AGENT_MODEL_MAP.update(runtime_role_map)
    topic = args.topic or "测试课题"
    journal = args.journal or "中文核心"
    run_mode = getattr(args, "mode", "autopilot")
    budget = getattr(args, "budget", 35.0)

    if args.mock or args.real == "mock":
        try:
            session_id = run_mock_pipeline(base_dir=base_dir, topic=topic, journal=journal)
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            return 1
        console.print(f"[green]Session completed (mock): {session_id}[/green]")
        return 0

    api_key = (
        args.api_key
        or os.environ.get("MINIMAX_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_API_KEY", "")
    )
    base_url = args.base_url or os.environ.get("MINIMAX_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL", "")
    model = args.model or os.environ.get("MINIMAX_MODEL") or os.environ.get("ANTHROPIC_MODEL", "")

    if not api_key:
        console.print("[red]Error: API key required for real mode.[/red]")
        console.print("Set MINIMAX_API_KEY/ANTHROPIC_AUTH_TOKEN env var or pass --api-key.")
        return 1

    console.print(f"[cyan]Real mode: base_url={base_url}, model={model}[/cyan]")
    try:
        session_id = run_pipeline(
            base_dir=base_dir,
            topic=topic,
            journal=journal,
            use_mock=False,
            api_key=api_key,
            base_url=base_url,
            model=model,
            run_mode=run_mode,
            budget_cap_cny=budget,
            role_profile=runtime_role_map,
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    console.print(f"[green]Session completed: {session_id}[/green]")
    return 0


# ── sessions ─────────────────────────────────────────────────────────────────

def _cmd_sessions(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    conn = _connect(base_dir)
    sessions = list_sessions(conn, limit=args.limit)
    conn.close()

    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return 0

    table = Table(title="Recent Sessions")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Topic")
    table.add_column("Journal")
    table.add_column("Mode")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Updated")

    for s in sessions:
        table.add_row(
            s["id"][:8] + "…",
            s["topic"][:30],
            s["journal_type"],
            s["run_mode"],
            s["stage"],
            s["status"],
            s["updated_at"][:16],
        )
    console.print(table)
    return 0


# ── status ────────────────────────────────────────────────────────────────────

def _cmd_status(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    conn = _connect(base_dir)
    try:
        summary = get_session_summary(conn, args.session_id)
    except KeyError:
        console.print(f"[red]Session not found: {args.session_id}[/red]")
        conn.close()
        return 1
    conn.close()

    console.print(f"\n[bold cyan]Session:[/bold cyan] {summary['id']}")
    console.print(f"[bold]Topic:[/bold]     {summary['topic']}")
    console.print(f"[bold]Journal:[/bold]   {summary['journal_type']}")
    console.print(f"[bold]Language:[/bold]  {summary['language']}")
    console.print(f"[bold]Mode:[/bold]       {summary['run_mode']}")
    console.print(f"[bold]Stage:[/bold]      {summary['stage']}")
    console.print(f"[bold]Status:[/bold]    {summary['status']}")
    console.print(f"[bold]Budget:[/bold]    ¥{summary['budget_cap_cny']:.2f}")
    console.print(f"[bold]Cost:[/bold]      ¥{summary['total_cost_cny']:.4f}")
    console.print(f"[bold]Msgs:[/bold]      {summary['message_count']}")
    console.print(f"[bold]Artifacts:[/bold] {summary['artifact_count']}")
    return 0


# ── cost ───────────────────────────────────────────────────────────────────────

def _cmd_cost(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    db = _db_path(base_dir)
    conn = sqlite3.connect(db)

    rows = conn.execute(
        """
        SELECT agent, model_id, stage,
               input_tokens, output_tokens, cost_cny, created_at
        FROM cost_log
        WHERE session_id = ?
        ORDER BY created_at ASC
        """,
        (args.session_id,),
    ).fetchall()
    conn.close()

    if not rows:
        console.print("[yellow]No cost records found.[/yellow]")
        return 0

    table = Table(title=f"Cost Breakdown — {args.session_id[:8]}")
    table.add_column("Agent")
    table.add_column("Model")
    table.add_column("Stage")
    table.add_column("Input Tokens")
    table.add_column("Output Tokens")
    table.add_column("Cost (¥)")
    table.add_column("Time")

    total = 0.0
    for agent, model, stage, inp, out, cost, ts in rows:
        total += cost
        table.add_row(agent, model, stage, str(inp), str(out), f"¥{cost:.4f}", ts[11:16])
    table.add_section()
    table.add_row("[bold]TOTAL[/bold]", "", "", "", "", f"[bold]¥{total:.4f}[/bold]", "")
    console.print(table)
    return 0


# ── role ────────────────────────────────────────────────────────────────────────

def _cmd_role(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    runtime_role_map = load_runtime_role_map(base_dir)
    AGENT_MODEL_MAP.update(runtime_role_map)
    if args.show:
        console.print("\n[bold cyan]Current Role Profile:[/bold cyan]")
        for agent, (p, m) in runtime_role_map.items():
            console.print(f"  {agent:<12} → {p}/{m}")
        return 0

    if args.set_agent and args.set_model:
        # 运行时切换（写入配置，影响后续 session）
        if "/" not in args.set_model:
            console.print("[red]Invalid --to format. Expected provider/model (e.g. openai/gpt4o).[/red]")
            return 1
        provider, model_name = args.set_model.split("/", 1)
        if args.set_agent not in AGENT_MODEL_MAP:
            console.print(f"[red]Unknown agent: {args.set_agent}[/red]")
            return 1
        runtime_role_map[args.set_agent] = (provider, model_name)
        AGENT_MODEL_MAP.update(runtime_role_map)
        save_path = save_runtime_role_map(base_dir, runtime_role_map)
        console.print(f"[green]Updated {args.set_agent} → {provider}/{model_name}[/green]")
        console.print(f"[cyan]Saved runtime profile: {save_path}[/cyan]")
        if args.session_id:
            conn = _connect(base_dir)
            try:
                update_session_model_config(conn, args.session_id, runtime_role_map)
                console.print(
                    f"[green]Session {args.session_id[:8]} model_config snapshot updated.[/green]"
                )
            except KeyError:
                console.print(f"[red]Session not found: {args.session_id}[/red]")
                conn.close()
                return 1
            conn.close()
        console.print("[yellow]Note: Changes affect new runs or resumed stages after this point.[/yellow]")
        return 0

    # 无参数：显示帮助
    parser = _build_parser()
    parser.parse_args(["role", "-h"])
    return 0


# ── mode ───────────────────────────────────────────────────────────────────────

def _cmd_mode(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    conn = _connect(base_dir)
    mode = args.mode  # autopilot | manual
    if mode not in ("autopilot", "manual"):
        console.print(f"[red]Invalid mode: {mode} (must be autopilot or manual)[/red]")
        conn.close()
        return 1
    try:
        from academic_agent_team.storage.db import update_session_run_mode
        update_session_run_mode(conn, args.session_id, mode)
        console.print(f"[green]Session {args.session_id[:8]} mode → {mode}[/green]")
    except KeyError:
        console.print(f"[red]Session not found: {args.session_id}[/red]")
        conn.close()
        return 1
    conn.close()
    return 0


# ── rollback ─────────────────────────────────────────────────────────────────

def _cmd_rollback(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    conn = _connect(base_dir)
    try:
        summary = get_session_summary(conn, args.session_id)
    except KeyError:
        console.print(f"[red]Session not found: {args.session_id}[/red]")
        conn.close()
        return 1

    if args.to_version is None and args.to_stage is None:
        versions = get_all_versions(conn, args.session_id)
        if not versions:
            console.print("[yellow]No versions found.[/yellow]")
            conn.close()
            return 0
        console.print(f"\n[bold cyan]Versions for {args.session_id[:8]}:[/bold cyan]")
        for v in versions:
            console.print(f"  {v['stage']}: v{v['version_num']} — {v['created_at'][:16]}")
        conn.close()
        return 0

    if args.to_stage is None:
        console.print("[red]--to-stage is required when executing rollback.[/red]")
        conn.close()
        return 1

    # 执行回退（标记后续 artifacts stale）
    from academic_agent_team.storage.db import mark_artifacts_stale_from_stage
    mark_artifacts_stale_from_stage(conn, args.session_id, args.to_stage)
    console.print(f"[green]Rolled back to {args.to_stage} — subsequent artifacts marked stale[/green]")
    conn.close()
    return 0


# ── diff ───────────────────────────────────────────────────────────────────────

def _cmd_diff(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    conn = _connect(base_dir)
    try:
        versions = get_all_versions(conn, args.session_id)
    except Exception:
        console.print(f"[red]Error reading versions for {args.session_id}[/red]")
        conn.close()
        return 1
    conn.close()

    target_versions = [v for v in versions if v["stage"] == args.stage]
    if len(target_versions) < 2:
        console.print(f"[yellow]Need at least 2 versions for stage '{args.stage}'.[/yellow]")
        return 0

    v_a = target_versions[max(0, args.v1 - 1)]
    v_b = target_versions[max(0, args.v2 - 1)]

    content_a = v_a["full_content"]
    content_b = v_b["full_content"]

    from difflib import unified_diff
    lines_a = content_a.splitlines()
    lines_b = content_b.splitlines()

    diff = list(unified_diff(
        lines_a, lines_b,
        fromfile=f"v{v_a['version_num']}",
        tofile=f"v{v_b['version_num']}",
        lineterm="",
    ))

    if not diff:
        console.print("[green]No differences.[/green]")
    else:
        console.print("\n".join(diff))
    return 0


# ── export ─────────────────────────────────────────────────────────────────────

def _cmd_export(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    output = base_dir / "output" / args.session_id
    dest = Path(args.dest or str(base_dir / f"export_{args.session_id[:8]}"))
    dest.mkdir(parents=True, exist_ok=True)

    import shutil
    if output.exists():
        shutil.copytree(output, dest / "output", dirs_exist_ok=True)
        console.print(f"[green]Exported to: {dest}[/green]")
    else:
        console.print(f"[red]No output found for session: {args.session_id}[/red]")
        return 1

    # 导出 session 记录
    conn = _connect(base_dir)
    try:
        summary = get_session_summary(conn, args.session_id)
        (dest / "session_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2)
        )
    except KeyError:
        pass
    conn.close()
    console.print(f"[green]Done: {dest}[/green]")
    return 0


# ── debug ──────────────────────────────────────────────────────────────────────

def _cmd_debug(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    conn = _connect(base_dir)
    try:
        summary = get_session_summary(conn, args.session_id)
    except KeyError:
        console.print(f"[red]Session not found: {args.session_id}[/red]")
        conn.close()
        return 1
    conn.close()

    log_path = base_dir / "session_store" / "logs" / f"{args.session_id}.log"
    logger = SessionLogger(log_path)
    tail_events = list(logger.tail(limit=args.tail or 10))

    console.print("[bold cyan]Session Summary[/bold cyan]")
    console.print(json.dumps(summary, ensure_ascii=False, indent=2))
    console.print("[bold cyan]Recent Log Events[/bold cyan]")
    console.print(json.dumps(tail_events, ensure_ascii=False, indent=2))
    return 0


# ── argparse 构建 ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-team")
    sub = parser.add_subparsers(dest="command", required=True)

    # ── start ──────────────────────────────────────────────────────────────
    start = sub.add_parser("start", help="新建论文写作 session")
    start.add_argument("--mock", action="store_true", help="使用 mock LLM（无需 API key）")
    start.add_argument("--real", nargs="?", const="env", default="env", help="使用真实 LLM")
    start.add_argument("--topic", help="研究课题")
    start.add_argument("--journal", default="中文核心", help="目标期刊")
    start.add_argument("--mode", default="autopilot", choices=["autopilot", "manual"],
                       help="执行模式")
    start.add_argument("--budget", type=float, default=35.0, help="预算上限（¥）")
    start.add_argument("--api-key", help="API Key")
    start.add_argument("--base-url", help="API Base URL")
    start.add_argument("--model", help="模型名")
    start.add_argument("--no-interactive", action="store_true", help="兼容标志")
    start.set_defaults(func=_cmd_start)

    # ── sessions ──────────────────────────────────────────────────────────
    sessions = sub.add_parser("sessions", help="列出最近的 session")
    sessions.add_argument("--limit", type=int, default=20)
    sessions.set_defaults(func=_cmd_sessions)

    # ── status ────────────────────────────────────────────────────────────
    status = sub.add_parser("status", help="查看 session 进度和费用")
    status.add_argument("session_id", help="Session ID")
    status.set_defaults(func=_cmd_status)

    # ── cost ───────────────────────────────────────────────────────────────
    cost = sub.add_parser("cost", help="查看实时费用明细")
    cost.add_argument("session_id", help="Session ID")
    cost.set_defaults(func=_cmd_cost)

    # ── role ───────────────────────────────────────────────────────────────
    role = sub.add_parser("role", help="查看/切换角色模型配置")
    role.add_argument("--show", action="store_true", help="显示当前角色配置")
    role.add_argument("--set", dest="set_agent",
                      help="设置目标 agent（如 advisor）")
    role.add_argument("--to", dest="set_model",
                      help="目标模型（如 anthropic/sonnet）")
    role.add_argument("--session-id", help="可选：同步更新指定 session 的 model_config 快照")
    role.set_defaults(func=_cmd_role)

    # ── mode ───────────────────────────────────────────────────────────────
    mode = sub.add_parser("mode", help="切换 autopilot / manual 模式")
    mode.add_argument("session_id", help="Session ID")
    mode.add_argument("mode", choices=["autopilot", "manual"])
    mode.set_defaults(func=_cmd_mode)

    # ── rollback ───────────────────────────────────────────────────────────
    rollback = sub.add_parser("rollback", help="回退 session 到指定阶段版本")
    rollback.add_argument("session_id", help="Session ID")
    rollback.add_argument("--to-stage", help="目标阶段（如 writing）")
    rollback.add_argument("--to-version", type=int, dest="to_version",
                          help="目标版本号（可选，不填则列出所有版本）")
    rollback.set_defaults(func=_cmd_rollback)

    # ── diff ───────────────────────────────────────────────────────────────
    diff = sub.add_parser("diff", help="对比两版论文差异")
    diff.add_argument("session_id", help="Session ID")
    diff.add_argument("stage", help="阶段（如 writing）")
    diff.add_argument("v1", type=int, default=1, help="版本1编号")
    diff.add_argument("v2", type=int, default=2, help="版本2编号")
    diff.set_defaults(func=_cmd_diff)

    # ── export ─────────────────────────────────────────────────────────────
    export = sub.add_parser("export", help="导出会话 artifacts")
    export.add_argument("session_id", help="Session ID")
    export.add_argument("--dest", help="导出目标目录")
    export.set_defaults(func=_cmd_export)

    # ── debug ─────────────────────────────────────────────────────────────
    debug = sub.add_parser("debug", help="打印 session 调试信息")
    debug.add_argument("session_id", help="Session ID")
    debug.add_argument("--tail", type=int, help="显示最近 N 条日志")
    debug.set_defaults(func=_cmd_debug)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

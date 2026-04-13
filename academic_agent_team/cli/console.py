"""
CLI 入口 — paper-team 命令行工具（PRD 9.2 完整命令集）。

支持的命令：
    start      新建 session
    db-migrate 显式迁移 legacy sessions.db schema
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
import asyncio
from datetime import datetime
import json
import os
import subprocess
import shutil
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
from academic_agent_team.pipeline_real import run_pipeline as run_pipeline_legacy
from academic_agent_team.pipeline_v2 import run_pipeline as run_pipeline_v2
from academic_agent_team.session_logger import SessionLogger
from academic_agent_team.storage.db import (
    connect,
    detect_missing_session_columns,
    get_all_versions,
    get_session_summary,
    list_sessions,
    migrate_legacy_sessions_schema,
    update_session_model_config,
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


# ── db-migrate ───────────────────────────────────────────────────────────────

def _cmd_db_migrate(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")

    missing_before = detect_missing_session_columns(conn)
    if not missing_before:
        console.print(f"[green]Schema already up to date: {db_path}[/green]")
        conn.close()
        return 0

    console.print(f"[yellow]Detected missing session columns: {missing_before}[/yellow]")
    if not args.yes:
        console.print("[yellow]Dry run only. Re-run with `paper-team db-migrate --yes` to apply.[/yellow]")
        conn.close()
        return 0

    backup_path = db_path.parent / f"{db_path.name}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)
        console.print(f"[cyan]Backup created: {backup_path}[/cyan]")

    applied = migrate_legacy_sessions_schema(conn)
    missing_after = detect_missing_session_columns(conn)
    conn.close()

    if missing_after:
        console.print(f"[red]Migration incomplete, missing columns remain: {missing_after}[/red]")
        return 1

    console.print(f"[green]Migration successful. Added columns: {applied or 'none'}[/green]")
    return 0


# ── start ─────────────────────────────────────────────────────────────────────

def _cmd_start(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    runtime_role_map = load_runtime_role_map(base_dir)
    AGENT_MODEL_MAP.update(runtime_role_map)
    topic = args.topic or "测试课题"
    journal = args.journal or "中文核心"
    run_mode = getattr(args, "mode", "autopilot")
    budget = getattr(args, "budget", 35.0)
    engine = getattr(args, "engine", "v2")

    if engine == "legacy" and (args.mock or args.real == "mock"):
        try:
            session_id = run_mock_pipeline(base_dir=base_dir, topic=topic, journal=journal)
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            return 1
        console.print(f"[green]Session completed (legacy mock): {session_id}[/green]")
        return 0

    if engine == "v2":
        # v2 模式映射：autopilot -> express, manual -> standard
        run_mode_v2 = "express" if run_mode == "autopilot" else "standard"
        human_callback = None

        if run_mode_v2 == "standard" and not args.no_interactive:
            async def _human_callback(
                intervention_id: str,
                phase: str,
                description: str,
                options: list[str] | None = None,
                data: dict | None = None,
            ) -> dict:
                del data
                console.print(f"\n[bold cyan]{intervention_id} / {phase}[/bold cyan] {description}")

                if options:
                    for idx, item in enumerate(options, 1):
                        console.print(f"  {idx}. {item}")
                    raw = input(f"请选择 [1-{len(options)}] (默认 1): ").strip()
                    try:
                        selected = int(raw) - 1 if raw else 0
                        if selected < 0 or selected >= len(options):
                            selected = 0
                    except ValueError:
                        selected = 0
                    return {"selected_index": selected}

                if intervention_id == "H3":
                    raw = input("选择 A(继续迭代)/B(手动修改) [A/B, 默认 A]: ").strip().lower()
                    return {"manual_edit": raw == "b"}

                raw = input("确认继续? [Y/n]: ").strip().lower()
                return {"auto_proceed": raw in ("", "y", "yes")}

            human_callback = _human_callback

        if args.mock or args.real == "mock":
            os.environ["PAPER_TEAM_LLM_MOCK"] = "true"
            os.environ["AI_DETECT_MOCK"] = "true"
            os.environ["CNKI_MOCK"] = "true"
            os.environ["CITATION_MOCK"] = "true"

        try:
            context = asyncio.run(
                run_pipeline_v2(
                    base_dir=base_dir,
                    topic=topic,
                    journal=journal,
                    run_mode=run_mode_v2,
                    budget_cap_cny=budget,
                    human_callback=human_callback,
                )
            )
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            console.print("[yellow]Tip: you can fallback with --engine legacy[/yellow]")
            return 1
        except Exception as exc:
            console.print(f"[red]Pipeline v2 failed: {exc}[/red]")
            console.print("[yellow]Tip: you can fallback with --engine legacy[/yellow]")
            return 1

        console.print(f"[green]Session completed (v2): {context.session_id}[/green]")
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
        session_id = run_pipeline_legacy(
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


# ── release-gate ─────────────────────────────────────────────────────────────

def _set_env_flag(name: str, value: str, previous: dict[str, str | None]) -> None:
    previous[name] = os.environ.get(name)
    os.environ[name] = value


def _restore_env_flags(previous: dict[str, str | None]) -> None:
    for key, old_val in previous.items():
        if old_val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old_val


def _cmd_release_gate(args: argparse.Namespace) -> int:
    """
    发布门禁自动化：
      1) schema preflight
      2) v2 + legacy mock smoke
      3) regression pytest
    """
    base_dir = Path.cwd()
    db_path = _db_path(base_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) schema preflight
    try:
        conn = connect(db_path)
    except RuntimeError as exc:
        console.print(f"[red]Schema preflight failed: {exc}[/red]")
        console.print("[yellow]Run `paper-team db-migrate --yes` before release gate.[/yellow]")
        return 1
    except sqlite3.Error as exc:
        console.print(f"[red]Schema preflight failed: unable to open DB ({exc})[/red]")
        return 1
    conn.close()
    console.print(f"[green]Schema preflight passed: {db_path}[/green]")

    # 2) smoke
    if not args.skip_smoke:
        env_backup: dict[str, str | None] = {}
        _set_env_flag("PAPER_TEAM_LLM_MOCK", "true", env_backup)
        _set_env_flag("AI_DETECT_MOCK", "true", env_backup)
        _set_env_flag("CNKI_MOCK", "true", env_backup)
        _set_env_flag("CITATION_MOCK", "true", env_backup)
        try:
            v2_ctx = asyncio.run(
                run_pipeline_v2(
                    base_dir=base_dir,
                    topic=args.topic or "release gate v2 smoke",
                    journal=args.journal or "中文核心",
                    run_mode="express",
                )
            )
            console.print(f"[green]Smoke passed (v2): {v2_ctx.session_id}[/green]")

            legacy_session_id = run_mock_pipeline(
                base_dir=base_dir,
                topic=args.topic or "release gate legacy smoke",
                journal=args.journal or "中文核心",
            )
            console.print(f"[green]Smoke passed (legacy): {legacy_session_id}[/green]")
        except Exception as exc:
            console.print(f"[red]Smoke failed: {exc}[/red]")
            _restore_env_flags(env_backup)
            return 1
        _restore_env_flags(env_backup)
    else:
        console.print("[yellow]Smoke skipped by --skip-smoke[/yellow]")

    # 3) regression
    if args.skip_regression:
        console.print("[yellow]Regression skipped by --skip-regression[/yellow]")
        console.print("[green]Release gate passed (without regression).[/green]")
        return 0

    targets = args.target or ["tests"]
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets]
    console.print(f"[cyan]Running regression: {' '.join(targets)}[/cyan]")
    proc = subprocess.run(
        cmd,
        cwd=base_dir,
        text=True,
        capture_output=True,
    )
    if proc.stdout:
        console.print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr:
            console.print(proc.stderr.strip())
        console.print("[red]Regression failed. Release gate blocked.[/red]")
        return 1

    console.print("[green]Regression passed.[/green]")
    console.print("[green]Release gate passed.[/green]")
    return 0


# ── argparse 构建 ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-team")
    sub = parser.add_subparsers(dest="command", required=True)

    # ── db-migrate ─────────────────────────────────────────────────────────
    db_migrate = sub.add_parser("db-migrate", help="迁移 legacy sessions.db schema")
    db_migrate.add_argument("--yes", action="store_true", help="确认执行迁移（会自动备份）")
    db_migrate.set_defaults(func=_cmd_db_migrate)

    # ── start ──────────────────────────────────────────────────────────────
    start = sub.add_parser("start", help="新建论文写作 session")
    start.add_argument("--mock", action="store_true", help="使用 mock LLM（无需 API key）")
    start.add_argument("--real", nargs="?", const="env", default="env", help="使用真实 LLM")
    start.add_argument("--topic", help="研究课题")
    start.add_argument("--journal", default="中文核心", help="目标期刊")
    start.add_argument("--mode", default="autopilot", choices=["autopilot", "manual"],
                       help="执行模式")
    start.add_argument("--engine", default="v2", choices=["v2", "legacy"],
                       help="执行引擎：v2(默认) 或 legacy")
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

    # ── release-gate ──────────────────────────────────────────────────────
    release_gate = sub.add_parser("release-gate", help="执行发布门禁（schema + smoke + regression）")
    release_gate.add_argument("--skip-smoke", action="store_true", help="跳过 smoke 验证")
    release_gate.add_argument("--skip-regression", action="store_true", help="跳过回归测试")
    release_gate.add_argument("--topic", help="smoke 会话 topic（可选）")
    release_gate.add_argument("--journal", default="中文核心", help="smoke 目标期刊")
    release_gate.add_argument(
        "--target",
        action="append",
        help="追加回归 pytest target（可重复传入）；默认内置 3 个核心用例",
    )
    release_gate.set_defaults(func=_cmd_release_gate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

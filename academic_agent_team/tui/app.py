"""
academic_agent_team/tui/app.py

Textual TUI 应用——生产级四面板布局。

架构要点：
- 所有 Textual/Rich 运行时依赖延迟加载，模块无 textual 时可 import
- create_tui_app() / run_tui() 首次触发加载，缺失则抛出清晰 ImportError
- Pipeline → UI 完全通过 events.py 解耦
- InterruptManager 通过 /abort 等命令注入 pipeline

布局（Grid）：
┌────────────────────────────────────────────────────┐
│                    Header (session info)              │
├──────────────────┬─────────────────────────────────┤
│                  │                                   │
│  AgentStatus     │       StreamingOutput             │
│  (固定高度)       │       (流式消息，可滚动)            │
│                  ├─────────────────────────────────┤
│                  │                                   │
│  DocumentViewer  │       CommandInput (Footer)       │
│  (Markdown)      │       (命令输入)                  │
└──────────────────┴─────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

# ── 核心事件 & 类型（无 textual / rich 依赖）────────────────────────────────

from academic_agent_team.tui.events import (
    AgentMessageEvent,
    CompletionEvent,
    CostUpdateEvent,
    ErrorEvent,
    HumanInterruptEvent,
    PipelineEventT,
    Stage,
    StateUpdateEvent,
    TokenStreamEvent,
)
from academic_agent_team.tui.interrupt import InterruptKind, InterruptManager

if TYPE_CHECKING:
    from academic_agent_team.tui.runner import PipelineRunner

# ── 依赖检查 ────────────────────────────────────────────────────────────────

_RICH_LOADED: bool | tuple = False
_TEXTUAL_LOADED: bool = False


def _ensure_rich() -> tuple:
    """Lazily import rich. Raises ImportError with clear instructions."""
    global _RICH_LOADED
    if isinstance(_RICH_LOADED, tuple):
        return _RICH_LOADED
    try:
        from rich.console import Console as RichConsole
        from rich.markdown import Markdown
        from rich.table import Table
        _RICH_LOADED = (RichConsole, Markdown, Table)
        return _RICH_LOADED
    except ImportError:
        raise ImportError(
            "rich is required for TUI mode but is not installed.\n"
            "Install it with: pip install rich"
        )


def _ensure_textual() -> None:
    """Lazily import textual. Raises ImportError with clear instructions."""
    global _TEXTUAL_LOADED
    if _TEXTUAL_LOADED:
        return
    try:
        import textual  # noqa: F401
        _TEXTUAL_LOADED = True
    except ImportError:
        raise ImportError(
            "textual is required for TUI mode but is not installed.\n"
            "Install it with: pip install textual\n"
            "Or run in headless mode without --tui."
        )


# ── App 状态（纯 dataclass，无 textual 依赖）────────────────────────────────

@dataclass
class AppState:
    """整个 TUI 的共享状态。"""
    session_id: str = ""
    topic: str = ""
    journal: str = ""
    budget_cap: float = 35.0
    cumulative_cost: float = 0.0
    current_stage: Stage = Stage.UNKNOWN
    running: bool = False
    completed: bool = False
    current_document: str = ""
    agent_statuses: dict[str, str] = field(default_factory=lambda: {
        "advisor": "idle",
        "researcher": "idle",
        "writer": "idle",
        "reviewer": "idle",
        "polisher": "idle",
    })
    token_buffers: dict[str, str] = field(default_factory=dict)


# ── 类占位符（_define_classes() 执行后替换为真实子类）────────────────────────

def _stub(name: str):
    """Class that raises ImportError if instantiated before textual loads."""
    class _S:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                f"{name} requires textual but was used before module initialization.\n"
                "Call create_tui_app() or run_tui() first."
            )
    _S.__name__ = name
    _S.__qualname__ = name
    return _S


CommandSubmitted: type = _stub("CommandSubmitted")
AgentStatusPanel: type = _stub("AgentStatusPanel")
StreamingOutputPanel: type = _stub("StreamingOutputPanel")
DocumentViewerPanel: type = _stub("DocumentViewerPanel")
CommandInput: type = _stub("CommandInput")
SessionHeader: type = _stub("SessionHeader")
TUIApp: type = _stub("TUIApp")
_create_tui_app: Any = None
_run_tui: Any = None


# ── 类工厂 ───────────────────────────────────────────────────────────────────

def _define_classes() -> None:
    """
    在 textual + rich 加载成功后定义所有 UI 类。
    幂等：重复调用直接返回。
    """
    global CommandSubmitted, AgentStatusPanel, StreamingOutputPanel
    global DocumentViewerPanel, CommandInput, SessionHeader, TUIApp
    global _create_tui_app, _run_tui

    if _create_tui_app is not None:
        return

    _ensure_textual()
    RichConsole, Markdown, Table = _ensure_rich()

    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.message import Message
    from textual.widgets import Header, Static, RichLog, Input

    # ── CommandSubmitted ───────────────────────────────────────────────────

    class CommandSubmitted(Message):
        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    # ── AgentStatusPanel ────────────────────────────────────────────────────

    class AgentStatusPanel(Static):
        _state: AppState

        def __init__(self, state: AppState) -> None:
            super().__init__()
            self._state = state

        def compose(self) -> ComposeResult:
            yield Static("▌ Agent 流水线", id="panel-title")
            yield Static("", id="agent-table")

        def on_mount(self) -> None:
            self.update_table()

        def update_agent(self, agent: str, status: str) -> None:
            self._state.agent_statuses[agent] = status
            self.update_table()

        def update_table(self) -> None:
            table = Table(
                title="状态", show_header=True, expand=True, box=None,
                style="cyan", header_style="bold cyan",
            )
            table.add_column("Agent", width=13)
            table.add_column("状态", width=11)
            table.add_column("说明", width=20)
            labels = {
                "advisor":    "选题顾问",
                "researcher": "文献研究员",
                "writer":     "论文写手",
                "reviewer":   "审稿人",
                "polisher":   "润色师",
            }
            status_styles = {
                "idle":    ("dim",         "⏸ idle"),
                "running": ("bold cyan",   "▶ running"),
                "waiting": ("yellow",      "◐ waiting"),
                "done":    ("bold green",  "✓ done"),
                "error":   ("bold red",    "✗ error"),
            }
            for name in ["advisor", "researcher", "writer", "reviewer", "polisher"]:
                status = self._state.agent_statuses.get(name, "idle")
                style, label = status_styles.get(status, ("dim", status))
                table.add_row(labels[name], label, "", style=style)
            console = RichConsole()
            with console.capture() as cap:
                console.print(table)
            self.query_one("#agent-table", Static).update(cap.get())

    # ── StreamingOutputPanel ────────────────────────────────────────────────

    class StreamingOutputPanel(VerticalScroll):
        _state: AppState
        _log: RichLog | None = None

        CSS = """
        StreamingOutputPanel {
            height: 60%;
            border: solid $accent;
            background: $surface;
        }
        """

        def __init__(self, state: AppState) -> None:
            super().__init__()
            self._state = state

        def compose(self) -> ComposeResult:
            yield Static("▌ 流式输出", id="stream-title")
            yield RichLog(id="stream-log", markup=True, auto_scroll=True, max_lines=5000)

        def on_mount(self) -> None:
            self._log = self.query_one(RichLog)

        def on_token_stream(self, event: TokenStreamEvent) -> None:
            buf = self._state.token_buffers
            buf[event.agent] = buf.get(event.agent, "") + event.content
            if self._log:
                self._log.write(event.content, auto_scroll=True)
            if event.is_final:
                buf[event.agent] = ""
                if self._log:
                    self._log.write("\n──────────────────────────────\n", auto_scroll=True)

        def on_agent_message(self, event: AgentMessageEvent) -> None:
            if not self._log:
                return
            p = event.parsed_payload or {}
            if "summary" in p:
                self._log.write(
                    f"[bold green]✓ {event.agent}[/bold green]  "
                    f"[dim]{event.stage.value}[/dim]\n  "
                    f"{str(p['summary'])[:100]}\n", auto_scroll=True,
                )
            elif "verdict" in p:
                color = "green" if p["verdict"] in ("accept", "minor_revision") else "yellow"
                self._log.write(
                    f"[bold {color}]{event.agent}[/bold {color}]  verdict="
                    f"[{color}]{p['verdict']}[/{color}]  "
                    f"score={p.get('overall_score','?')}\n", auto_scroll=True,
                )
            elif "selected_direction" in p:
                self._log.write(
                    f"[bold cyan]✓ {event.agent}[/bold cyan]  "
                    f"推荐方向: {p['selected_direction']}\n", auto_scroll=True,
                )
            else:
                self._log.write(
                    f"[dim]✓ {event.agent} → {event.stage.value}[/dim]\n",
                    auto_scroll=True,
                )
            self._state.token_buffers[event.agent] = ""

        def clear(self) -> None:
            if self._log:
                self._log.clear()

    # ── DocumentViewerPanel ─────────────────────────────────────────────────

    class DocumentViewerPanel(VerticalScroll):
        _state: AppState

        CSS = """
        DocumentViewerPanel {
            height: 1fr;
            border: solid $secondary;
            background: $surface;
        }
        """

        def __init__(self, state: AppState) -> None:
            super().__init__()
            self._state = state

        def compose(self) -> ComposeResult:
            yield Static("▌ 文档预览", id="doc-title")
            yield Static("📄 论文内容将在写作阶段实时显示...", id="doc-content")

        def on_state_update(self, event: StateUpdateEvent) -> None:
            self._state.current_stage = event.to_stage
            stage_labels = {
                Stage.WRITING: "📝 论文草稿",
                Stage.REVIEW:  "🔍 审稿意见",
                Stage.POLISH:  "✨ 润色版本",
            }
            if event.to_stage in stage_labels:
                self.query_one("#doc-title", Static).update(f"▌ {stage_labels[event.to_stage]}")

        def on_agent_message(self, event: AgentMessageEvent) -> None:
            if event.agent not in ("writer", "polisher"):
                return
            p = event.parsed_payload or {}
            sections = p.get("sections") or p.get("polished_sections") or {}
            if not sections or not isinstance(sections, dict):
                return
            order = ["abstract", "introduction", "literature_review",
                     "methodology", "results", "discussion", "conclusion"]
            content = "\n\n".join(
                f"## {k.capitalize()}\n{sections[k]}"
                for k in order if sections.get(k)
            )
            self._state.current_document = content
            md = Markdown(content or "*（空内容）*", code_theme="monokai")
            self.query_one("#doc-content", Static).update(md)

    # ── CommandInput ────────────────────────────────────────────────────────

    class CommandInput(Input):
        _im: InterruptManager | None

        BINDINGS = [
            Binding("ctrl+c", "interrupt", "打断", show=True),
            Binding("enter", "submit", "发送", show=False),
        ]

        def __init__(self, interrupt_manager: InterruptManager | None = None) -> None:
            super().__init__(placeholder="输入命令（/help 查看）...", id="cmd-input")
            self._im = interrupt_manager

        def on_mount(self) -> None:
            self.focus()

        def action_interrupt(self) -> None:
            if self._im:
                from academic_agent_team.tui.interrupt import InterruptSignal
                self._im.send(InterruptSignal.make(InterruptKind.CANCEL))
            self.app.notify("⚠ 已发送打断信号", severity="warning", timeout=3)

        def action_submit(self) -> None:
            cmd = self.value.strip()
            self.value = ""
            if cmd:
                self.post_message(CommandSubmitted(cmd))

    # ── SessionHeader ────────────────────────────────────────────────────────

    class SessionHeader(Header):
        _state: AppState

        def __init__(self, state: AppState) -> None:
            super().__init__()
            self._state = state

        def set_title(self, title: str, sub: str = "") -> None:
            self.title = title
            self.sub_title = sub

    # ── TUIApp ─────────────────────────────────────────────────────────────

    class TUIApp(App):
        CSS = """
        Screen { background: $surface; }
        #left-col  { width: 38%; height: 100%; }
        #right-col { width: 62%; height: 100%; }
        #panel-title, #stream-panel-title {
            height: 1;
            padding: 0 1;
            background: $primary;
            color: $text;
            text-style: bold;
        }
        """

        BINDINGS = [
            Binding("ctrl+q", "quit", "退出", show=True),
            Binding("ctrl+l", "clear_log", "清日志", show=False),
        ]

        _state: AppState
        _im: InterruptManager
        _task: asyncio.Task[None] | None
        _agent_panel: AgentStatusPanel | None
        _stream_panel: StreamingOutputPanel | None
        _doc_panel: DocumentViewerPanel | None
        runner: "PipelineRunner"

        def __init__(
            self,
            runner: "PipelineRunner",
            topic: str = "",
            journal: str = "",
            budget_cap: float = 35.0,
            interrupt_manager: InterruptManager | None = None,
        ) -> None:
            super().__init__()
            self.runner = runner
            self._state = AppState(
                topic=topic, journal=journal, budget_cap=budget_cap,
            )
            self._im = interrupt_manager or InterruptManager()
            self._task = None
            self._agent_panel = None
            self._stream_panel = None
            self._doc_panel = None

        def compose(self) -> ComposeResult:
            self._agent_panel = AgentStatusPanel(self._state)
            self._stream_panel = StreamingOutputPanel(self._state)
            self._doc_panel = DocumentViewerPanel(self._state)
            yield SessionHeader(self._state)
            with Horizontal(id="main-row"):
                with Vertical(id="left-col"):
                    yield self._agent_panel
                    yield self._doc_panel
                with Vertical(id="right-col"):
                    yield Static("▌ 流式输出", id="stream-panel-title")
                    yield self._stream_panel
            yield CommandInput(self._im)

        async def on_mount(self) -> None:
            self.title = f"Academic Agent Team  |  {self._state.topic}"
            self.sub_title = (
                f"{self._state.topic}  ·  {self._state.journal}  ·  "
                f"¥{self._state.budget_cap}  ·  启动中..."
            )
            self._state.running = True
            self._task = self.asyncio.create_task(self._run())

        async def on_unmount(self) -> None:
            if self._task and not self._task.done():
                self._task.cancel()

        async def _run(self) -> None:
            try:
                async for event in self.runner.run():
                    await self._dispatch(event)
            except asyncio.CancelledError:
                self.notify("Pipeline 已取消", severity="warning")
            except Exception as e:
                self.notify(f"Pipeline 异常: {e}", severity="error")

        async def _dispatch(self, event: PipelineEventT) -> None:
            if isinstance(event, TokenStreamEvent):
                if self._stream_panel:
                    self._stream_panel.on_token_stream(event)

            elif isinstance(event, AgentMessageEvent):
                self._state.agent_statuses[event.agent] = "done"
                if self._agent_panel:
                    self._agent_panel.update_agent(event.agent, "done")
                if self._stream_panel:
                    self._stream_panel.on_agent_message(event)
                if self._doc_panel:
                    self._doc_panel.on_agent_message(event)

            elif isinstance(event, StateUpdateEvent):
                self._state.current_stage = event.to_stage
                self._state.session_id = event.session_id or self._state.session_id
                if event.agent and self._agent_panel:
                    self._agent_panel.update_agent(event.agent, "running")
                if self._doc_panel:
                    self._doc_panel.on_state_update(event)
                self.sub_title = (
                    f"[{event.to_stage.value}]  {self._state.topic}  ·  "
                    f"{self._state.journal}  ·  ¥{self._state.budget_cap}"
                )

            elif isinstance(event, CostUpdateEvent):
                self._state.cumulative_cost = event.cumulative_cny
                pct = (
                    event.cumulative_cny / event.budget_cap_cny * 100
                    if event.budget_cap_cny else 0
                )
                budget_str = f"¥{event.cumulative_cny:.2f} / ¥{event.budget_cap_cny} ({pct:.0f}%)"
                self.sub_title = (
                    f"{self._state.current_stage.value}  {self._state.topic}  ·  "
                    f"{self._state.journal}  ·  {budget_str}"
                )
                if pct >= 80:
                    self.notify(f"⚠ 预算已达 {pct:.0f}%！", severity="warning", timeout=5)

            elif isinstance(event, ErrorEvent):
                if event.agent and self._agent_panel:
                    self._agent_panel.update_agent(event.agent, "error")
                self.notify(
                    f"✗ {event.agent or 'Pipeline'}: {event.message[:100]}",
                    severity="error", timeout=0,
                )

            elif isinstance(event, HumanInterruptEvent):
                self.notify(
                    f"⏸ 人工介入: /{event.command}  {event.raw_input[:60]}",
                    severity="warning", timeout=8,
                )

            elif isinstance(event, CompletionEvent):
                self._state.running = False
                self._state.completed = True
                self._state.session_id = event.session_id
                for name in self._state.agent_statuses:
                    if self._agent_panel:
                        self._agent_panel.update_agent(name, "done")
                self.notify(
                    f"✅ 完成！session={event.session_id[:8]}...  "
                    f"words={event.word_count}  cost=¥{event.total_cost_cny:.4f}",
                    severity="information", timeout=0,
                )

        def on_command_submitted(self, event: CommandSubmitted) -> None:
            cmd = event.command.strip()
            if not cmd:
                return
            if cmd.startswith("/"):
                self._slash(cmd)
            else:
                from academic_agent_team.tui.interrupt import InterruptSignal
                self._im.send(InterruptSignal.make(InterruptKind.REWRITE, payload=cmd))

        def _slash(self, cmd: str) -> None:
            parts = cmd.split(maxsplit=1)
            name, arg = parts[0].lower(), (parts[1] if len(parts) > 1 else "")

            if name in ("/abort", "/cancel"):
                from academic_agent_team.tui.interrupt import InterruptSignal
                self._im.send(InterruptSignal.make(InterruptKind.CANCEL))
                self.notify("⚠ 打断信号已发送", severity="warning", timeout=3)

            elif name == "/status":
                self.notify(
                    f"session={self._state.session_id[:8] or '(none)'}  "
                    f"stage={self._state.current_stage.value}  "
                    f"running={self._state.running}  "
                    f"cost=¥{self._state.cumulative_cost:.4f}",
                    timeout=5,
                )

            elif name == "/role":
                from academic_agent_team.config.role_profiles import DEFAULT_ROLE_PROFILE
                lines = [f"{a}: {p}/{m}" for a, (p, m) in DEFAULT_ROLE_PROFILE.items()]
                self.notify("Role profile:\n" + "\n".join(lines), timeout=6)

            elif name == "/mode":
                if arg not in ("autopilot", "manual"):
                    self.notify("用法: /mode autopilot|manual", severity="warning", timeout=3)
                else:
                    self.notify(f"运行模式切换: {arg}（下次启动生效）", timeout=3)

            elif name == "/help":
                helps = [
                    "/abort         打断 pipeline",
                    "/status        显示状态",
                    "/role          显示角色配置",
                    "/mode <mode>   切换模式",
                    "/help          本帮助",
                    "<text>         透传为人工反馈",
                ]
                self.notify("\n".join(helps), timeout=8)

            elif name == "/goto":
                self.notify(
                    "⚠ /goto 需在 pipeline 外部使用（下次启动时指定 --mode）",
                    severity="warning", timeout=5,
                )

            else:
                self.notify(f"未知命令: {name}，输入 /help", severity="warning", timeout=3)

        def action_quit(self) -> None:
            if self._state.running:
                self.notify("Pipeline 运行中，请先 /abort 再退出", severity="warning", timeout=5)
                return
            self.exit()

        def action_clear_log(self) -> None:
            if self._stream_panel:
                self._stream_panel.clear()

    # ── 内部工厂函数 ────────────────────────────────────────────────────────

    def _create_tui_app_impl(
        *,
        engine: str = "autogen",
        base_dir: Path,
        topic: str,
        journal: str,
        use_mock: bool = False,
        run_mode: str = "autopilot",
        budget_cap_cny: float = 35.0,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> tuple:
        from academic_agent_team.tui.runner import (
            AutoGenRunner,
            PipelineConfig,
            SequentialRunner,
        )
        im = InterruptManager()
        shared_queue: asyncio.Queue[str] = asyncio.Queue()
        _orig = im.send

        def _proxied(signal) -> None:
            _orig(signal)
            shared_queue.put_nowait(signal.kind.value)

        im.send = _proxied  # type: ignore[method-assign]

        config = PipelineConfig(
            base_dir=base_dir, topic=topic, journal=journal,
            use_mock=use_mock, run_mode=run_mode,
            budget_cap_cny=budget_cap_cny,
            api_key=api_key, base_url=base_url, model=model,
            interrupt_manager=im, interrupt_queue=shared_queue,
        )
        runner: PipelineRunner = (
            SequentialRunner(config) if engine == "sequential"
            else AutoGenRunner(config)
        )
        app = TUIApp(
            runner=runner,
            topic=topic, journal=journal,
            budget_cap=budget_cap_cny,
            interrupt_manager=im,
        )
        return app, im

    def _run_tui_impl(
        engine: str = "autogen",
        topic: str = "",
        journal: str = "中文核心",
        base_dir: str = ".",
        use_mock: bool = True,
        run_mode: str = "autopilot",
        budget_cap_cny: float = 35.0,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> None:
        app, _im = _create_tui_app_impl(
            engine=engine, base_dir=Path(base_dir), topic=topic,
            journal=journal, use_mock=use_mock, run_mode=run_mode,
            budget_cap_cny=budget_cap_cny,
            api_key=api_key, base_url=base_url, model=model,
        )
        app.run()

    _create_tui_app = _create_tui_app_impl
    _run_tui = _run_tui_impl


# ── 公开 API ─────────────────────────────────────────────────────────────────

def create_tui_app(
    *,
    engine: str = "autogen",
    base_dir: Path,
    topic: str,
    journal: str,
    use_mock: bool = False,
    run_mode: str = "autopilot",
    budget_cap_cny: float = 35.0,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> tuple:
    """
    根据 engine 类型创建 TUIApp + InterruptManager。

    首次调用触发 textual + rich 加载；
    若依赖缺失，抛出 ImportError 并附安装指引。
    """
    _define_classes()
    return _create_tui_app(
        engine=engine, base_dir=base_dir, topic=topic,
        journal=journal, use_mock=use_mock, run_mode=run_mode,
        budget_cap_cny=budget_cap_cny,
        api_key=api_key, base_url=base_url, model=model,
    )


def run_tui(
    engine: str = "autogen",
    topic: str = "",
    journal: str = "中文核心",
    base_dir: str = ".",
    use_mock: bool = True,
    run_mode: str = "autopilot",
    budget_cap_cny: float = 35.0,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> None:
    """CLI 入口函数。"""
    _define_classes()
    _run_tui(
        engine=engine, topic=topic, journal=journal,
        base_dir=base_dir, use_mock=use_mock, run_mode=run_mode,
        budget_cap_cny=budget_cap_cny,
        api_key=api_key, base_url=base_url, model=model,
    )


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Academic Agent Team TUI")
    parser.add_argument("--engine", choices=["autogen", "sequential"], default="autogen")
    parser.add_argument("--topic", default="")
    parser.add_argument("--journal", default="中文核心")
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--mock", dest="use_mock", action="store_true")
    parser.add_argument("--real", dest="use_mock", action="store_false")
    parser.add_argument("--mode", dest="run_mode", choices=["autopilot", "manual"], default="autopilot")
    parser.add_argument("--budget", dest="budget_cap_cny", type=float, default=35.0)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default="")
    args = parser.parse_args(sys.argv[2:])

    run_tui(
        engine=args.engine, topic=args.topic, journal=args.journal,
        base_dir=args.base_dir, use_mock=args.use_mock, run_mode=args.run_mode,
        budget_cap_cny=args.budget_cap_cny,
        api_key=args.api_key, base_url=args.base_url, model=args.model,
    )


if __name__ == "__main__":
    main()

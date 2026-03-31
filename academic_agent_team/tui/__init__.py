"""
academic_agent_team.tui

Textual TUI 层——四面板布局 + pipeline 事件映射。

使用示例：

    # Headless 模式（无需 textual，可任意导入）
    from academic_agent_team.tui import events, interrupt, runner

    from academic_agent_team.tui.events import (
        TokenStreamEvent,
        AgentMessageEvent,
        StateUpdateEvent,
        CostUpdateEvent,
        ErrorEvent,
        HumanInterruptEvent,
        CompletionEvent,
        Stage,
        PipelineEventT,
    )

    from academic_agent_team.tui.runner import (
        PipelineRunner,
        AutoGenRunner,
        SequentialRunner,
        PipelineConfig,
    )

    from academic_agent_team.tui.interrupt import (
        InterruptManager,
        InterruptSignal,
        InterruptKind,
    )

    # TUI 模式（需要 pip install textual rich）
    from academic_agent_team.tui.app import (
        TUIApp,          # 主应用类
        create_tui_app,  # 工厂函数
        run_tui,         # CLI 入口
    )
"""

from academic_agent_team.tui import events
from academic_agent_team.tui import interrupt
from academic_agent_team.tui import runner

# Re-export event types at package level for convenience
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
    Verdict,
)

# Re-export interrupt types
from academic_agent_team.tui.interrupt import (
    InterruptKind,
    InterruptManager,
    InterruptSignal,
)

# Re-export runner types
from academic_agent_team.tui.runner import (
    AutoGenRunner,
    PipelineConfig,
    PipelineRunner,
    SequentialRunner,
)

__all__ = [
    # Sub-modules (always safe to import)
    "events",
    "interrupt",
    "runner",
    # Event types
    "AgentMessageEvent",
    "CompletionEvent",
    "CostUpdateEvent",
    "ErrorEvent",
    "HumanInterruptEvent",
    "PipelineEventT",
    "Stage",
    "StateUpdateEvent",
    "TokenStreamEvent",
    "Verdict",
    # Interrupt types
    "InterruptKind",
    "InterruptManager",
    "InterruptSignal",
    # Runner types
    "AutoGenRunner",
    "PipelineConfig",
    "PipelineRunner",
    "SequentialRunner",
]
# NOTE: TUIApp, create_tui_app, run_tui are NOT re-exported here because
# they require textual. Import them explicitly from academic_agent_team.tui.app
# when you need the TUI (the ImportError will be raised at that point).

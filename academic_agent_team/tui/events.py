"""
academic_agent_team/tui/events.py

强类型事件系统 — 所有 pipeline → TUI 的通信都通过此模块。
使用 dataclass + JSON-serializable，确保可测试性和跨进程扩展。

事件分类：
  TokenStream   — token 级流式输出（用于打字机效果）
  AgentMessage  — 完整的 Agent 输出消息
  StateUpdate   — pipeline 状态机跃迁
  CostUpdate    — 成本统计更新
  Error         — 可恢复/不可恢复错误
  HumanInterrupt— 人工打断命令（/pause 等）
  Completion    — pipeline 正常结束
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator


# ─── Stage 枚举 ───────────────────────────────────────────────────────────────

class Stage(str, Enum):
    """Pipeline 阶段，与 DB schema 对齐。"""
    TOPIC = "topic_done"
    LITERATURE = "literature_done"
    WRITING = "writing_done"
    REVIEW = "review_done"
    POLISH = "polish_done"
    EXPORT = "export"
    UNKNOWN = "unknown"

    @classmethod
    def from_agent_name(cls, name: str) -> "Stage":
        mapping = {
            "advisor": cls.TOPIC,
            "researcher": cls.LITERATURE,
            "writer": cls.WRITING,
            "reviewer": cls.REVIEW,
            "polisher": cls.POLISH,
        }
        return mapping.get(name, cls.UNKNOWN)


# ─── Verdict ─────────────────────────────────────────────────────────────────

class Verdict(str, Enum):
    ACCEPT = "accept"
    MINOR_REVISION = "minor_revision"
    MAJOR_REVISION = "major_revision"
    REJECT = "reject"


# ─── Event 基类 ───────────────────────────────────────────────────────────────

@dataclass
class PipelineEvent:
    """所有事件的基类，带 common fields。"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = ""


@dataclass
class TokenStreamEvent(PipelineEvent):
    """
    Token 级流式输出。
    agent 正在输出 content（一个或多个 token）。
    用于 TUI 的打字机渲染。
    """
    agent: str = ""
    content: str = ""
    is_final: bool = False  # True = 此 token 是最终块（full message 完成）

    def __repr__(self) -> str:
        tail = self.content[:40] + ("..." if len(self.content) > 40 else "")
        return f"TokenStream(agent={self.agent}, len={len(self.content)}, final={self.is_final})"


@dataclass
class AgentMessageEvent(PipelineEvent):
    """
    完整的 Agent 输出消息。
    在 Agent 完成一次响应后发出。
    """
    agent: str = ""
    stage: Stage = Stage.UNKNOWN
    raw_content: str = ""
    parsed_payload: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    is_handoff: bool = False
    handoff_target: str = ""  # 如果 is_handoff=True，指目标 agent

    def __repr__(self) -> str:
        return f"AgentMessage(agent={self.agent}, stage={self.stage.value}, handoff={self.is_handoff})"


@dataclass
class StateUpdateEvent(PipelineEvent):
    """
    Pipeline 状态机跃迁。
    每次 stage 变更时发出。
    """
    from_stage: Stage = Stage.UNKNOWN
    to_stage: Stage = Stage.UNKNOWN
    agent: str = ""
    verdict: Verdict | None = None  # 仅 review 阶段有
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"StateUpdate({self.from_stage.value} → {self.to_stage.value}, agent={self.agent})"


@dataclass
class CostUpdateEvent(PipelineEvent):
    """
    成本统计更新。
    每次 LLM 调用完成后从 adapter.actual_usage() 聚合。
    """
    agent: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_cny: float = 0.0
    cumulative_cny: float = 0.0
    budget_cap_cny: float = 0.0
    budget_pct: float = 0.0  # cumulative_cny / budget_cap_cny * 100

    @property
    def budget_warning(self) -> bool:
        return self.budget_pct >= 80.0

    def __repr__(self) -> str:
        return f"CostUpdate({self.agent}, cumulative=¥{self.cumulative_cny:.4f}, {self.budget_pct:.1f}%/{self.budget_cap_cny})"


@dataclass
class ErrorEvent(PipelineEvent):
    """
    Pipeline 错误。
    is_recoverable = True 时 TUI 应显示错误但继续运行；
    is_recoverable = False 时 pipeline 已终止。
    """
    agent: str = ""
    stage: Stage = Stage.UNKNOWN
    message: str = ""
    is_recoverable: bool = True
    exception_type: str = ""
    exception_msg: str = ""

    def __repr__(self) -> str:
        recoverable = "RECOVERABLE" if self.is_recoverable else "FATAL"
        return f"Error({recoverable}, {self.agent}, {self.message[:60]})"


@dataclass
class HumanInterruptEvent(PipelineEvent):
    """
    人工打断命令（通过 InterruptManager 注入）。
    TUI 收到后应更新 UI 状态并可选响应。
    """
    command: str = ""      # 完整命令如 "/pause"
    raw_input: str = ""    # 用户原始输入
    args: dict[str, Any] = field(default_factory=dict)  # 解析后参数

    def __repr__(self) -> str:
        return f"HumanInterrupt({self.command}, args={self.args})"


@dataclass
class CompletionEvent(PipelineEvent):
    """
    Pipeline 正常结束。
    """
    session_id: str = ""
    final_stage: Stage = Stage.UNKNOWN
    total_messages: int = 0
    total_cost_cny: float = 0.0
    word_count: int = 0
    output_path: str = ""

    def __repr__(self) -> str:
        return f"Completion(session={self.session_id[:8]}, cost=¥{self.total_cost_cny:.4f}, words={self.word_count})"


# ─── Union 类型别名 ───────────────────────────────────────────────────────────

PipelineEventT = (
    TokenStreamEvent
    | AgentMessageEvent
    | StateUpdateEvent
    | CostUpdateEvent
    | ErrorEvent
    | HumanInterruptEvent
    | CompletionEvent
)

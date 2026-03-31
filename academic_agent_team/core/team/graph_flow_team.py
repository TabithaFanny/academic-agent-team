"""
core/team/graph_flow_team.py

对齐 PRD Section 7.5：AutoGen 0.7 GraphFlow 团队编排器。

团队拓扑（单向流水线 + reviewer 可退回 writer）：
    ┌─────────┐     ┌───────────┐     ┌───────┐     ┌──────────┐     ┌──────────┐
    │ advisor │────▶│ researcher │────▶│ writer │────▶│ reviewer │────▶│ polisher │
    └─────────┘     └───────────┘     └───────┘     └──────────┘     └──────────┘
                                               ▲         │
                                               │         │
                                          major_rev                         (reviewer → writer = major_revision 退回)

设计要点：
- 每个 Agent 的 handoffs[] 列表驱动自动路由（AutoGen 0.7 内置机制）
- DiGraphBuilder 定义节点和边，提供显式拓扑约束
- MaxMessageTermination 防止无限循环（max=100）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow

from academic_agent_team.core.agents.autogen_agents import (
    ADVISOR,
    RESEARCHER,
    WRITER,
    create_advisor_agent,
    create_polisher_agent,
    create_reviewer_agent,
    create_researcher_agent,
    create_user_proxy,
    create_writer_agent,
)
from academic_agent_team.core.autogen_adapter import ModelClientAdapter

if TYPE_CHECKING:
    from autogen_core.models import ChatCompletionClient

__all__ = ["AcademicTeam", "build_academic_team"]


# ─── AcademicTeam ──────────────────────────────────────────────────────────────


class AcademicTeam:
    """
    AutoGen 0.7 GraphFlow 学术论文团队。

    参数：
        flow: GraphFlow 实例
        topic: 研究课题
        journal: 目标期刊
        session_id: 会话 ID
    """

    def __init__(
        self,
        flow: GraphFlow,
        topic: str,
        journal: str,
        session_id: str,
    ) -> None:
        self._flow = flow
        self.topic = topic
        self.journal = journal
        self.session_id = session_id

    async def run(self) -> TaskResult:
        """执行完整流水线（advisor → researcher → writer → reviewer → polisher）。"""
        task = self._build_task_prompt()
        return await self._flow.run(task=task)

    async def run_stream(self):
        """
        流式执行，流式产出消息（用于 TUI 实时显示）。

        Yields：
            BaseAgentEvent | BaseChatMessage | TaskResult
        """
        task = self._build_task_prompt()
        async for msg in self._flow.run_stream(task=task):
            yield msg

    def _build_task_prompt(self) -> str:
        return (
            f"【会话 ID】{self.session_id}\n"
            f"【研究课题】{self.topic}\n"
            f"【目标期刊】{self.journal}\n\n"
            f"请以选题顾问身份开始，分析以上课题，"
            f"输出 JSON 格式的 topic_done payload，完成后自动进入下一阶段。"
        )

    async def reset(self) -> None:
        """重置团队状态（用于 resume）。"""
        await self._flow.reset()


# ─── Team 工厂函数 ─────────────────────────────────────────────────────────────


def build_academic_team(
    *,
    advisor_client: "ChatCompletionClient",
    researcher_client: "ChatCompletionClient",
    writer_client: "ChatCompletionClient",
    reviewer_client: "ChatCompletionClient",
    polisher_client: "ChatCompletionClient",
    topic: str,
    journal: str,
    session_id: str,
    max_messages: int = 100,
) -> AcademicTeam:
    """
    构建学术论文写作团队（对齐 PRD Section 7.5 Pipeline）。

    参数：
        *_client: 各 Agent 对应的 ChatCompletionClient（由 ModelClientAdapter 包装）
        topic: 研究课题
        journal: 目标期刊（中文核心/CSSCI/IEEE Trans/CCF-A）
        session_id: 会话 ID
        max_messages: 最大消息数（防止无限循环，默认 100）

    返回：
        AcademicTeam 实例

    用法：
        team = build_academic_team(
            advisor_client=ModelClientAdapter(AnthropicClient(...)),
            researcher_client=ModelClientAdapter(DeepSeekClient(...)),
            ...
            topic="大模型在学术写作中的应用",
            journal="中文核心",
            session_id="s-001",
        )
        result = await team.run()
    """
    # ── 创建 5 个 Agent ────────────────────────────────────────────────────
    advisor = create_advisor_agent(advisor_client)
    researcher = create_researcher_agent(researcher_client)
    writer = create_writer_agent(writer_client)
    reviewer = create_reviewer_agent(reviewer_client)
    polisher = create_polisher_agent(polisher_client)
    user_proxy = create_user_proxy()

    # ── 构建 DiGraph ────────────────────────────────────────────────────────
    # AutoGen 0.7 GraphFlow 使用 DiGraphBuilder 定义拓扑。
    # 注意：reviewer ↔ writer 的循环（major_revision 退回）由 reviewer.handoffs[]
    # 内部驱动，不在 DiGraph 中用无条件边表示（否则触发 cycle 检测错误）。
    # 终止边 polisher → user_proxy 是显式的（无条件终止）。
    graph = (
        DiGraphBuilder()
        .add_node(advisor)
        .add_node(researcher)
        .add_node(writer)
        .add_node(reviewer)
        .add_node(polisher)
        .add_node(user_proxy)
        .set_entry_point(advisor)
        .add_edge(advisor, researcher)
        .add_edge(researcher, writer)
        .add_edge(writer, reviewer)
        .add_edge(reviewer, polisher)  # minor/accept → polisher
        # reviewer → writer 由 reviewer.handoffs[] 中的 Handoff 驱动（major_revision 退回）
        .add_edge(polisher, user_proxy)  # 终止 → user_proxy
        .build()
    )

    # ── 终止条件 ────────────────────────────────────────────────────────────
    termination = MaxMessageTermination(max_messages=max_messages)

    # ── GraphFlow ───────────────────────────────────────────────────────────
    flow = GraphFlow(
        participants=[advisor, researcher, writer, reviewer, polisher, user_proxy],
        graph=graph,
        termination_condition=termination,
        max_turns=max_messages,
    )

    return AcademicTeam(flow=flow, topic=topic, journal=journal, session_id=session_id)

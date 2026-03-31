"""
学术 Agent Team — AutoGen 0.7 GraphFlow 编排器。

实现 PRD 7.5 定义的固定流水线：
  advisor → researcher → writer → reviewer → polisher → export

支持：
  - 线性顺序推进（PRD 默认 autopilot）
  - 人工介入（UserProxyAgent 节点）
  - 状态机约束（不允许跳阶段）
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.base._termination import TerminationCondition
from autogen_agentchat.messages import BaseChatMessage
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow

from academic_agent_team.agents.advisor import AdvisorAgent
from academic_agent_team.agents.polisher import PolisherAgent
from academic_agent_team.agents.researcher import ResearcherAgent
from academic_agent_team.agents.reviewer import ReviewerAgent
from academic_agent_team.agents.writer import WriterAgent
from academic_agent_team.config.models import AGENT_MODEL_MAP
from academic_agent_team.contracts.agent_contracts import (
    ERROR_CODES,
    ContractValidationError,
    validate_payload_dict,
)
from academic_agent_team.core.clients.autogen_adapter import ModelClientAdapter
from academic_agent_team.session_logger import SessionLogger
from academic_agent_team.storage.db import (
    connect,
    create_session,
    insert_artifact,
    insert_cost,
    insert_message,
    insert_raw_response,
    insert_version,
    mark_artifacts_stale_from_stage,
    update_session_run_mode,
    update_session_stage,
)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json_response(text: str) -> dict:
    """从 LLM 输出中提取 JSON，兼容 markdown code block 和截断。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    candidates = re.findall(r"\{[\s\S]*\}", text)
    for candidate in reversed(candidates):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return {}


def _get_client_for_role(role: str, provider: str | None = None, model: str | None = None):
    """根据 role 从 config 获取适配后的 ChatCompletionClient。"""
    from academic_agent_team.config.models import get_model_spec
    from academic_agent_team.core.clients.mock_client import MockClient

    if provider is None:
        provider, model_name = AGENT_MODEL_MAP.get(role, ("mock", "default"))
    else:
        model_name = model or "default"

    spec = get_model_spec(provider, model_name)
    base = spec.client_class()

    if isinstance(base, MockClient):
        return ModelClientAdapter(base)

    # 真实 client 暂时用 MiniMax/OpenAI，暂不接 Anthropic/DeepSeek
    if provider == "minimax":
        from academic_agent_team.core.clients.minimax_client import MiniMaxClient
        return ModelClientAdapter(MiniMaxClient())
    elif provider == "openai":
        from academic_agent_team.core.clients.openai_client import OpenAIClient
        return ModelClientAdapter(OpenAIClient())
    else:
        return ModelClientAdapter(base)


class ExportTermination(TerminationCondition):
    """自定义终止条件：polisher 完成即终止。"""

    def __init__(self):
        self._export_done = False

    async def should_terminate(self, messages: list[BaseChatMessage]) -> bool:
        # 检查最后一条消息来源是否是 polisher
        if messages:
            last = messages[-1]
            source = getattr(last, "source", "") or getattr(last, "name", "")
            if source == "polisher":
                return True
        return False


def build_pipeline_team() -> tuple[GraphFlow, dict[str, AssistantAgent]]:
    """
    构建学术论文写作 5-Agent 流水线团队。

    流水线拓扑：
        [user] → advisor → researcher → writer → reviewer → polisher

    Returns:
        (GraphFlow 实例, {role: Agent 实例}字典)
    """
    # 创建 5 个 Agent
    advisor = AdvisorAgent(model_client=_get_client_for_role("advisor"))
    researcher = ResearcherAgent(model_client=_get_client_for_role("researcher"))
    writer = WriterAgent(model_client=_get_client_for_role("writer"))
    reviewer = ReviewerAgent(model_client=_get_client_for_role("reviewer"))
    polisher = PolisherAgent(model_client=_get_client_for_role("polisher"))
    user_proxy = UserProxyAgent(name="user_proxy")

    agents = {
        "advisor": advisor,
        "researcher": researcher,
        "writer": writer,
        "reviewer": reviewer,
        "polisher": polisher,
        "user_proxy": user_proxy,
    }

    # 构建线性流水线图
    builder = DiGraphBuilder()
    builder.add_node(advisor)
    builder.add_node(researcher)
    builder.add_node(writer)
    builder.add_node(reviewer)
    builder.add_node(polisher)
    builder.add_node(user_proxy)

    # 线性顺序边
    builder.add_edge(user_proxy, advisor)
    builder.add_edge(advisor, researcher)
    builder.add_edge(researcher, writer)
    builder.add_edge(writer, reviewer)
    builder.add_edge(reviewer, polisher)
    builder.add_edge(polisher, user_proxy)

    builder.set_entry_point(user_proxy)

    team = GraphFlow(
        participants=[advisor, researcher, writer, reviewer, polisher, user_proxy],
        graph=builder.build(),
        termination_condition=ExportTermination(),
        description="学术论文写作 Agent Team",
    )

    return team, agents


async def run_autogen_pipeline(
    base_dir: Path,
    topic: str,
    journal: str,
    run_mode: str = "autopilot",
    budget_cap_cny: float = 35.0,
) -> str:
    """
    运行 AutoGen GraphFlow 流水线的协程版本。

    与 run_pipeline() 接口兼容，用于替换过程式 pipeline。
    """
    session_store = base_dir / "session_store"
    db_path = session_store / "sessions.db"
    conn = connect(db_path)
    session_id = create_session(
        conn=conn,
        topic=topic,
        journal_type=journal,
        language="zh",
        model_config=AGENT_MODEL_MAP,
        run_mode=run_mode,
        budget_cap_cny=budget_cap_cny,
    )

    logger = SessionLogger(session_store / "logs" / f"{session_id}.log")
    output_dir = base_dir / "output" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    team, agents = build_pipeline_team()
    total_cost = 0.0
    stage_map = {
        "advisor": "topic_done",
        "researcher": "literature_done",
        "writer": "writing_done",
        "reviewer": "review_done",
        "polisher": "polish_done",
    }

    logger.append({
        "event": "pipeline_start",
        "ts": _ts(),
        "session_id": session_id,
        "topic": topic,
        "journal": journal,
        "run_mode": run_mode,
    })

    # 运行 team（异步迭代器）
    artifact_content: dict[str, str] = {}
    async for msg in team.run(task=f"课题：{topic}，目标期刊：{journal}"):
        source = getattr(msg, "source", "") or getattr(msg, "name", "")
        content = getattr(msg, "content", "") or ""

        # 记录消息
        if source in stage_map:
            stage = stage_map[source]
            insert_message(
                conn=conn,
                session_id=session_id,
                sender=source,
                receiver="team",
                stage=stage,
                content=content,
                metadata={"agent": source},
            )
            artifact_content[source] = content

        # JSON 解析并验证 → 落盘
        if source in stage_map:
            stage = stage_map[source]
            parsed = _parse_json_response(content)
            if parsed:
                try:
                    validated = validate_payload_dict(parsed)
                    (output_dir / f"{stage}.json").write_text(
                        json.dumps(validated, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    artifact_content[f"{source}_validated"] = json.dumps(validated, ensure_ascii=False)
                    logger.append({
                        "event": "stage_complete",
                        "ts": _ts(),
                        "session_id": session_id,
                        "agent": source,
                        "stage": stage,
                    })
                except ContractValidationError as e:
                    logger.append({
                        "event": "error",
                        "ts": _ts(),
                        "session_id": session_id,
                        "error_code": "E007",
                        "agent": source,
                        "errors": e.errors,
                    })
            update_session_stage(conn, session_id, stage)

    # 最终快照
    final_text = "\n\n".join(artifact_content.get(f"{s}_validated", "") for s in stage_map)
    if artifact_content.get("polisher_validated"):
        pol = json.loads(artifact_content["polisher_validated"])
        sections = pol.get("polished_sections", {})
        if isinstance(sections, dict):
            final_text = "\n\n".join(sections.values())

    (output_dir / "paper.md").write_text(final_text or "", encoding="utf-8")

    update_session_stage(conn, session_id, stage="export", status="completed")
    logger.append({
        "event": "pipeline_complete",
        "ts": _ts(),
        "session_id": session_id,
        "total_cost_cny": round(total_cost, 6),
    })
    conn.close()

    return session_id

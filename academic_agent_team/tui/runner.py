"""
academic_agent_team/tui/runner.py

PipelineRunner 抽象层 + 两套实现。

设计原则：
- PipelineRunner 是 Protocol（duck typing），不继承具体类
- 两套实现 (SequentialRunner / AutoGenRunner) 均返回 AsyncIterator[PipelineEvent]
- TUI 只依赖 Protocol，不知道也不关心底层引擎
- 所有 token 级别的事件都从流式接口产生
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Protocol, TYPE_CHECKING

from academic_agent_team.tui.events import (
    AgentMessageEvent,
    CompletionEvent,
    CostUpdateEvent,
    ErrorEvent,
    PipelineEventT,
    Stage,
    StateUpdateEvent,
    TokenStreamEvent,
    Verdict,
)

if TYPE_CHECKING:
    from academic_agent_team.core.autogen_adapter import ModelClientAdapter
    from academic_agent_team.tui.interrupt import InterruptManager
else:
    # 运行时导入（避免 TYPE_CHECKING 时仅做类型检查）
    from academic_agent_team.tui.interrupt import InterruptManager  # noqa: F401,E402


# ─── PipelineConfig ───────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    """统一配置，两套 runner 共用。"""
    base_dir: Path
    topic: str
    journal: str
    run_mode: str = "autopilot"        # autopilot | manual
    budget_cap_cny: float = 35.0
    use_mock: bool = False
    model_overrides: dict[str, str] = field(default_factory=dict)
    # InterruptManager 由 TUI 注入，pipeline 端轮询
    interrupt_manager: "InterruptManager | None" = None
    # api_key / base_url / model — 仅 sequential 引擎需要
    api_key: str = ""
    base_url: str = ""
    model: str = ""


# ─── PipelineRunner Protocol ───────────────────────────────────────────────────

class PipelineRunner(Protocol):
    """
    Pipeline 抽象接口。

    实现要求：
    1. run() 是 async generator（AsyncIterator[PipelineEventT]）
    2. 每产出任何事件必须包含 session_id
    3. 支持 interrupt_queue 注入的 /abort（检查 asyncio.Event 或 Queue）
    4. TokenStreamEvent.is_final=False 时 TUI 追加显示，
       is_final=True 时 TUI 收起打字机状态
    """

    config: PipelineConfig

    async def run(self) -> AsyncIterator[PipelineEventT]:
        """执行 pipeline，yield 事件流。"""
        ...


# ─── AutoGenRunner ────────────────────────────────────────────────────────────

class AutoGenRunner:
    """
    AutoGen 0.7 GraphFlow pipeline 的事件化包装。

    职责：
    - 封装 build_academic_team() + team.run_stream()
    - 将 AutoGen 消息 (TextMessage / HandoffMessage) → PipelineEvent
    - 从 ModelClientAdapter.actual_usage() 聚合 CostUpdateEvent
    - 正确处理 max_messages 终止条件
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self._total_cost: float = 0.0
        self._stage_outputs: dict[str, dict] = {}
        self._current_agent: str = ""
        self._current_tokens: str = ""
        self._interrupted = False

    async def run(self) -> AsyncIterator[PipelineEventT]:
        from academic_agent_team.core.agents.autogen_agents import (
            ADVISOR, REVIEWER, RESEARCHER, POLISHER, WRITER,
            create_advisor_agent,
            create_polisher_agent,
            create_reviewer_agent,
            create_researcher_agent,
            create_user_proxy,
            create_writer_agent,
        )
        from academic_agent_team.core.autogen_adapter import ModelClientAdapter
        from academic_agent_team.core.clients.mock_client import MockClient
        from academic_agent_team.core.team.graph_flow_team import build_academic_team
        from autogen_agentchat.messages import HandoffMessage, TextMessage

        config = self.config
        session_id = ""

        # ── Build clients ─────────────────────────────────────────────────
        def _client_for(agent: str) -> "ModelClientAdapter":
            if config.use_mock:
                return ModelClientAdapter(MockClient(), provider_name="mock")
            from academic_agent_team.pipeline_real import _get_client_for_agent
            client, model_id = _get_client_for_agent(agent)
            return ModelClientAdapter(client, provider_name=model_id)

        advisor_client = _client_for("advisor")
        researcher_client = _client_for("researcher")
        writer_client = _client_for("writer")
        reviewer_client = _client_for("reviewer")
        polisher_client = _client_for("polisher")
        all_clients = {
            "advisor": advisor_client,
            "researcher": researcher_client,
            "writer": writer_client,
            "reviewer": reviewer_client,
            "polisher": polisher_client,
        }

        # ── Build team ───────────────────────────────────────────────────
        team = build_academic_team(
            advisor_client=advisor_client,
            researcher_client=researcher_client,
            writer_client=writer_client,
            reviewer_client=reviewer_client,
            polisher_client=polisher_client,
            topic=config.topic,
            journal=config.journal,
            session_id="",  # 运行时填充
            max_messages=100,
        )

        # ── Iterate events ────────────────────────────────────────────────
        token_flush_count = 0
        FLUSH_EVERY_N_CHARS = 20  # 每 20 字 yield 一次 TokenStreamEvent

        try:
            async for msg in team.run_stream():
                # ── 检查打断（轮询延迟 ≤ 50ms）─────────────────────────────────
                if config.interrupt_manager is not None:
                    signal = await config.interrupt_manager.wait_for_signal(timeout=0.05)
                    if signal is not None:
                        from academic_agent_team.tui.interrupt import InterruptKind
                        if signal.kind == InterruptKind.CANCEL:
                            self._interrupted = True
                            yield ErrorEvent(
                                session_id=session_id,
                                agent=self._current_agent,
                                message="Pipeline cancelled by user.",
                                is_recoverable=False,
                            )
                            return
                        # pause/resume 等其他信号记录但不中断主流程
                        from academic_agent_team.tui.events import HumanInterruptEvent
                        yield HumanInterruptEvent(
                            session_id=session_id,
                            command=signal.kind.value,
                            raw_input=signal.payload,
                            args={"metadata": signal.metadata},
                        )

                # ── TextMessage（Agent 输出）──────────────────────────────
                if isinstance(msg, TextMessage):
                    agent: str = msg.source
                    raw_content: str = msg.content if isinstance(msg.content, str) else str(msg.content)

                    # 第一次 TextMessage → 从 task prompt 中提 session_id
                    if not session_id:
                        # 从 team 内部 log 推算（简版：用 uuid 前 8 位）
                        import uuid as _uuid
                        session_id = str(_uuid.uuid4())

                    self._current_agent = agent
                    self._current_tokens += raw_content

                    # 实时 token 流事件
                    token_flush_count += len(raw_content)
                    is_final = False
                    if token_flush_count >= FLUSH_EVERY_N_CHARS:
                        yield TokenStreamEvent(
                            session_id=session_id,
                            agent=agent,
                            content=self._current_tokens,
                            is_final=False,
                        )
                        token_flush_count = 0

                    # 阶段映射
                    stage = Stage.from_agent_name(agent)

                    # HandoffMessage 实际由 HandoffMessage 类型处理，
                    # 但 TextMessage 末尾可能含 handoff 触发内容（如 "TERMINATE"）
                    # 这里通过内容判断是否需要发 StateUpdate

                # ── HandoffMessage ─────────────────────────────────────────
                elif isinstance(msg, HandoffMessage):
                    target: str = msg.target
                    from_agent: str = getattr(msg, "source", "?")

                    # 刷新 token（is_final）
                    if self._current_tokens:
                        yield TokenStreamEvent(
                            session_id=session_id,
                            agent=self._current_agent,
                            content=self._current_tokens,
                            is_final=True,
                        )
                        self._current_tokens = ""
                        token_flush_count = 0

                    # 解析 verdict（reviewer → writer 时）
                    verdict: Verdict | None = None
                    to_stage = Stage.from_agent_name(target)
                    if from_agent == "reviewer" and self._stage_outputs.get("reviewer"):
                        v = self._stage_outputs["reviewer"].get("verdict", "")
                        verdict = Verdict(v) if v in [x.value for x in Verdict] else None

                    # 解析 payload
                    raw = self._stage_outputs.get(from_agent, {})
                    if self._current_tokens:
                        from academic_agent_team.pipeline_real import _parse_json_response
                        raw = _parse_json_response(self._current_tokens)

                    from_stage = Stage.from_agent_name(from_agent)

                    yield AgentMessageEvent(
                        session_id=session_id,
                        agent=from_agent,
                        stage=from_stage,
                        raw_content=self._current_tokens,
                        parsed_payload=raw,
                        is_handoff=True,
                        handoff_target=target,
                    )

                    yield StateUpdateEvent(
                        session_id=session_id,
                        from_stage=from_stage,
                        to_stage=to_stage,
                        agent=from_agent,
                        verdict=verdict,
                        metadata={"handoff_target": target},
                    )

                    self._stage_outputs[from_agent] = raw

                    # cost 更新
                    cumulative = self._aggregate_cost(all_clients)
                    for agent_name, client in all_clients.items():
                        usage = client.actual_usage()
                        cost_cny = self._estimate_cost(agent_name, usage.prompt_tokens, usage.completion_tokens)
                        yield CostUpdateEvent(
                            session_id=session_id,
                            agent=agent_name,
                            prompt_tokens=usage.prompt_tokens,
                            completion_tokens=usage.completion_tokens,
                            cost_cny=cost_cny,
                            cumulative_cny=cumulative,
                            budget_cap_cny=config.budget_cap_cny,
                            budget_pct=cumulative / config.budget_cap_cny * 100,
                        )

        except Exception as e:
            yield ErrorEvent(
                session_id=session_id,
                agent=self._current_agent,
                message=str(e),
                is_recoverable=False,
                exception_type=type(e).__name__,
                exception_msg=str(e),
            )
            return

        # ── Completion ────────────────────────────────────────────────────
        if not self._interrupted:
            # 最终 cost
            cumulative = self._aggregate_cost(all_clients)
            word_count = self._stage_outputs.get("writer", {}).get("word_count", 0)

            yield CompletionEvent(
                session_id=session_id,
                final_stage=Stage.POLISH,
                total_messages=len(self._stage_outputs),
                total_cost_cny=cumulative,
                word_count=word_count,
                output_path=str(config.base_dir / "output" / session_id),
            )

    # ── Cost helpers ───────────────────────────────────────────────────────────

    def _aggregate_cost(self, clients: dict[str, "ModelClientAdapter"]) -> float:
        total = 0.0
        for name, client in clients.items():
            usage = client.actual_usage()
            total += self._estimate_cost(name, usage.prompt_tokens, usage.completion_tokens)
        return total

    def _estimate_cost(self, agent: str, prompt_tokens: int, completion_tokens: int) -> float:
        """根据 agent 类型估算 CNY 成本（与 models.py 中的定价对齐）。"""
        rates: dict[str, tuple[float, float]] = {
            "advisor":     (21.6 / 1_000_000, 108.0 / 1_000_000),   # claude-sonnet
            "researcher":  (0.27 * 7.2 / 1_000_000, 1.1 * 7.2 / 1_000_000),  # deepseek
            "writer":      (0.27 * 7.2 / 1_000_000, 1.1 * 7.2 / 1_000_000),
            "reviewer":    (21.6 / 1_000_000, 108.0 / 1_000_000),
            "polisher":     (0.27 * 7.2 / 1_000_000, 1.1 * 7.2 / 1_000_000),
        }
        rate = rates.get(agent, (0.5 / 1_000_000, 2.0 / 1_000_000))
        return prompt_tokens * rate[0] + completion_tokens * rate[1]


# ─── SequentialRunner ──────────────────────────────────────────────────────────

import re as _re

_AGENT_STAGES = {
    "advisor":     (Stage.TOPIC,     "选题顾问"),
    "researcher":  (Stage.LITERATURE, "文献研究员"),
    "writer":      (Stage.WRITING,   "论文写手"),
    "reviewer":    (Stage.REVIEW,    "审稿人"),
    "polisher":    (Stage.POLISH,    "润色师"),
}
_SEQUENTIAL_AGENT_NAMES = ["advisor", "researcher", "writer", "reviewer", "polisher"]


class SequentialRunner:
    """
    顺序 Pipeline 的事件化包装（对应 run_pipeline()）。

    每阶段直接调用 client.complete()，每步之间 yield 完整事件流：
    TokenStream → AgentMessage → StateUpdate → CostUpdate
    支持 interrupt_queue 打断（≤ 50ms 轮询间隔）。
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self._outputs: dict[str, dict] = {}
        self._cumulative_cost: float = 0.0

    async def run(self) -> AsyncIterator[PipelineEventT]:
        from academic_agent_team.core.agent_prompts import (
            ADVISOR_SYSTEM, POLISHER_SYSTEM, PROMPT_TEMPLATES,
            RESEARCHER_SYSTEM, REVIEWER_SYSTEM, WRITER_SYSTEM,
        )
        from academic_agent_team.core.clients.mock_client import MockClient
        from academic_agent_team.pipeline_real import (
            _get_client_for_agent, connect, create_session, build_role_profile,
        )
        from academic_agent_team.session_logger import SessionLogger
        from academic_agent_team.storage.db import (
            insert_artifact, insert_raw_response, update_session_stage,
        )

        cfg = self.config
        session_store = cfg.base_dir / "session_store"
        db_path = session_store / "sessions.db"
        conn = connect(db_path)

        role_snapshot = build_role_profile()
        session_id = create_session(
            conn=conn, topic=cfg.topic, journal_type=cfg.journal,
            language="zh", model_config=role_snapshot,
            run_mode=cfg.run_mode, budget_cap_cny=cfg.budget_cap_cny,
        )
        output_dir = cfg.base_dir / "output" / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        logger = SessionLogger(session_store / "logs" / f"{session_id}.log")
        logger.append({
            "event": "tui_pipeline_start", "ts": _ts_iso(),
            "session_id": session_id, "engine": "sequential",
        })

        yield StateUpdateEvent(
            session_id=session_id,
            from_stage=Stage.UNKNOWN, to_stage=Stage.TOPIC, agent="advisor",
        )

        direction = cfg.topic

        for agent_name in _SEQUENTIAL_AGENT_NAMES:
            # ── Interrupt 轮询（≤ 50ms）─────────────────────────────────────
            if self._check_abort():
                yield ErrorEvent(
                    session_id=session_id, agent=agent_name,
                    message="Pipeline aborted by user.", is_recoverable=False,
                )
                return

            stage_enum, _ = _AGENT_STAGES[agent_name]

            # 状态跃迁
            from_stage = Stage.from_agent_name(
                _SEQUENTIAL_AGENT_NAMES[_SEQUENTIAL_AGENT_NAMES.index(agent_name) - 1]
            ) if agent_name != "advisor" else Stage.UNKNOWN
            yield StateUpdateEvent(
                session_id=session_id,
                from_stage=from_stage, to_stage=stage_enum, agent=agent_name,
            )

            # Client
            client, model_id = _get_client_for_agent(agent_name)
            if cfg.use_mock:
                client = MockClient()

            # Prompt
            if agent_name == "advisor":
                prompt = PROMPT_TEMPLATES["advisor"].format(topic=cfg.topic, journal=cfg.journal)
                system = ADVISOR_SYSTEM
            elif agent_name == "researcher":
                prompt = PROMPT_TEMPLATES["researcher"].format(direction=direction)
                system = RESEARCHER_SYSTEM
            elif agent_name == "writer":
                matrix = self._outputs.get("researcher", {}).get("literature_matrix", "")
                prompt = PROMPT_TEMPLATES["writer"].format(direction=direction, literature_matrix=matrix)
                system = WRITER_SYSTEM
            elif agent_name == "reviewer":
                sections = self._outputs.get("writer", {}).get("sections", {})
                paper = "\n\n".join(sections.values()) if isinstance(sections, dict) else str(sections)
                prompt = PROMPT_TEMPLATES["reviewer"].format(paper_draft=paper)
                system = REVIEWER_SYSTEM
            else:
                sections = self._outputs.get("writer", {}).get("sections", {})
                paper = "\n\n".join(sections.values()) if isinstance(sections, dict) else str(sections)
                prompt = PROMPT_TEMPLATES["polisher"].format(paper_draft=paper)
                system = POLISHER_SYSTEM

            # LLM 调用（线程池，避免阻塞事件循环）
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None,
                lambda: client.complete(prompt=prompt, system=system, max_tokens=8192),
            )
            content = raw.content

            # Token 流（分批，每 30 字符一块）
            for chunk in _chunk(content, 30):
                yield TokenStreamEvent(
                    session_id=session_id, agent=agent_name,
                    content=chunk, is_final=False,
                )
            yield TokenStreamEvent(
                session_id=session_id, agent=agent_name,
                content="", is_final=True,
            )

            # 解析 JSON payload
            parsed = _parse_json(content)
            parsed.setdefault("stage", stage_enum.value)
            parsed.setdefault("session_id", session_id)
            self._outputs[agent_name] = parsed
            if agent_name == "advisor":
                direction = parsed.get("selected_direction", cfg.topic)

            # DB 持久化
            insert_raw_response(conn, session_id, agent_name, stage_enum.value,
                             content, model_id, raw.cost_cny)
            insert_artifact(conn, session_id, stage_enum.value, f"{agent_name}_output",
                          json.dumps(parsed, ensure_ascii=False, indent=2))
            update_session_stage(conn, session_id, stage_enum.value)

            # 成本
            self._cumulative_cost += raw.cost_cny
            yield CostUpdateEvent(
                session_id=session_id, agent=agent_name,
                prompt_tokens=raw.input_tokens, completion_tokens=raw.output_tokens,
                cost_cny=raw.cost_cny, cumulative_cny=self._cumulative_cost,
                budget_cap_cny=cfg.budget_cap_cny,
                budget_pct=self._cumulative_cost / cfg.budget_cap_cny * 100,
            )

            # 消息完成
            is_last = agent_name == "polisher"
            idx = _SEQUENTIAL_AGENT_NAMES.index(agent_name)
            yield AgentMessageEvent(
                session_id=session_id, agent=agent_name, stage=stage_enum,
                raw_content=content, parsed_payload=parsed,
                token_count=raw.input_tokens + raw.output_tokens,
                is_handoff=not is_last,
                handoff_target=(
                    _SEQUENTIAL_AGENT_NAMES[idx + 1]
                    if not is_last and idx + 1 < len(_SEQUENTIAL_AGENT_NAMES)
                    else ""
                ),
            )
            logger.append({
                "event": f"{agent_name}_done", "ts": _ts_iso(),
                "session_id": session_id, "stage": stage_enum.value,
                "cost_cny": raw.cost_cny,
            })

        # 写文件 + 完成
        sections = self._outputs.get("writer", {}).get("sections", {})
        final_text = "\n\n".join(sections.values()) if isinstance(sections, dict) else str(sections)
        word_count = self._outputs.get("writer", {}).get("word_count", 0) or len(final_text)
        (output_dir / "paper.md").write_text(final_text, encoding="utf-8")
        update_session_stage(conn, session_id, stage="export", status="completed")
        conn.close()

        yield CompletionEvent(
            session_id=session_id, final_stage=Stage.POLISH,
            total_messages=len(_SEQUENTIAL_AGENT_NAMES),
            total_cost_cny=self._cumulative_cost, word_count=word_count,
            output_path=str(output_dir),
        )

    def _check_abort(self) -> bool:
        mgr = self.config.interrupt_manager
        if mgr is None:
            return False
        # InterruptManager.is_cancelled() 是同步的
        if mgr.is_cancelled():
            return True
        # 也检查队首信号是否有 CANCEL
        signal = mgr.peek()
        if signal is not None:
            from academic_agent_team.tui.interrupt import InterruptKind
            if signal.kind == InterruptKind.CANCEL:
                return True
        return False


# ─── 工具函数 ──────────────────────────────────────────────────────────────────

def _ts_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _chunk(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


def _parse_json(content: str) -> dict:
    content = content.strip()
    content = _re.sub(r"^```(?:json)?\n?", "", content)
    content = _re.sub(r"\n?```$", "", content).strip()
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        for m in _re.finditer(r"\{[\s\S]*\}", content):
            try:
                result = json.loads(m.group())
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, TypeError):
                continue
    return {}

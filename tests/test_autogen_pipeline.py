"""
tests/test_autogen_pipeline.py

验证 AutoGen 0.7 GraphFlow 团队集成：
1. MockClient 通过 ModelClientAdapter 适配 AutoGen ChatCompletionClient 接口
2. build_academic_team() 成功构建团队
3. 5 个 Agent 的 handoffs 拓扑正确
4. 端到端运行（Mock 模式）
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from academic_agent_team.core.autogen_adapter import ModelClientAdapter
from academic_agent_team.core.agents.autogen_agents import (
    ADVISOR,
    POLISHER,
    RESEARCHER,
    REVIEWER,
    WRITER,
    create_advisor_agent,
)
from academic_agent_team.core.clients.mock_client import MockClient
from academic_agent_team.core.team.graph_flow_team import build_academic_team


def test_mock_client_adapter_implements_chat_completion_client():
    """MockClient 通过 ModelClientAdapter 实现 AutoGen ChatCompletionClient。"""
    mock = MockClient()
    adapter = ModelClientAdapter(mock, provider_name="mock", max_tokens=4096)
    assert hasattr(adapter, "create")
    assert hasattr(adapter, "create_stream")
    assert hasattr(adapter, "count_tokens")
    assert hasattr(adapter, "actual_usage")
    assert hasattr(adapter, "close")


async def _create_async(adapter, messages):
    return await adapter.create(messages)


def test_mock_client_adapter_create_returns_valid_result():
    """ModelClientAdapter.create() 返回有效的 CreateResult。"""
    mock = MockClient()
    adapter = ModelClientAdapter(mock, provider_name="mock", max_tokens=4096)

    from autogen_core.models import UserMessage

    messages = [UserMessage(content="请生成一个JSON payload", source="user")]
    result = asyncio.run(_create_async(adapter, messages))

    assert result.content  # 非空
    assert result.finish_reason  # 有 finish reason
    assert result.usage.prompt_tokens >= 0
    assert result.usage.completion_tokens >= 0


def test_count_tokens_returns_positive_int():
    """count_tokens() 返回合理的 token 数估算。"""
    from autogen_core.models import UserMessage

    adapter = ModelClientAdapter(MockClient(), provider_name="mock")
    messages = [
        UserMessage(content="这是一个测试消息" * 50, source="user"),
    ]
    count = adapter.count_tokens(messages)
    assert count > 0
    assert isinstance(count, int)


def test_build_academic_team_with_mock_clients():
    """build_academic_team() 用 Mock Client 成功构建（不实际运行）。"""
    mock = MockClient()
    adapter = ModelClientAdapter(mock, provider_name="mock")

    team = build_academic_team(
        advisor_client=adapter,
        researcher_client=adapter,
        writer_client=adapter,
        reviewer_client=adapter,
        polisher_client=adapter,
        topic="测试课题",
        journal="中文核心",
        session_id="test-session-autogen-001",
        max_messages=10,
    )

    assert team.topic == "测试课题"
    assert team.journal == "中文核心"
    assert team.session_id == "test-session-autogen-001"
    assert hasattr(team, "run")
    assert hasattr(team, "run_stream")
    assert hasattr(team, "reset")


def test_autogen_team_run_produces_messages():
    """端到端：AutoGen 团队用 Mock Client 运行，产生消息。"""
    mock = MockClient()
    adapter = ModelClientAdapter(mock, provider_name="mock")

    team = build_academic_team(
        advisor_client=adapter,
        researcher_client=adapter,
        writer_client=adapter,
        reviewer_client=adapter,
        polisher_client=adapter,
        topic="大模型在学术写作中的应用",
        journal="中文核心",
        session_id="test-session-autogen-002",
        max_messages=10,
    )

    # 运行（MockClient 会立即返回固定响应）
    result = asyncio.run(team.run())

    assert result is not None
    assert hasattr(result, "messages")
    assert hasattr(result, "stop_reason")
    # 至少有一些消息（Mock 会循环几次）
    assert len(result.messages) > 0


async def _run_stream_sync(team: "AcademicTeam") -> list:
    messages = []
    async for msg in team.run_stream():
        messages.append(msg)
    return messages


def test_autogen_team_run_stream_yields_messages():
    """流式执行：run_stream() 逐条产出消息。"""
    mock = MockClient()
    adapter = ModelClientAdapter(mock, provider_name="mock")

    team = build_academic_team(
        advisor_client=adapter,
        researcher_client=adapter,
        writer_client=adapter,
        reviewer_client=adapter,
        polisher_client=adapter,
        topic="AI辅助学术研究",
        journal="IEEE Trans",
        session_id="test-session-autogen-003",
        max_messages=8,
    )

    messages = asyncio.run(_run_stream_sync(team))
    assert len(messages) > 0


def test_autogen_agent_handoffs_topology():
    """验证各 Agent 的 handoffs 拓扑符合 pipeline 定义。"""
    mock = MockClient()
    adapter = ModelClientAdapter(mock, provider_name="mock")

    advisor = create_advisor_agent(adapter)
    # handoffs 是 Dict[str, HandoffBase]
    advisor_targets = {h.target for h in advisor._handoffs.values()}
    assert RESEARCHER in advisor_targets

    from academic_agent_team.core.agents.autogen_agents import (
        create_polisher_agent,
        create_reviewer_agent,
        create_researcher_agent,
        create_writer_agent,
    )

    researcher = create_researcher_agent(adapter)
    writer = create_writer_agent(adapter)
    reviewer = create_reviewer_agent(adapter)
    polisher = create_polisher_agent(adapter)

    # researcher → writer
    assert WRITER in {h.target for h in researcher._handoffs.values()}
    # writer → reviewer
    assert REVIEWER in {h.target for h in writer._handoffs.values()}
    # reviewer → polisher 或 writer
    reviewer_targets = {h.target for h in reviewer._handoffs.values()}
    assert WRITER in reviewer_targets
    assert POLISHER in reviewer_targets
    # polisher 无 handoff（终止）
    assert len(polisher._handoffs) == 0

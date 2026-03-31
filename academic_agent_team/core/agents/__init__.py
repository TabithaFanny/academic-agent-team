"""
core/agents/__init__.py

AutoGen 0.7 学术论文 Agent 集合。
每个 Agent 对应一个 stage，由 pipeline 流程统一定义 handoff。
"""

from __future__ import annotations

from academic_agent_team.core.agents.autogen_agents import (
    USER_PROXY_NAME,
    WRITER,
    ADVISOR,
    RESEARCHER,
    REVIEWER,
    POLISHER,
    create_advisor_agent,
    create_polisher_agent,
    create_researcher_agent,
    create_reviewer_agent,
    create_user_proxy,
    create_writer_agent,
)

__all__ = [
    "ADVISOR",
    "RESEARCHER",
    "WRITER",
    "REVIEWER",
    "POLISHER",
    "USER_PROXY_NAME",
    "create_advisor_agent",
    "create_researcher_agent",
    "create_writer_agent",
    "create_reviewer_agent",
    "create_polisher_agent",
    "create_user_proxy",
]

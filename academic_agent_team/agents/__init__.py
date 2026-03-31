"""
Academic Agent Team — AutoGen 0.7 Agent 定义。

每个 Agent 继承 AssistantAgent，接入 AutoGen 0.7 GraphFlow 调度框架。
"""

from __future__ import annotations

from academic_agent_team.agents.advisor import AdvisorAgent
from academic_agent_team.agents.pipelined_team import build_pipeline_team, run_autogen_pipeline
from academic_agent_team.agents.polisher import PolisherAgent
from academic_agent_team.agents.researcher import ResearcherAgent
from academic_agent_team.agents.reviewer import ReviewerAgent
from academic_agent_team.agents.writer import WriterAgent

__all__ = [
    "AdvisorAgent",
    "ResearcherAgent",
    "WriterAgent",
    "ReviewerAgent",
    "PolisherAgent",
    "build_pipeline_team",
    "run_autogen_pipeline",
]

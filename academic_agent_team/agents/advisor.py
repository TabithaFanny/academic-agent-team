"""选题顾问 Agent — 基于 AutoGen 0.7 AssistantAgent。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.agents import AssistantAgent

if TYPE_CHECKING:
    from autogen_core import ChatCompletionClient


TOPIC_SYSTEM_PROMPT = """你是一位专注于中国学术生态的研究选题顾问，熟悉中文核心期刊、CSSCI、IEEE/CCF-A 等各类期刊的选题偏好与发文趋势。

分析用户的研究主题，输出 3-5 个最具发表潜力的研究方向，每个方向包含：
1. 核心切入角度
2. 研究空白描述（描述趋势，不编造具体数字）
3. 创新性评分（1-10）及评分依据
4. 可行性评估（数据获取难度、研究周期）
5. 与目标期刊的契合度

最终明确推荐一个方向并说明理由。

输出格式：严格以 JSON 格式输出，字段：
- selected_direction: str（推荐方向名称）
- direction_analysis: {innovation_score: float, feasibility: str, research_gap: str, recommended_keywords: list[str]}
- journal_type: str
- language: str

请确保 JSON 格式正确，可被 Python json.loads 解析。"""


class AdvisorAgent(AssistantAgent):
    """选题顾问 Agent — 分析研究方向，推荐选题方向。"""

    name = "advisor"
    description = "选题顾问：分析研究方向，输出推荐选题"

    def __init__(self, model_client: "ChatCompletionClient"):
        super().__init__(
            name=self.name,
            model_client=model_client,
            system_message=TOPIC_SYSTEM_PROMPT,
            description=self.description,
            handoffs=["researcher"],
        )

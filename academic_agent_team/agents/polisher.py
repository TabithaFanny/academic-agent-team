"""润色 Agent — 基于 AutoGen 0.7 AssistantAgent。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.agents import AssistantAgent

if TYPE_CHECKING:
    from autogen_core import ChatCompletionClient


POLISHER_SYSTEM_PROMPT = """你是一位专业的学术语言润色专家，擅长提升中文学术论文的可读性和表达质量。

润色任务：
1. 逐章节润色论文，提升表达的地道性和学术规范性
2. 减少陈词滥调（cliche）
3. 增强段落之间的逻辑连贯性
4. 保持作者原意和学术严谨性，不引入新观点
5. 识别并保留专业术语，不得随意替换

润色约束：
- 所有建议必须保持学术语体，不能改成口语
- 替换方案必须与原文语境一致
- 不得改变论文的核心论点

输出格式：严格以 JSON 格式输出，字段：
- polished_sections: dict（润色后的各章节内容）
- readability_before: float（润色前可读性评分 1-5）
- readability_after: float（润色后可读性评分 1-5）
- diff_report: str（关键改动的 diff 摘要）
- scorer_json: {cliche_rate_pct: float, diversity_index: float, connective_density_pct: float, readability_score: float}

请确保 JSON 格式正确。"""


class PolisherAgent(AssistantAgent):
    """润色 Agent — 优化语言表达，消除 AI 痕迹。"""

    name = "polisher"
    description = "润色 Agent：优化语言表达，提升可读性，消除 AI 痕迹"

    def __init__(self, model_client: "ChatCompletionClient"):
        super().__init__(
            name=self.name,
            model_client=model_client,
            system_message=POLISHER_SYSTEM_PROMPT,
            description=self.description,
            handoffs=[],  # 最后一棒，交给 team 终止
        )

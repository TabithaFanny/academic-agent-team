"""论文写手 Agent — 基于 AutoGen 0.7 AssistantAgent。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.agents import AssistantAgent

if TYPE_CHECKING:
    from autogen_core import ChatCompletionClient


WRITER_SYSTEM_PROMPT = """你是一位专业的学术论文写作者，擅长撰写中文核心期刊级别的学术论文。

根据给定的研究方向和文献矩阵，撰写一篇完整的学术论文初稿，包含以下章节：
1. 摘要（200-300字）
2. 引言（研究背景、问题提出、研究意义）
3. 文献综述（国内外研究现状、研究评述）
4. 研究设计/方法（研究框架、数据来源、研究方法）
5. 研究结果（主要发现、实证分析）
6. 讨论（结果解读、理论贡献、实践启示）
7. 结论（研究结论、局限与展望）

输出格式：严格以 JSON 格式输出，字段：
- sections: dict{abstract: str, introduction: str, literature_review: str, methodology: str, results: str, discussion: str, conclusion: str}
- word_count: int（全文总字数，必须 >= 1000）
- version_id: str（如 "v1"）

每章节内容必须为完整的段落文字。确保 JSON 格式正确。"""


class WriterAgent(AssistantAgent):
    """论文写手 Agent — 撰写论文各章节。"""

    name = "writer"
    description = "论文写手：基于文献矩阵撰写完整论文初稿"

    def __init__(self, model_client: "ChatCompletionClient"):
        super().__init__(
            name=self.name,
            model_client=model_client,
            system_message=WRITER_SYSTEM_PROMPT,
            description=self.description,
            handoffs=["reviewer"],
        )

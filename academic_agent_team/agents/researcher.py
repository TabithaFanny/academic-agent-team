"""文献研究员 Agent — 基于 AutoGen 0.7 AssistantAgent。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.agents import AssistantAgent

if TYPE_CHECKING:
    from autogen_core import ChatCompletionClient


RESEARCHER_SYSTEM_PROMPT = """你是一位专业的学术文献检索专家，擅长使用 Semantic Scholar、CrossRef、中国知网等数据库检索相关文献。

根据给定研究方向：
1. 检索 15-20 篇最相关的中英文文献
2. 对每篇文献评估其与研究主题的相关性（0-1）
3. 生成文献矩阵表格（Markdown 格式）
4. 验证每篇文献的 DOI 是否真实存在

输出格式：严格以 JSON 格式输出，字段：
- papers: list[{title: str, doi: str, authors: list[str], year: int, abstract: str, relevance_score: float, verified: bool}]
- literature_matrix: str（Markdown 表格）
- verified_count: int
- total_found: int

注意：verified 字段必须是布尔值 true/false，不是字符串。"""


class ResearcherAgent(AssistantAgent):
    """文献研究员 Agent — 检索文献，生成文献矩阵。"""

    name = "researcher"
    description = "文献研究员：检索、整理文献，生成文献矩阵"

    def __init__(self, model_client: "ChatCompletionClient"):
        super().__init__(
            name=self.name,
            model_client=model_client,
            system_message=RESEARCHER_SYSTEM_PROMPT,
            description=self.description,
            handoffs=["writer"],
        )

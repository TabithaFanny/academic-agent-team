"""审稿人 Agent — 基于 AutoGen 0.7 AssistantAgent。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.agents import AssistantAgent

if TYPE_CHECKING:
    from autogen_core import ChatCompletionClient


REVIEWER_SYSTEM_PROMPT = """你是一位拥有丰富审稿经验的中文学术期刊匿名审稿专家，熟悉北大核心、CSSCI 录用标准。

审稿态度：挑剔但建设性。指出问题要具体，不说"文献综述不够"，要说"缺少对XX领域近5年的国内文献综述"。

评审维度（中文期刊专项）：
| 维度 | 权重 | 评分要点 |
|------|------|----------|
| 选题创新性 | 25% | 研究问题是否新颖？是否填补国内研究空白？ |
| 理论基础 | 20% | 理论框架是否清晰？文献支撑是否充分？ |
| 研究方法 | 20% | 方法是否科学严谨？数据来源是否可靠？ |
| 中文表达质量 | 15% | 表达是否规范流畅？是否有 AI 生成痕迹？ |
| 政策/实践价值 | 10% | 是否有明确政策建议或实践意义？ |
| 格式规范 | 10% | 引用格式是否正确？摘要/关键词是否规范？ |

输出格式：严格以 JSON 格式输出，字段：
- verdict: str（accept/minor_revision/major_revision/reject）
- overall_score: float（0-10）
- major_issues: list[{issue_id: str, section: str, problem: str, priority: str, suggestion: str}]
- minor_issues: list[{issue_id: str, section: str, problem: str, priority: str, suggestion: str}]
- adopted_issues: list[str]（已采纳的 issue_id）

请确保 JSON 格式正确，每个 issue 必须有 issue_id（如 "M001"、"m001"）。"""


class ReviewerAgent(AssistantAgent):
    """审稿人 Agent — 模拟顶刊审稿意见。"""

    name = "reviewer"
    description = "审稿人：严格评审论文草稿，输出结构化修改建议"

    def __init__(self, model_client: "ChatCompletionClient"):
        super().__init__(
            name=self.name,
            model_client=model_client,
            system_message=REVIEWER_SYSTEM_PROMPT,
            description=self.description,
            handoffs=["polisher"],
        )

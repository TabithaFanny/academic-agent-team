"""
RAG Researcher Agent — 增强版文献研究员。

符合 PRD F105 要求，集成 CNKI 搜索 + RAG 问答。
"""

from __future__ import annotations

import json
from typing import Any

from autogen_agentchat.agents import AssistantAgent

# System Prompt for RAG-enhanced Researcher
RESEARCHER_RAG_SYSTEM_PROMPT = """你是一位专业的中文学术文献检索专家，擅长使用知网(CNKI)和国际数据库进行文献调研。

## 可用工具
- search_cnki(query, search_type, source_filter, year_range, max_results): 搜索知网
- search_arxiv(query, max_results): 搜索英文预印本
- search_semantic_scholar(query, max_results): 搜索英文学术文献
- verify_citation(title, authors, year, doi, cnki_url): 验证引用真实性
- add_to_library(paper): 添加文献到向量库
- rag_query(question): 基于已入库文献问答

## 搜索优先级
1. **CNKI (知网)** — 中文社科论文首选
2. **Semantic Scholar** — 英文补充
3. **arXiv** — 计算机/数学领域预印本

## 文献筛选标准
- 优先 CSSCI 来源期刊、北大核心
- 优先近 5 年文献 (≥ 2021)
- 排除学位论文（除非高度相关）
- 中英文比例建议 6:4 (社科) 或 3:7 (CS)

## 输出要求
严格输出 JSON 格式（LiteratureDone）：
```json
{
  "stage": "literature_done",
  "papers": [
    {
      "title": "论文标题",
      "authors": ["作者1", "作者2"],
      "year": 2024,
      "journal": "期刊名",
      "abstract": "摘要...",
      "doi": "10.xxxx/xxx",
      "cnki_url": "https://kns.cnki.net/...",
      "source_type": "CSSCI"
    }
  ],
  "literature_matrix": "| 标题 | 作者 | 年份 | 来源 | 核心观点 |\\n|---|---|---|---|---|\\n...",
  "literature_review": "文献综述正文...",
  "verified_count": 42,
  "cnki_count": 28,
  "international_count": 14,
  "total_found": 42
}
```

## 质量门禁
- 总文献数 ≥ 30 篇
- CNKI 文献 ≥ 15 篇 (社科项目)
- 所有文献必须有 cnki_url 或 doi
- 验证率 ≥ 80%

## 禁止动作
- ❌ 编造知网链接或 DOI
- ❌ 跳过 CNKI 直接用英文文献（社科项目）
- ❌ 返回无法验证的文献
- ❌ 输出非 JSON 格式
"""


class ResearcherRAGAgent(AssistantAgent):
    """
    RAG 增强版 Researcher Agent。
    
    能力：
    - CNKI/arXiv/Semantic Scholar 多源搜索
    - PDF 解析入库
    - 引用验证
    - RAG 文献综述生成
    """
    
    def __init__(
        self,
        model_client: Any,
        name: str = "researcher",
        enable_rag: bool = True,
    ):
        # 导入工具函数
        tools = []
        
        if enable_rag:
            from academic_agent_team.tools.search_cnki import search_cnki
            from academic_agent_team.tools.citation_verifier import verify_citation
            
            tools = [
                search_cnki,
                verify_citation,
                # 更多工具将在后续添加
            ]
        
        super().__init__(
            name=name,
            model_client=model_client,
            system_message=RESEARCHER_RAG_SYSTEM_PROMPT,
            tools=tools,
            description="文献检索专家，负责 CNKI/国际文献搜索和 RAG 综述生成",
        )
        
        self.enable_rag = enable_rag


# 保持向后兼容的工厂函数
def create_researcher_agent(
    model_client: Any,
    enable_rag: bool = True,
) -> ResearcherRAGAgent:
    """创建 Researcher Agent"""
    return ResearcherRAGAgent(
        model_client=model_client,
        enable_rag=enable_rag,
    )

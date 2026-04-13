"""
RAG 查询逻辑 — 检索增强生成核心实现。

提供基于向量数据库的语义检索和答案生成。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from academic_agent_team.storage.vector_db import SearchResult, VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class RAGResponse(BaseModel):
    """RAG 查询响应"""
    answer: str = Field(description="生成的答案")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="引用来源")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度 (0-1)")
    
    @property
    def has_sources(self) -> bool:
        """是否有引用来源"""
        return len(self.sources) > 0


async def rag_query(
    question: str,
    collection_name: str = "papers",
    top_k: int = 5,
    min_similarity: float = 0.3,
    vector_store: VectorStore | None = None,
) -> RAGResponse:
    """
    RAG 查询 — 检索相关文档并生成答案。
    
    Args:
        question: 用户问题
        collection_name: 向量集合名称
        top_k: 检索的文档数量
        min_similarity: 最小相似度阈值
        vector_store: 可选的 VectorStore 实例，用于测试注入
        
    Returns:
        RAGResponse 包含答案、来源和置信度
    """
    if not question or not question.strip():
        return RAGResponse(
            answer="请提供有效的问题。",
            sources=[],
            confidence=0.0,
        )
    
    # 获取或创建向量存储
    store = vector_store or get_vector_store(collection_name=collection_name)
    
    try:
        # 执行语义检索
        search_results = await store.query(query=question, k=top_k)
        
        # 过滤低相似度结果
        filtered_results = [
            result for result in search_results 
            if result.similarity >= min_similarity
        ]
        
        if not filtered_results:
            return RAGResponse(
                answer="未找到与问题相关的文档。请尝试调整问题或添加更多知识库内容。",
                sources=[],
                confidence=0.0,
            )
        
        # 构建来源信息
        sources = _build_sources(filtered_results)
        
        # 计算整体置信度
        confidence = _calculate_confidence(filtered_results)
        
        # 生成答案
        answer = await _generate_answer(question, filtered_results)
        
        return RAGResponse(
            answer=answer,
            sources=sources,
            confidence=confidence,
        )
        
    except Exception as e:
        logger.error(f"RAG 查询失败: {e}")
        return RAGResponse(
            answer=f"查询过程中出现错误: {str(e)}",
            sources=[],
            confidence=0.0,
        )


def _build_sources(results: list[SearchResult]) -> list[dict[str, Any]]:
    """从搜索结果构建来源信息"""
    sources = []
    for result in results:
        source = {
            "id": result.id,
            "content": result.content[:500] if len(result.content) > 500 else result.content,
            "similarity": round(result.similarity, 4),
            "metadata": result.metadata,
        }
        # 添加常用元数据字段
        if "title" in result.metadata:
            source["title"] = result.metadata["title"]
        if "source" in result.metadata:
            source["source_file"] = result.metadata["source"]
        if "authors" in result.metadata:
            source["authors"] = result.metadata["authors"]
        sources.append(source)
    return sources


def _calculate_confidence(results: list[SearchResult]) -> float:
    """计算整体置信度（基于 top 结果的相似度）"""
    if not results:
        return 0.0
    
    # 使用加权平均，top 结果权重更高
    weights = [1.0 / (i + 1) for i in range(len(results))]
    total_weight = sum(weights)
    
    weighted_sum = sum(
        result.similarity * weight 
        for result, weight in zip(results, weights)
    )
    
    confidence = weighted_sum / total_weight if total_weight > 0 else 0.0
    return round(min(confidence, 1.0), 4)


async def _generate_answer(question: str, results: list[SearchResult]) -> str:
    """
    基于检索结果生成答案。
    
    当前实现：拼接相关文档内容作为答案。
    未来可接入 LLM 进行真正的生成式问答。
    """
    if not results:
        return "未找到相关信息。"
    
    # 构建上下文
    context_parts = []
    for i, result in enumerate(results, 1):
        title = result.metadata.get("title", f"文档 {result.id}")
        snippet = result.content[:300] if len(result.content) > 300 else result.content
        context_parts.append(f"[{i}] {title}\n{snippet}")
    
    context = "\n\n".join(context_parts)
    
    # 简单回答格式（未来可替换为 LLM 调用）
    answer = f"根据检索到的 {len(results)} 篇相关文档：\n\n{context}"
    
    # TODO: 接入 LLM 进行真正的生成式问答
    # 示例:
    # answer = await llm_generate(
    #     prompt=f"基于以下上下文回答问题:\n\n上下文:\n{context}\n\n问题: {question}",
    # )
    
    return answer

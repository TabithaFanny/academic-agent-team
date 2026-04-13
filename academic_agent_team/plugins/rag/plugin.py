"""
RAG 插件 — 注册 RAG 工具到插件系统。

符合 PRD 插件规范，提供检索增强生成能力。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from academic_agent_team.plugins.base import BasePlugin
from academic_agent_team.storage.vector_db import VectorStore

from .query import RAGResponse, rag_query

logger = logging.getLogger(__name__)


class RAGPlugin(BasePlugin):
    """
    RAG 插件 — 提供检索增强生成功能。
    
    工具列表:
    - rag_query: 基于知识库的语义检索问答
    """
    
    name: str = "rag"
    version: str = "0.1.0"
    description: str = "检索增强生成插件，支持基于向量数据库的知识问答"
    
    def __init__(
        self,
        vector_store: VectorStore | None = None,
        default_collection: str = "papers",
        default_top_k: int = 5,
    ):
        """
        初始化 RAG 插件。
        
        Args:
            vector_store: 可选的自定义 VectorStore 实例
            default_collection: 默认集合名称
            default_top_k: 默认检索数量
        """
        super().__init__()
        self._vector_store = vector_store
        self._default_collection = default_collection
        self._default_top_k = default_top_k
    
    def _register_tools(self) -> list[Callable[..., Any]]:
        """注册 RAG 工具函数"""
        return [self._create_rag_query_tool()]
    
    def _create_rag_query_tool(self) -> Callable[..., Any]:
        """创建 rag_query 工具函数（闭包绑定配置）"""
        vector_store = self._vector_store
        default_collection = self._default_collection
        default_top_k = self._default_top_k
        
        async def rag_query_tool(
            question: str,
            collection_name: str | None = None,
            top_k: int | None = None,
        ) -> dict[str, Any]:
            """
            RAG 知识库问答工具。
            
            基于向量数据库检索相关文档，返回答案和来源。
            
            Args:
                question: 用户问题
                collection_name: 向量集合名称（可选）
                top_k: 检索文档数量（可选）
                
            Returns:
                包含 answer, sources, confidence 的字典
            """
            response = await rag_query(
                question=question,
                collection_name=collection_name or default_collection,
                top_k=top_k or default_top_k,
                vector_store=vector_store,
            )
            
            return {
                "answer": response.answer,
                "sources": response.sources,
                "confidence": response.confidence,
            }
        
        # 设置函数元数据（用于 Tool Calling schema 生成）
        rag_query_tool.__name__ = "rag_query"
        rag_query_tool.__doc__ = """
RAG 知识库问答工具。

基于向量数据库检索相关文档，返回答案和来源。

Args:
    question: 用户问题
    collection_name: 向量集合名称（可选，默认 "papers"）
    top_k: 检索文档数量（可选，默认 5）

Returns:
    dict: {"answer": str, "sources": list, "confidence": float}
"""
        
        return rag_query_tool
    
    def health_check(self) -> bool:
        """检查 RAG 插件是否可用"""
        try:
            # 检查向量存储是否可用
            from academic_agent_team.storage.vector_db import get_vector_store
            store = self._vector_store or get_vector_store()
            # 简单检查：尝试获取文档数量
            _ = store.count()
            return True
        except Exception as e:
            logger.warning(f"RAG 插件健康检查失败: {e}")
            return False
    
    def cleanup(self) -> None:
        """清理 RAG 插件资源"""
        super().cleanup()
        self._vector_store = None
        logger.info("RAG 插件资源已清理")

"""
RAG 插件 — 提供检索增强生成能力。

支持基于向量数据库的知识检索和问答。
"""

from .plugin import RAGPlugin
from .query import RAGResponse, rag_query

__all__ = ["RAGPlugin", "RAGResponse", "rag_query"]

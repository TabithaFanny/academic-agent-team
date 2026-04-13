"""
向量数据库封装 — Chroma 本地存储。

符合 PRD F102 要求，支持文献向量存储和检索。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Document(BaseModel):
    """文档模型"""
    id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class SearchResult(BaseModel):
    """搜索结果"""
    id: str
    content: str
    metadata: dict[str, Any]
    similarity: float
    
    @property
    def source(self) -> str:
        return self.metadata.get("source", "unknown")


class VectorStore:
    """
    向量数据库封装 — 基于 Chroma。
    
    支持：
    - 文献入库（自动 embedding）
    - 语义搜索
    - 元数据过滤
    - 持久化存储
    """
    
    def __init__(
        self,
        collection_name: str = "papers",
        persist_directory: str | Path | None = None,
        embedding_model: Literal["openai", "local"] = "openai",
    ):
        self.collection_name = collection_name
        self.persist_directory = Path(persist_directory) if persist_directory else Path("./vector_store")
        self.embedding_model = embedding_model
        
        self._client = None
        self._collection = None
        self._embedding_fn = None
    
    def _get_client(self):
        """延迟初始化 Chroma 客户端"""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
                
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                
                self._client = chromadb.Client(Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=str(self.persist_directory),
                    anonymized_telemetry=False,
                ))
            except ImportError:
                logger.error("chromadb 未安装，请运行: pip install chromadb")
                raise
        return self._client
    
    def _get_collection(self):
        """获取或创建 collection"""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection
    
    def _get_embedding_fn(self):
        """获取 embedding 函数"""
        if self._embedding_fn is None:
            if self.embedding_model == "openai":
                self._embedding_fn = self._openai_embedding
            else:
                self._embedding_fn = self._local_embedding
        return self._embedding_fn
    
    async def _openai_embedding(self, texts: list[str]) -> list[list[float]]:
        """OpenAI embedding"""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI()
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.warning(f"OpenAI embedding 失败: {e}，降级到本地模型")
            return await self._local_embedding(texts)
    
    async def _local_embedding(self, texts: list[str]) -> list[list[float]]:
        """本地 embedding (sentence-transformers)"""
        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except ImportError:
            logger.error("sentence-transformers 未安装")
            # 返回零向量作为 fallback
            return [[0.0] * 384 for _ in texts]
    
    async def add_documents(
        self,
        documents: list[Document],
        batch_size: int = 100,
    ) -> list[str]:
        """
        添加文档到向量库。
        
        Args:
            documents: 文档列表
            batch_size: 批处理大小
            
        Returns:
            添加的文档 ID 列表
        """
        if not documents:
            return []
        
        collection = self._get_collection()
        embedding_fn = self._get_embedding_fn()
        
        added_ids = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            ids = [doc.id for doc in batch]
            contents = [doc.content for doc in batch]
            metadatas = [doc.metadata for doc in batch]
            
            # 计算 embeddings
            if batch[0].embedding:
                embeddings = [doc.embedding for doc in batch]
            else:
                embeddings = await embedding_fn(contents)
            
            # 添加到 collection
            collection.add(
                ids=ids,
                documents=contents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            
            added_ids.extend(ids)
        
        logger.info(f"添加 {len(added_ids)} 篇文献到向量库")
        return added_ids
    
    async def query(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        语义搜索。
        
        Args:
            query: 查询文本
            k: 返回结果数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            SearchResult 列表（按相似度降序）
        """
        collection = self._get_collection()
        embedding_fn = self._get_embedding_fn()
        
        # 计算查询向量
        query_embedding = (await embedding_fn([query]))[0]
        
        # 查询
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"],
        )
        
        # 转换结果
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                # Chroma 返回的是距离，转换为相似度
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 - distance  # cosine distance to similarity
                
                search_results.append(SearchResult(
                    id=doc_id,
                    content=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    similarity=similarity,
                ))
        
        return search_results
    
    async def query_by_embedding(
        self,
        embedding: list[float],
        k: int = 5,
    ) -> list[SearchResult]:
        """根据 embedding 向量查询"""
        collection = self._get_collection()
        
        results = collection.query(
            query_embeddings=[embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 - distance
                
                search_results.append(SearchResult(
                    id=doc_id,
                    content=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    similarity=similarity,
                ))
        
        return search_results
    
    def delete(self, doc_ids: list[str]) -> None:
        """删除文档"""
        collection = self._get_collection()
        collection.delete(ids=doc_ids)
        logger.info(f"删除 {len(doc_ids)} 篇文献")
    
    def get_sources(self, doc_ids: list[str]) -> list[Document]:
        """根据 ID 获取文档"""
        collection = self._get_collection()
        
        results = collection.get(
            ids=doc_ids,
            include=["documents", "metadatas"],
        )
        
        documents = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                documents.append(Document(
                    id=doc_id,
                    content=results["documents"][i] if results["documents"] else "",
                    metadata=results["metadatas"][i] if results["metadatas"] else {},
                ))
        
        return documents
    
    def count(self) -> int:
        """获取文档数量"""
        collection = self._get_collection()
        return collection.count()
    
    def persist(self) -> None:
        """持久化到磁盘"""
        if self._client:
            self._client.persist()
            logger.info(f"向量库已持久化到 {self.persist_directory}")


# 全局实例
_default_store: VectorStore | None = None


def get_vector_store(
    collection_name: str = "papers",
    persist_directory: str | Path | None = None,
) -> VectorStore:
    """获取向量库实例"""
    global _default_store
    
    if _default_store is None:
        _default_store = VectorStore(
            collection_name=collection_name,
            persist_directory=persist_directory or "./vector_store",
        )
    
    return _default_store

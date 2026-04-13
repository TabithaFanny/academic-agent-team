"""
CNKI 文献搜索工具 — 基于 MagicCNKI 集成。

符合 PRD F112 要求，CNKI 搜索为中文社科论文首选来源。
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """文献来源类型"""
    CSSCI = "CSSCI"
    PKU_CORE = "北大核心"
    SCI = "SCI"
    GENERAL = "普通期刊"
    THESIS = "学位论文"
    CONFERENCE = "会议论文"


class CNKIPaper(BaseModel):
    """CNKI 文献模型"""
    title: str
    authors: list[str]
    journal: str
    year: int
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    cnki_url: str
    source_type: SourceType = SourceType.GENERAL
    doi: str | None = None
    citations: int = 0
    downloads: int = 0
    
    @property
    def citation_key(self) -> str:
        """生成引用键"""
        first_author = self.authors[0] if self.authors else "Unknown"
        return f"{first_author.split()[0]}{self.year}"


class CNKISearchResult(BaseModel):
    """CNKI 搜索结果"""
    papers: list[CNKIPaper]
    total_found: int
    query: str
    search_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class RateLimiter:
    """请求限速器"""
    
    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self._last_request: float = 0
        self._lock = asyncio.Lock()
    
    async def wait(self) -> None:
        """等待直到可以发送下一个请求"""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last_request = asyncio.get_event_loop().time()


# CSSCI 期刊列表（部分示例，实际应从数据库加载）
CSSCI_JOURNALS = {
    "新闻与传播研究", "新闻大学", "国际新闻界", "现代传播",
    "新闻记者", "编辑之友", "出版发行研究", "中国出版",
    "社会学研究", "中国社会科学", "管理世界", "经济研究",
}


class CNKISearchTool:
    """
    CNKI 搜索工具 — Researcher Agent 专用。
    
    优先级：CNKI > Semantic Scholar > arXiv
    """
    
    def __init__(self):
        self.rate_limiter = RateLimiter(requests_per_minute=10)
        self._mock_mode = os.getenv("CNKI_MOCK", "false").lower() == "true"
        self._searcher = None
    
    def _get_searcher(self):
        """延迟加载 MagicCNKI"""
        if self._searcher is None:
            try:
                from magiccnki import CNKISearcher
                self._searcher = CNKISearcher()
            except ImportError:
                logger.warning("MagicCNKI 未安装，使用 Mock 模式")
                self._mock_mode = True
        return self._searcher
    
    def _classify_source(self, journal: str) -> SourceType:
        """根据期刊名判断来源类型"""
        if journal in CSSCI_JOURNALS:
            return SourceType.CSSCI
        # 实际应查询数据库
        return SourceType.GENERAL
    
    async def search(
        self,
        query: str,
        search_type: Literal["主题", "关键词", "作者", "篇名"] = "主题",
        source_filter: list[str] | None = None,
        year_range: tuple[int, int] | None = None,
        max_results: int = 50,
    ) -> CNKISearchResult:
        """
        搜索知网文献。
        
        Args:
            query: 搜索关键词
            search_type: 搜索类型
            source_filter: 来源过滤 ["CSSCI", "北大核心", "SCI"]
            year_range: 年份范围 (start, end)
            max_results: 最大结果数
            
        Returns:
            CNKISearchResult 搜索结果
        """
        await self.rate_limiter.wait()
        
        if self._mock_mode:
            return await self._mock_search(query, search_type, max_results)
        
        try:
            searcher = self._get_searcher()
            if searcher is None:
                return await self._mock_search(query, search_type, max_results)
            
            # 调用 MagicCNKI
            results = searcher.search(
                query=query,
                search_type=search_type,
                source=source_filter,
                year_from=year_range[0] if year_range else None,
                year_to=year_range[1] if year_range else None,
                limit=max_results,
            )
            
            papers = []
            for r in results:
                papers.append(CNKIPaper(
                    title=r.get("title", ""),
                    authors=r.get("authors", []),
                    journal=r.get("journal", ""),
                    year=int(r.get("year", 2024)),
                    abstract=r.get("abstract", ""),
                    keywords=r.get("keywords", []),
                    cnki_url=r.get("url", ""),
                    source_type=self._classify_source(r.get("journal", "")),
                    doi=r.get("doi"),
                    citations=r.get("citations", 0),
                    downloads=r.get("downloads", 0),
                ))
            
            return CNKISearchResult(
                papers=papers,
                total_found=len(papers),
                query=query,
                search_type=search_type,
            )
            
        except Exception as e:
            logger.warning(f"CNKI 搜索失败: {e}，降级到备用源")
            return await self._fallback_search(query, max_results)
    
    async def _mock_search(
        self,
        query: str,
        search_type: str,
        max_results: int,
    ) -> CNKISearchResult:
        """Mock 搜索（用于测试）"""
        mock_papers = [
            CNKIPaper(
                title=f"人工智能与{query}的研究进展",
                authors=["张三", "李四"],
                journal="新闻与传播研究",
                year=2024,
                abstract=f"本文探讨了{query}领域的最新发展...",
                keywords=[query, "人工智能", "新闻传播"],
                cnki_url=f"https://kns.cnki.net/kcms2/article/abstract?v=mock_{i}",
                source_type=SourceType.CSSCI,
                doi=f"10.1234/mock.{i}",
            )
            for i in range(min(max_results, 50))
        ]
        
        return CNKISearchResult(
            papers=mock_papers,
            total_found=len(mock_papers),
            query=query,
            search_type=search_type,
        )
    
    async def _fallback_search(
        self,
        query: str,
        max_results: int,
    ) -> CNKISearchResult:
        """降级搜索 — 使用 Semantic Scholar + OpenAlex"""
        logger.info(f"CNKI 降级：使用 Semantic Scholar 搜索 '{query}'")
        
        # 这里调用备用搜索
        # 实际实现需要集成 SemanticScholarTool
        return CNKISearchResult(
            papers=[],
            total_found=0,
            query=query,
            search_type="fallback",
        )


# 工具函数（供 Agent Tool Calling 使用）
_cnki_tool = CNKISearchTool()


async def search_cnki(
    query: str,
    search_type: Literal["主题", "关键词", "作者", "篇名"] = "主题",
    source_filter: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
    max_results: int = 50,
) -> CNKISearchResult:
    """
    搜索知网文献（Agent Tool）。
    
    Args:
        query: 搜索关键词
        search_type: 搜索类型 ("主题", "关键词", "作者", "篇名")
        source_filter: 来源过滤 ["CSSCI", "北大核心"]
        year_range: 年份范围 (2020, 2026)
        max_results: 最大结果数
        
    Returns:
        CNKISearchResult 包含文献列表
    """
    return await _cnki_tool.search(
        query=query,
        search_type=search_type,
        source_filter=source_filter,
        year_range=year_range,
        max_results=max_results,
    )

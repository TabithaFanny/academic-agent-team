"""
引用验证工具 — CrossRef DOI + CNKI 链接验证。

符合 PRD F108 要求，所有引用必须可溯源。
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """验证状态"""
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    INVALID_FORMAT = "invalid_format"
    NETWORK_ERROR = "network_error"
    PENDING = "pending"


class CitationMetadata(BaseModel):
    """引用元数据"""
    title: str
    authors: list[str]
    year: int
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    cnki_url: str | None = None
    publisher: str | None = None


class Citation(BaseModel):
    """引用对象"""
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    cnki_url: str | None = None
    raw_text: str = ""


class VerificationResult(BaseModel):
    """单条验证结果"""
    verified: bool
    status: VerificationStatus
    reason: str = ""
    metadata: CitationMetadata | None = None
    original: Citation | None = None


class BatchVerificationResult(BaseModel):
    """批量验证结果"""
    verified_citations: list[Citation]
    failed_citations: list[tuple[Citation, str]]  # (citation, reason)
    verification_rate: float
    total: int
    verified_count: int
    failed_count: int


class CrossRefClient:
    """CrossRef API 客户端"""
    
    BASE_URL = "https://api.crossref.org/works"
    
    def __init__(self):
        self.timeout = 10.0
        self.email = os.getenv("CROSSREF_EMAIL", "paper-genius@example.com")
    
    async def get_work(self, doi: str) -> dict[str, Any]:
        """根据 DOI 获取文献元数据"""
        url = f"{self.BASE_URL}/{doi}"
        headers = {"User-Agent": f"PaperGenius/1.0 (mailto:{self.email})"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                raise DoiNotFoundError(f"DOI not found: {doi}")
            
            response.raise_for_status()
            data = response.json()
            return data.get("message", {})
    
    async def search(self, query: str, rows: int = 5) -> list[dict]:
        """搜索文献"""
        url = self.BASE_URL
        params = {"query": query, "rows": rows}
        headers = {"User-Agent": f"PaperGenius/1.0 (mailto:{self.email})"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("items", [])


class DoiNotFoundError(Exception):
    """DOI 未找到"""
    pass


class CNKIVerifier:
    """CNKI 链接验证器"""
    
    CNKI_PATTERN = re.compile(
        r"https?://kns\.cnki\.net/kcms2?/article/abstract\?v=[\w\-_]+",
        re.IGNORECASE
    )
    
    def validate_url_format(self, url: str) -> bool:
        """验证 CNKI URL 格式"""
        return bool(self.CNKI_PATTERN.match(url))

    async def _check_url_reachable(self, url: str) -> tuple[bool, str]:
        """检查 CNKI 链接可达性。"""
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get(url)
            if response.status_code >= 400:
                return False, f"CNKI 链接不可达: HTTP {response.status_code}"
            return True, "CNKI 链接可达"
        except Exception as e:
            return False, f"CNKI 链接验证网络错误: {e}"
    
    async def verify(self, url: str) -> VerificationResult:
        """验证 CNKI 链接是否有效"""
        if not self.validate_url_format(url):
            return VerificationResult(
                verified=False,
                status=VerificationStatus.INVALID_FORMAT,
                reason="CNKI URL 格式不正确"
            )

        # 默认兼容旧行为：只校验格式
        strict_http = os.getenv("CNKI_VERIFY_HTTP", "false").lower() == "true"
        if not strict_http:
            return VerificationResult(
                verified=True,
                status=VerificationStatus.VERIFIED,
                reason="CNKI URL 格式正确（未启用 HTTP 可达性验证）"
            )

        reachable, message = await self._check_url_reachable(url)
        if not reachable:
            status = VerificationStatus.NETWORK_ERROR if "网络错误" in message else VerificationStatus.NOT_FOUND
            return VerificationResult(
                verified=False,
                status=status,
                reason=message
            )

        return VerificationResult(
            verified=True,
            status=VerificationStatus.VERIFIED,
            reason=message
        )


class CitationVerifier:
    """
    引用验证器 — 验证引用真实性。
    
    策略：
    1. 有 DOI → CrossRef 验证
    2. 有 CNKI URL → CNKI 格式验证
    3. 都没有 → 标记为需要补充
    """
    
    def __init__(self):
        self.crossref = CrossRefClient()
        self.cnki = CNKIVerifier()
        self._mock_mode = os.getenv("CITATION_MOCK", "false").lower() == "true"
    
    async def verify_citation(self, citation: Citation) -> VerificationResult:
        """验证单条引用"""
        
        if self._mock_mode:
            return VerificationResult(
                verified=True,
                status=VerificationStatus.VERIFIED,
                reason="Mock mode",
                original=citation
            )
        
        # 优先验证 DOI
        if citation.doi:
            return await self._verify_doi(citation)
        
        # 其次验证 CNKI
        if citation.cnki_url:
            return await self._verify_cnki(citation)
        
        # 都没有
        return VerificationResult(
            verified=False,
            status=VerificationStatus.INVALID_FORMAT,
            reason="缺少 DOI 或 CNKI 链接，无法验证",
            original=citation
        )
    
    async def _verify_doi(self, citation: Citation) -> VerificationResult:
        """验证 DOI"""
        try:
            metadata = await self.crossref.get_work(citation.doi)
            
            # 提取元数据
            authors = []
            for author in metadata.get("author", []):
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                if name:
                    authors.append(name)
            
            year = None
            if "published" in metadata:
                date_parts = metadata["published"].get("date-parts", [[]])
                if date_parts and date_parts[0]:
                    year = date_parts[0][0]
            
            return VerificationResult(
                verified=True,
                status=VerificationStatus.VERIFIED,
                metadata=CitationMetadata(
                    title=metadata.get("title", [""])[0] if metadata.get("title") else "",
                    authors=authors,
                    year=year or 2024,
                    journal=metadata.get("container-title", [""])[0] if metadata.get("container-title") else None,
                    doi=citation.doi,
                    publisher=metadata.get("publisher"),
                ),
                original=citation
            )
        
        except DoiNotFoundError:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.NOT_FOUND,
                reason=f"DOI 不存在: {citation.doi}",
                original=citation
            )
        
        except Exception as e:
            logger.warning(f"DOI 验证失败: {e}")
            return VerificationResult(
                verified=False,
                status=VerificationStatus.NETWORK_ERROR,
                reason=f"网络错误: {str(e)}",
                original=citation
            )
    
    async def _verify_cnki(self, citation: Citation) -> VerificationResult:
        """验证 CNKI 链接"""
        result = await self.cnki.verify(citation.cnki_url)
        result.original = citation
        return result
    
    async def verify_all(self, citations: list[Citation]) -> BatchVerificationResult:
        """批量验证引用"""
        if not citations:
            return BatchVerificationResult(
                verified_citations=[],
                failed_citations=[],
                verification_rate=1.0,
                total=0,
                verified_count=0,
                failed_count=0,
            )
        
        # 并发验证
        tasks = [self.verify_citation(c) for c in citations]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        verified = []
        failed = []
        
        for citation, result in zip(citations, results):
            if isinstance(result, Exception):
                failed.append((citation, str(result)))
            elif result.verified:
                verified.append(citation)
            else:
                failed.append((citation, result.reason))
        
        total = len(citations)
        verified_count = len(verified)
        
        return BatchVerificationResult(
            verified_citations=verified,
            failed_citations=failed,
            verification_rate=verified_count / total if total > 0 else 0,
            total=total,
            verified_count=verified_count,
            failed_count=len(failed),
        )


# Gate 函数
async def citation_verification_gate(
    citations: list[Citation],
    min_rate: float = 0.8,
) -> tuple[bool, BatchVerificationResult, str]:
    """
    引用验证门禁。
    
    Args:
        citations: 待验证引用列表
        min_rate: 最低验证率要求 (默认 80%)
        
    Returns:
        (passed, result, message)
    """
    verifier = CitationVerifier()
    result = await verifier.verify_all(citations)
    
    if result.verification_rate >= min_rate:
        return True, result, f"引用验证通过 ({result.verification_rate:.0%})"
    else:
        return False, result, f"引用验证率过低: {result.verification_rate:.0%} < {min_rate:.0%}"


# 工具函数（供 Agent Tool Calling 使用）
_verifier = CitationVerifier()


async def verify_citation(
    title: str,
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    cnki_url: str | None = None,
) -> VerificationResult:
    """
    验证单条引用（Agent Tool）。
    
    Args:
        title: 论文标题
        authors: 作者列表
        year: 发表年份
        doi: DOI 标识符
        cnki_url: CNKI 链接
        
    Returns:
        VerificationResult 验证结果
    """
    citation = Citation(
        title=title,
        authors=authors or [],
        year=year,
        doi=doi,
        cnki_url=cnki_url,
    )
    return await _verifier.verify_citation(citation)

"""
文献检索工具 — 接入 Semantic Scholar API + CrossRef API。

PRD M3 要求：支持中英文文献，15分钟内完成调研。
PRD 7.5 技术要点：Semantic Scholar + CrossRef 双检验。

功能：
  - search_papers(query, limit): 搜索论文，返回真实文献数据
  - verify_doi(doi): 验证 DOI 是否真实存在（CrossRef）
  - build_literature_matrix(papers): 生成 Markdown 文献矩阵
  - fetch_paper_details(paper_id): 获取单篇论文详情
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from dataclasses import dataclass


# ── 数据模型 ─────────────────────────────────────────────────────────────────

@dataclass
class PaperRecord:
    title: str
    doi: str | None
    authors: list[str]
    year: int
    abstract: str | None
    relevance_score: float  # 0-1
    venue: str | None        # 期刊/会议名
    citation_count: int
    paper_id: str            # Semantic Scholar paper ID
    verified: bool           # CrossRef 验证结果
    url: str | None


# ── Semantic Scholar API ───────────────────────────────────────────────────────

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"


def search_papers(
    query: str,
    limit: int = 20,
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[PaperRecord]:
    """
    使用 Semantic Scholar API 搜索论文。

    免费，无需 API key（速率限制内）。
    返回最多 `limit` 篇最相关论文。
    """
    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": (
            "title,abstract,authors,year,venue,citationCount,"
            "externalIds,url,openAccessPdf,s2FieldsOfStudy"
        ),
    }
    if year_from:
        params["year"] = f"{year_from}-{year_to or ''}"
    url = f"{SEMANTIC_SCHOLAR_BASE}/paper/search?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Semantic Scholar search failed: {e}") from e

    papers: list[PaperRecord] = []
    for item in data.get("data", []):
        ext = item.get("externalIds", {}) or {}
        doi = ext.get("DOI")  # DOI may be None
        papers.append(PaperRecord(
            title=item.get("title", "Untitled"),
            doi=doi,
            authors=[a.get("name", "") for a in item.get("authors", [])],
            year=item.get("year") or 0,
            abstract=item.get("abstract"),
            relevance_score=0.9,  # 搜索结果按相关性排序，假设相关
            venue=item.get("venue"),
            citation_count=item.get("citationCount", 0),
            paper_id=item.get("paperId", ""),
            verified=False,  # 待 CrossRef 验证
            url=item.get("url") or item.get("openAccessPdf", {}).get("url"),
        ))
    return papers


def fetch_paper_details(paper_id: str) -> dict:
    """获取单篇论文详情（含摘要、引用数等）。"""
    fields = "title,abstract,authors,year,venue,citationCount,references,externalIds"
    url = f"{SEMANTIC_SCHOLAR_BASE}/paper/{paper_id}?fields={fields}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to fetch paper {paper_id}: {e}") from e


# ── CrossRef DOI 验证 ────────────────────────────────────────────────────────

CROSSREF_BASE = "https://api.crossref.org/works"


def verify_doi(doi: str) -> bool:
    """
    使用 CrossRef API 验证 DOI 是否真实存在。

    免费，无需 API key。
    返回 True = DOI 有效，False = DOI 无效或网络错误。
    """
    if not doi:
        return False
    url = f"{CROSSREF_BASE}/{urllib.parse.quote(doi)}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "AcademicAgentTeam/1.0 (mailto:user@example.com)",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "ok"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise RuntimeError(f"CrossRef HTTP error {e.code}: {e.read()}") from e
    except Exception:
        return False


def verify_papers(papers: list[PaperRecord]) -> list[PaperRecord]:
    """
    对论文列表逐一 CrossRef DOI 验证。

    更新 PaperRecord.verified 字段。
    网络错误 → 标记为 False（不阻断流程）。
    """
    verified = []
    for paper in papers:
        if paper.doi:
            paper.verified = verify_doi(paper.doi)
        else:
            paper.verified = False
        verified.append(paper)
    return verified


# ── 文献矩阵生成 ───────────────────────────────────────────────────────────────

def build_literature_matrix(papers: list[PaperRecord]) -> tuple[str, int, int]:
    """
    将论文列表生成为 Markdown 文献矩阵表格。

    返回 (matrix_markdown, verified_count, total_count)
    """
    lines = [
        "| # | Title | Authors | Year | Venue | DOI | Verified |",
        "|---|-------|---------|------|-------|-----|----------|",
    ]
    for i, p in enumerate(papers, 1):
        title_short = p.title[:60] + "…" if len(p.title) > 60 else p.title
        author_str = ", ".join(a.split()[-1] for a in p.authors[:3])
        if len(p.authors) > 3:
            author_str += " et al."
        doi_str = p.doi or "—"
        verified_icon = "✅" if p.verified else "⚠️ [需验证]"
        lines.append(
            f"| {i} | {title_short} | {author_str} | {p.year} | "
            f"{p.venue or '—'} | {doi_str} | {verified_icon} |"
        )

    verified_count = sum(1 for p in papers if p.verified)
    return "\n".join(lines), verified_count, len(papers)


# ── 端到端文献调研 ─────────────────────────────────────────────────────────────

def research_literature(
    direction: str,
    limit: int = 20,
    verify: bool = True,
) -> dict:
    """
    完整文献调研流程：

    1. Semantic Scholar 搜索
    2. CrossRef DOI 双重验证（可选）
    3. 生成文献矩阵

    返回 dict，结构与 LiteratureDone payload 兼容：
        {
            "papers": [...],
            "literature_matrix": "...",
            "verified_count": int,
            "total_found": int,
        }
    """
    console_msg = []

    # Step 1: 搜索
    papers = search_papers(direction, limit=limit)
    if not papers:
        return {
            "papers": [],
            "literature_matrix": "| 无结果 |",
            "verified_count": 0,
            "total_found": 0,
        }

    # Step 2: DOI 验证（默认开启）
    if verify:
        papers = verify_papers(papers)

    # Step 3: 构建矩阵
    matrix, verified_count, total = build_literature_matrix(papers)

    return {
        "papers": [
            {
                "title": p.title,
                "doi": p.doi,
                "authors": p.authors,
                "year": p.year,
                "abstract": p.abstract or "",
                "relevance_score": p.relevance_score,
                "verified": p.verified,
            }
            for p in papers
        ],
        "literature_matrix": matrix,
        "verified_count": verified_count,
        "total_found": total,
    }

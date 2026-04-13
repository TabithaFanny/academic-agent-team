"""
Tools 模块初始化。
"""

from academic_agent_team.tools.search_cnki import (
    CNKIPaper,
    CNKISearchResult,
    CNKISearchTool,
    SourceType,
    search_cnki,
)
from academic_agent_team.tools.citation_verifier import (
    Citation,
    CitationMetadata,
    CitationVerifier,
    VerificationResult,
    VerificationStatus,
    citation_verification_gate,
    verify_citation,
)
from academic_agent_team.tools.plagiarism_checker import (
    PlagiarismChecker,
    ReductionSuggestion,
    SimilarityLevel,
    SimilarityResult,
    SimilarPair,
    check_plagiarism,
    format_plagiarism_report,
)

__all__ = [
    # CNKI 搜索
    "CNKIPaper",
    "CNKISearchResult",
    "CNKISearchTool",
    "SourceType",
    "search_cnki",
    # 引用验证
    "Citation",
    "CitationMetadata",
    "CitationVerifier",
    "VerificationResult",
    "VerificationStatus",
    "citation_verification_gate",
    "verify_citation",
    # 查重检测
    "PlagiarismChecker",
    "ReductionSuggestion",
    "SimilarityLevel",
    "SimilarityResult",
    "SimilarPair",
    "check_plagiarism",
    "format_plagiarism_report",
]

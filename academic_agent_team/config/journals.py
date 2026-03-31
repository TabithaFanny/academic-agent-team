"""
期刊配置（Journals）— PRD 8 / 9.1 规格。

定义各目标期刊的格式规范，字数限制，引用格式等。
"""

from __future__ import annotations


# ── 期刊标准配置 ─────────────────────────────────────────────────────────────

JOURNAL_STANDARDS: dict[str, dict] = {
    "中文核心": {
        "citation": "GB/T 7714-2015",
        "word_limit": "8000-15000",
        "ai_detection_max_pct": 20,
        "template": "chinese_journal.cls",
        "required_sections": [
            "abstract", "introduction", "literature_review",
            "methodology", "results", "discussion", "conclusion",
        ],
        "notes": "中文核心期刊，含北大核心、南大核心（CSSCI）等",
    },

    "CSSCI": {
        "citation": "GB/T 7714-2015",
        "word_limit": "10000-20000",
        "ai_detection_max_pct": 15,
        "template": "cssci.cls",
        "required_sections": [
            "abstract", "introduction", "literature_review",
            "methodology", "results", "discussion", "conclusion",
        ],
        "notes": "中文社会科学引文索引，社科类最高级别",
    },

    "IEEE Trans": {
        "citation": "IEEE",
        "word_limit": "8000-10000",
        "format": "double-column",
        "template": "IEEEtran.cls",
        "required_sections": [
            "abstract", "introduction", "related_work",
            "methodology", "experiments", "conclusion", "references",
        ],
        "notes": "IEEE  Transactions，含 CCF-A 类",
    },

    "CCF-A": {
        "citation": "IEEE/ACM",
        "page_limit": "10-12",
        "word_limit": "8000-12000",
        "novelty_min_pct": 30,
        "template": "acmart.cls",
        "required_sections": [
            "abstract", "introduction", "related_work",
            "methodology", "experiments", "conclusion", "references",
        ],
        "notes": "CCF 推荐 A 类会议/期刊",
    },
}


# ── 预定义 prompt 模板映射 ──────────────────────────────────────────────────

# 各 Agent 各阶段的 prompt template key 映射
JOURNAL_PROMPT_PREFERENCES: dict[str, dict[str, str]] = {
    "中文核心": {
        "outline": "prompt_33_cn_outline_v1.0",
        "reviewer": "prompt_32_cn_reviewer_v1.0",
    },
    "CSSCI": {
        "outline": "prompt_33_cn_outline_v1.0",
        "reviewer": "prompt_32_cn_reviewer_v1.0",
    },
    "IEEE Trans": {
        "outline": "prompt_33_en_outline_v1.0",
        "reviewer": "prompt_32_en_reviewer_v1.0",
    },
    "CCF-A": {
        "outline": "prompt_33_en_outline_v1.0",
        "reviewer": "prompt_32_ccf_reviewer_v1.0",
    },
}


def get_journal_standard(journal: str) -> dict:
    """获取期刊标准配置，找不到则返回中文核心默认值。"""
    return JOURNAL_STANDARDS.get(journal, JOURNAL_STANDARDS["中文核心"])


def validate_journal(journal: str) -> bool:
    """检查期刊是否在支持列表中。"""
    return journal in JOURNAL_STANDARDS

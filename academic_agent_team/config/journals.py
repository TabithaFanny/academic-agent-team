"""
config/journals.py

对齐 PRD Section 8 期刊标准配置。
内置 4 种期刊模板：中文核心 / CSSCI / IEEE Trans / CCF-A。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ─── 期刊常量 ─────────────────────────────────────────────────────────────────

JOURNAL_TYPES = (
    "中文核心",
    "CSSCI",
    "IEEE Trans",
    "CCF-A",
)

JOURNAL_LANGUAGES = ("zh", "en")


# ─── 期刊标准 ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class JournalStandard:
    """单个期刊的格式标准。对齐 PRD Section 8 JOURNAL_STANDARDS。"""
    name: str
    citation_format: str                          # 引用格式
    word_limit: str                               # 字数限制描述
    ai_detection_threshold_pct: float | None    # AI 味检测阈值，None 表示不限
    plagiarism_threshold_pct: float | None       # 查重阈值，None 表示不限
    novelty_requirement: str | None             # 创新性要求，无则 None
    template_file: str | None                    # LaTeX/Word 模板文件名
    template_vars: dict = field(default_factory=dict)  # 模板变量

    # 额外属性
    page_limit: str | None = None                # 页数限制
    format_notes: tuple[str, ...] = field(default_factory=())  # 其他格式说明


JOURNAL_STANDARDS: dict[str, JournalStandard] = {
    "中文核心": JournalStandard(
        name="中文核心期刊",
        citation_format="GB/T 7714-2015",
        word_limit="8000-15000",
        ai_detection_threshold_pct=20.0,
        plagiarism_threshold_pct=20.0,
        novelty_requirement=None,
        template_file="chinese_journal.tex",
        page_limit=None,
        format_notes=(
            "摘要200-300字，含3-5个关键词",
            "中图分类号和文献标志码",
            "作者单位脚注",
        ),
        template_vars={
            "cls": "cctart",
            "fonts": "songti,heiti",
            "cite_style": "GB/T 7714-2015",
        },
    ),

    "CSSCI": JournalStandard(
        name="中文社会科学引文索引",
        citation_format="GB/T 7714-2015",
        word_limit="10000-20000",
        ai_detection_threshold_pct=15.0,
        plagiarism_threshold_pct=10.0,
        novelty_requirement=None,
        template_file="cssci_journal.tex",
        page_limit=None,
        format_notes=(
            "政治立场审查",
            "摘要含研究目的一句话",
            "国家社科基金标注",
        ),
        template_vars={
            "cls": "cctart",
            "cite_style": "GB/T 7714-2015",
            "fund_field": True,
        },
    ),

    "IEEE Trans": JournalStandard(
        name="IEEE Transactions",
        citation_format="IEEE",
        word_limit="8000-10000",
        ai_detection_threshold_pct=20.0,
        plagiarism_threshold_pct=15.0,
        novelty_requirement="30%+ novel contribution",
        template_file="IEEEtran.cls",
        page_limit="10-12 pages (double column)",
        format_notes=(
            "双栏格式",
            "Abstract 150-200 words",
            "Index Terms (IEEE keywords)",
            "Nomenclature (术语表)",
        ),
        template_vars={
            "cls": "IEEEtran",
            "layout": "twocolumn",
            "cite_style": "IEEE",
        },
    ),

    "CCF-A": JournalStandard(
        name="CCF-A 类会议/期刊",
        citation_format="IEEE/ACM",
        word_limit="10-12 pages",
        ai_detection_threshold_pct=20.0,
        plagiarism_threshold_pct=10.0,
        novelty_requirement="30%+",
        template_file="acmart.cls",
        page_limit="10-12",
        format_notes=(
            "Abstract 150-200 words",
            "Introduction 1-2 pages",
            "Related Work",
            "Experiments（含 ablation study）",
            "Appendix 可选",
        ),
        template_vars={
            "cls": "acmart",
            "cite_style": "ACM",
            "anonymous": True,  # 盲审模式
        },
    ),
}


# ─── 辅助函数 ─────────────────────────────────────────────────────────────────

def get_journal_standard(journal_type: str) -> JournalStandard:
    """获取期刊标准，不存在则抛出 ValueError。"""
    if journal_type not in JOURNAL_STANDARDS:
        available = ", ".join(JOURNAL_STANDARDS.keys())
        raise ValueError(
            f"Unknown journal type: {journal_type!r}. "
            f"Available: {available}"
        )
    return JOURNAL_STANDARDS[journal_type]


def validate_journal_type(journal_type: str) -> bool:
    """检查期刊类型是否已知。"""
    return journal_type in JOURNAL_STANDARDS


def get_all_journal_types() -> tuple[str, ...]:
    """返回所有支持的期刊类型。"""
    return JOURNAL_TYPES

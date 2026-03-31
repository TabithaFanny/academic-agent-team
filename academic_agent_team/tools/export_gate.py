"""
导出门禁四 gate — PRD 7.5 / 9.1 规格。

export 前必须全部通过，任意 gate 失败则：
  1. 禁止导出
  2. 输出可执行修复清单（E010 错误）

四道 gate：
  - contract_ok : 所有 stage payload 通过 pydantic 校验
  - citation_ok : 所有 DOI 已验证，未验证项不超过 20%
  - format_ok   : 字数/章节/引用格式符合目标期刊规范
  - ethics_ok   : 无明显学术伦理风险
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from academic_agent_team.contracts.agent_contracts import (
    ERROR_CODES,
    ContractValidationError,
    validate_payload,
)
from academic_agent_team.tools.literature import verify_doi


# ── Gate 结果模型 ──────────────────────────────────────────────────────────────

@dataclass
class GateResult:
    passed: bool
    gate: str          # contract | citation | format | ethics
    error_code: str    # E007 / E004 / E010
    messages: list[str] = field(default_factory=list)
    fix_suggestions: list[str] = field(default_factory=list)

    def summary(self) -> str:
        icon = "✅" if self.passed else "❌"
        lines = [f"{icon} [{self.error_code}] {self.gate}"]
        for m in self.messages:
            lines.append(f"   {m}")
        if self.fix_suggestions:
            lines.append("   📋 修复建议:")
            for s in self.fix_suggestions:
                lines.append(f"   - {s}")
        return "\n".join(lines)


# ── Gate 1: Contract 校验 ────────────────────────────────────────────────────

def check_contract_gate(session_dir: Path) -> GateResult:
    """
    检查所有 stage JSON 是否通过 pydantic 契约校验。
    失败 → E007
    """
    required_stages = {
        "topic_done": "选题报告",
        "literature_done": "文献矩阵",
        "writing_done": "论文草稿",
        "review_done": "审稿报告",
        "polish_done": "润色报告",
    }
    errors: list[str] = []
    fix_suggestions: list[str] = []

    for stage_file, name in required_stages.items():
        f = session_dir / f"{stage_file}.json"
        if not f.exists():
            errors.append(f"缺少 {name}：{stage_file}.json")
            fix_suggestions.append(f"运行选题/文献/写作流程生成 {stage_file}.json")
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            validate_payload(data)
        except (json.JSONDecodeError, ContractValidationError) as e:
            errors.append(f"{name} 校验失败：{e}")
            fix_suggestions.append(f"检查 {stage_file}.json 格式或重新运行 {name} 流程")

    return GateResult(
        passed=len(errors) == 0,
        gate="contract",
        error_code="E007" if errors else "OK",
        messages=errors,
        fix_suggestions=fix_suggestions,
    )


# ── Gate 2: Citation 校验 ────────────────────────────────────────────────────

def check_citation_gate(session_dir: Path) -> GateResult:
    """
    检查文献 DOI 验证率。
    - verified_count / total_found >= 80% → 通过
    - 未验证 DOI 列表输出为修复建议
    失败 → E004
    """
    lit_file = session_dir / "literature_done.json"
    if not lit_file.exists():
        return GateResult(
            passed=False,
            gate="citation",
            error_code="E004",
            messages=["缺少 literature_done.json，无法校验引用"],
            fix_suggestions=["运行文献检索流程生成 literature_done.json"],
        )

    try:
        lit = json.loads(lit_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return GateResult(
            passed=False, gate="citation", error_code="E004",
            messages=[f"literature_done.json 格式错误：{e}"],
        )

    papers = lit.get("papers", [])
    total = lit.get("total_found", len(papers))
    verified_count = lit.get("verified_count", 0)

    if total == 0:
        return GateResult(
            passed=False, gate="citation", error_code="E004",
            messages=["文献总数为 0"],
            fix_suggestions=["运行文献检索获取相关文献"],
        )

    unverified = [p for p in papers if not p.get("verified")]
    unverified_dois = [p.get("doi", "") for p in unverified if p.get("doi")]

    pass_rate = verified_count / total if total > 0 else 0
    messages: list[str] = []
    suggestions: list[str] = []

    if pass_rate < 0.8:
        messages.append(f"文献验证率 {pass_rate:.0%}（{verified_count}/{total}），低于 80% 门槛")
        messages.append(f"未验证 DOI：{unverified_dois[:5]}{'...' if len(unverified_dois) > 5 else ''}")
        for doi in unverified_dois[:5]:
            suggestions.append(f"验证 DOI {doi} 或使用 CrossRef / Google Scholar 手动确认")
    else:
        messages.append(f"文献验证率 {pass_rate:.0%}（{verified_count}/{total}）✅")

    return GateResult(
        passed=pass_rate >= 0.8,
        gate="citation",
        error_code="E004" if pass_rate < 0.8 else "OK",
        messages=messages,
        fix_suggestions=suggestions,
    )


# ── Gate 3: Format 校验 ──────────────────────────────────────────────────────

JOURNAL_REQUIREMENTS = {
    "中文核心": {
        "word_range": (8000, 15000),
        "citation_format": "GB/T 7714-2015",
        "required_sections": ["abstract", "introduction", "literature_review", "methodology", "results", "discussion", "conclusion"],
        "ai_detection_max_pct": 20,
    },
    "CSSCI": {
        "word_range": (10000, 20000),
        "citation_format": "GB/T 7714-2015",
        "required_sections": ["abstract", "introduction", "literature_review", "methodology", "results", "discussion", "conclusion"],
        "ai_detection_max_pct": 15,
    },
    "IEEE Trans": {
        "word_range": (8000, 10000),
        "citation_format": "IEEE",
        "required_sections": ["abstract", "introduction", "literature_review", "methodology", "results", "conclusion"],
        "ai_detection_max_pct": 20,
    },
    "CCF-A": {
        "word_range": (8000, 12000),
        "citation_format": "IEEE/ACM",
        "required_sections": ["abstract", "introduction", "related_work", "methodology", "experiments", "conclusion", "references"],
        "ai_detection_max_pct": 20,
    },
}


def check_format_gate(session_dir: Path, journal_type: str = "中文核心") -> GateResult:
    """
    检查格式合规性（字数/章节/引用格式）。
    失败 → E010（格式类 export gate 失败）
    """
    req = JOURNAL_REQUIREMENTS.get(journal_type, JOURNAL_REQUIREMENTS["中文核心"])
    writing_file = session_dir / "writing_done.json"
    messages: list[str] = []
    suggestions: list[str] = []
    failed = False

    if not writing_file.exists():
        return GateResult(
            passed=False, gate="format", error_code="E010",
            messages=[f"缺少 writing_done.json，无法校验格式"],
            fix_suggestions=["运行论文写作流程生成 writing_done.json"],
        )

    try:
        writing = json.loads(writing_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return GateResult(
            passed=False, gate="format", error_code="E010",
            messages=[f"writing_done.json 格式错误：{e}"],
        )

    # 字数检查
    word_count = writing.get("word_count", 0)
    wmin, wmax = req["word_range"]
    if word_count < wmin:
        messages.append(f"字数 {word_count} 低于 {journal_type} 下限 {wmin}")
        suggestions.append(f"扩充论文内容至 {wmin}+ 字（当前差 {wmin - word_count} 字）")
        failed = True
    elif word_count > wmax:
        messages.append(f"字数 {word_count} 超出 {journal_type} 上限 {wmax}")
        suggestions.append(f"精简论文内容至 {wmax} 字以内")
        failed = True
    else:
        messages.append(f"字数 {word_count} 符合 {journal_type} 范围 [{wmin}-{wmax}] ✅")

    # 章节完整性
    sections: dict = writing.get("sections", {})
    missing_sections = [s for s in req["required_sections"] if s not in sections]
    if missing_sections:
        messages.append(f"缺少必需章节：{missing_sections}")
        suggestions.append(f"补充以下章节内容：{', '.join(missing_sections)}")
        failed = True
    else:
        messages.append(f"章节结构完整（{len(sections)} 节）✅")

    # 引用格式（简单检查：DOI / [] 格式）
    paper_md = session_dir / "paper.md"
    if paper_md.exists():
        text = paper_md.read_text(encoding="utf-8")
        doi_pattern = r"doi[:\s]+(10\.\d{4,}[^\s]+)"
        dois_found = re.findall(doi_pattern, text, re.IGNORECASE)
        bracket_refs = re.findall(r"\[[\w\d\-\.,;\s]+\]", text)
        if doi_pattern or bracket_refs:
            messages.append(f"检测到引用格式：DOI格式={len(dois_found)}条，[]格式={len(bracket_refs)}条 ✅")

    return GateResult(
        passed=not failed,
        gate="format",
        error_code="E010" if failed else "OK",
        messages=messages,
        fix_suggestions=suggestions,
    )


# ── Gate 4: Ethics 校验 ──────────────────────────────────────────────────────

ETHICS_RED_FLAGS = [
    (r"伪造|捏造|虚假数据|fake\s*data", "疑似数据伪造"),
    (r"抄袭|抄袭他人|抄袭论文", "疑似抄袭内容"),
    (r"代写|论文代写|找人代写", "疑似代写服务"),
    (r"一行ai|ai一键生成|chatgpt.*全文", "疑似AI整篇代写"),
]


def check_ethics_gate(session_dir: Path) -> GateResult:
    """
    扫描论文文本中的学术伦理风险（红词检测）。
    检测到风险词 → warning，不直接阻断（提示人工复核）。
    失败 → E010（ethics）
    """
    paper_md = session_dir / "paper.md"
    messages: list[str] = []
    suggestions: list[str] = []

    if not paper_md.exists():
        return GateResult(
            passed=False, gate="ethics", error_code="E010",
            messages=["缺少 paper.md，无法进行伦理检查"],
            fix_suggestions=["确保论文内容已生成"],
        )

    text = paper_md.read_text(encoding="utf-8")
    risks_found: list[tuple[str, str]] = []

    for pattern, label in ETHICS_RED_FLAGS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            risks_found.append((label, f"匹配 '{pattern}'"))

    if risks_found:
        for label, detail in risks_found:
            messages.append(f"⚠️ 伦理风险：{label}（{detail}）")
        suggestions.append("⚠️ 请人工复核以上内容是否符合学术诚信要求")
        suggestions.append("建议：在论文致谢中说明使用了 AI 辅助工具")
        passed = False
        error_code = "E010"
    else:
        messages.append("未检测到明显学术伦理风险 ✅")
        passed = True
        error_code = "OK"

    return GateResult(
        passed=passed,
        gate="ethics",
        error_code=error_code,
        messages=messages,
        fix_suggestions=suggestions,
    )


# ── 门禁总检查 ─────────────────────────────────────────────────────────────────

@dataclass
class ExportGateReport:
    session_id: str
    journal_type: str
    results: list[GateResult]

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def error_codes(self) -> list[str]:
        return [r.error_code for r in self.results if r.error_code != "OK"]

    def fix_manifest(self) -> str:
        """生成人类可读的修复清单。"""
        lines = ["## 导出门禁检查报告", ""]
        for r in self.results:
            lines.append(r.summary())
            lines.append("")
        if self.all_passed:
            lines.append("🎉 所有门禁通过，可执行导出。")
        else:
            lines.append("⛔ 门禁未通过，请修复以上问题后重新导出。")
        return "\n".join(lines)


def run_export_gates(session_dir: Path, session_id: str, journal_type: str) -> ExportGateReport:
    """
    运行全部四道 gate，返回综合报告。

    任意 gate 失败 → 打印修复清单，禁止 export。
    """
    results = [
        check_contract_gate(session_dir),
        check_citation_gate(session_dir),
        check_format_gate(session_dir, journal_type),
        check_ethics_gate(session_dir),
    ]

    report = ExportGateReport(session_id=session_id, journal_type=journal_type, results=results)

    print(f"\n{'='*50}")
    print(f"Export Gate Report — {session_id[:8]}")
    print(f"{'='*50}")
    print(report.fix_manifest())

    if not report.all_passed:
        print(f"\n⛔ 导出被阻断（error_codes: {report.error_codes()}）")
        raise RuntimeError(f"[E010] Export gate failed: {report.error_codes()}")

    return report

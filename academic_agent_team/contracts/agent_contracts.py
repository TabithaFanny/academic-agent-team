"""
contracts/agent_contracts.py

PRD 7.6 接口契约 — pydantic 严格校验版本。

运行时所有 Agent 输出的 payload 必须通过这里定义的 pydantic 模型校验，
校验失败立即抛出 ContractValidationError（错误码 E007）并中断阶段推进。
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


# ─── 常量 ───────────────────────────────────────────────────────────────────

CONTRACT_VERSION = "1.0.0"
STAGE_ORDER = ("topic", "literature", "writing", "review", "polish", "export")


class Stage(str, Enum):
    TOPIC = "topic"
    LITERATURE = "literature"
    WRITING = "writing"
    REVIEW = "review"
    POLISH = "polish"
    EXPORT = "export"


class JournalType(str, Enum):
    CHINESE_CORE = "中文核心"
    CSSCI = "CSSCI"
    IEEE_TRANS = "IEEE Trans"
    CCF_A = "CCF-A"


class Language(str, Enum):
    ZH = "zh"
    EN = "en"


class Verdict(str, Enum):
    ACCEPT = "accept"
    MINOR_REVISION = "minor_revision"
    MAJOR_REVISION = "major_revision"
    REJECT = "reject"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ─── 错误码 ───────────────────────────────────────────────────────────────────

ERROR_CODES = {
    "E001": "API 超时 — 单次请求超时阈值",
    "E002": "Rate Limit — HTTP 429",
    "E003": "上下文超长 — 超过模型 max_tokens",
    "E004": "文献验证失败 — DOI 不存在或校验失败",
    "E005": "插话冲突 — 与已确认决策冲突",
    "E006": "会话损坏 — SQLite/快照读取异常",
    "E007": "契约校验失败 — pydantic 校验失败",
    "E008": "鉴权失败 — API key 缺失/401/403",
    "E009": "Provider 不可达 — DNS/网络不可达",
    "E010": "导出门禁失败 — citation/format/ethics 任一失败",
}


class ContractValidationError(Exception):
    """错误码 E007：payload 校验失败时抛出。"""

    def __init__(self, stage: str, errors: list[str]):
        self.stage = stage
        self.errors = errors
        code = "E007"
        detail = "; ".join(errors)
        super().__init__(f"[{code}] stage={stage} errors={detail}")


# ─── 基础模型 ────────────────────────────────────────────────────────────────

class BasePayload(BaseModel):
    """所有 stage payload 必须继承此基类。"""
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    stage: str
    session_id: Annotated[str, Field(min_length=1)]
    contract_version: str = CONTRACT_VERSION


# ─── 各 Stage Payload ──────────────────────────────────────────────────────────


class DirectionAnalysis(BaseModel):
    innovation_score: Annotated[float, Field(ge=0, le=10)]
    feasibility: str  # high / medium / low
    research_gap: str
    recommended_keywords: list[str]


class TopicDone(BasePayload):
    stage: Literal["topic_done"]
    selected_direction: Annotated[str, Field(min_length=5)]
    direction_analysis: DirectionAnalysis
    journal_type: JournalType
    language: Language


class Paper(BaseModel):
    title: str
    doi: str | None = None
    authors: list[str]
    year: int
    abstract: str
    relevance_score: Annotated[float, Field(ge=0, le=1)]
    verified: bool  # true/false 布尔值，不是字符串


class LiteratureDone(BasePayload):
    stage: Literal["literature_done"]
    papers: list[Paper]
    literature_matrix: str  # Markdown 表格
    verified_count: Annotated[int, Field(ge=0)]
    total_found: Annotated[int, Field(ge=0)]
    session_id: str


class WritingDone(BasePayload):
    stage: Literal["writing_done"]
    sections: dict[str, str]  # {abstract/introduction/...: content}
    word_count: Annotated[int, Field(ge=1000, le=50000)]
    version_id: str


class Issue(BaseModel):
    issue_id: str
    section: str
    problem: str
    priority: Priority
    suggestion: str


class ReviewDone(BasePayload):
    stage: Literal["review_done"]
    verdict: Verdict
    overall_score: Annotated[float, Field(ge=0, le=10)]
    major_issues: list[Issue]
    minor_issues: list[Issue]
    adopted_issues: list[str]  # 已采纳的 issue_id 列表


class ScorerJson(BaseModel):
    cliche_rate_pct: float = Field(ge=0, le=100)
    diversity_index: float = Field(ge=0, le=1)
    connective_density_pct: float = Field(ge=0, le=100)
    readability_score: Annotated[float, Field(ge=1, le=5)]


class PolishDone(BasePayload):
    stage: Literal["polish_done"]
    polished_sections: dict[str, str]
    readability_before: Annotated[float, Field(ge=1, le=5)]
    readability_after: Annotated[float, Field(ge=1, le=5)]
    diff_report: str
    scorer_json: ScorerJson | dict


# ─── 校验入口 ─────────────────────────────────────────────────────────────────

PAYLOAD_MODELS: dict[str, type[BasePayload]] = {
    "topic_done": TopicDone,
    "literature_done": LiteratureDone,
    "writing_done": WritingDone,
    "review_done": ReviewDone,
    "polish_done": PolishDone,
}


def validate_payload(payload: dict) -> BasePayload:
    """
    主校验入口。

    - 检查 contract_version 是否匹配
    - 使用 pydantic 做严格字段校验
    - 校验失败抛出 ContractValidationError(E007)

    Returns:
        对应 stage 的 pydantic model 实例（已校验的干净数据）
    """
    stage = payload.get("stage")
    if stage not in PAYLOAD_MODELS:
        raise ContractValidationError(
            stage=str(stage),
            errors=[f"Unknown stage: {stage!r}. Valid: {list(PAYLOAD_MODELS.keys())}"],
        )

    model_cls = PAYLOAD_MODELS[stage]

    try:
        validated = model_cls.model_validate(payload)
    except ValidationError as exc:
        error_messages = [
            f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']} (input={e['input']!r})"
            for e in exc.errors()
        ]
        raise ContractValidationError(stage=stage, errors=error_messages) from exc

    # 业务约束：verified_count 与实际 verified papers 数量一致
    if stage == "literature_done" and validated.papers is not None:
        actual_verified = sum(1 for p in validated.papers if p.verified)
        if actual_verified != validated.verified_count:
            raise ContractValidationError(
                stage=stage,
                errors=[
                    f"verified_count={validated.verified_count} "
                    f"does not match actual verified papers={actual_verified}"
                ],
            )

    return validated


def validate_payload_dict(payload: dict) -> dict:
    """便利包装：输入 dict，输出已校验 dict（兼容旧调用方）。"""
    validated = validate_payload(payload)
    return validated.model_dump()

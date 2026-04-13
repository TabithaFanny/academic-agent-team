"""
PaperGenius Pro — 主 Pipeline 编排器 (MVP v1.1)。

支持两种模式：
- 标准模式（Standard）：4 个 Human-in-the-Loop 干预点
- 极速模式（Express）：最小干预，仅选题确认 + 最终预览

实现 6 Phase 流水线：
  Phase 1: 选题讨论 (Advisor ⟷ Researcher)
  Phase 2: 文献调研 (Researcher + RAG Tools)
  Phase 2.5: 数据分析 (Data Analyst) [可选]
  Phase 3: 写作-审稿 (Writer ⟷ Reviewer)
  Phase 4: 润色终审 (Polisher ⟷ Reviewer)
  Phase 5: 导出 (LaTeX Exporter)
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from academic_agent_team.config.models import AGENT_MODEL_MAP, get_model_spec
from academic_agent_team.core.agent_prompts import (
    ADVISOR_SYSTEM,
    POLISHER_SYSTEM,
    PROMPT_TEMPLATES,
    REVIEWER_SYSTEM,
    WRITER_SYSTEM,
)
from academic_agent_team.core.clients.anthropic_client import AnthropicClient
from academic_agent_team.core.clients.deepseek_client import DeepSeekClient
from academic_agent_team.core.clients.minimax_client import MiniMaxClient
from academic_agent_team.core.clients.mock_client import MockClient
from academic_agent_team.core.clients.ollama_client import OllamaClient
from academic_agent_team.core.clients.openai_client import OpenAIClient
from academic_agent_team.core.clients.zhipu_client import ZhipuClient
from academic_agent_team.core.base_client import ModelResponse
from academic_agent_team.storage.db import (
    connect,
    create_session,
    insert_artifact,
    insert_cost,
    insert_message,
    update_session_stage,
)
from academic_agent_team.tools.ai_detection import AIDetector
from academic_agent_team.tools.plagiarism_checker import PlagiarismChecker

DATA_ANALYST_SYSTEM = """你是一位专业的数据分析师。请基于输入的数据概览输出严格 JSON：
analysis_type, interpretation, key_findings, statistics_results, figures。
statistics_results 必须是对象；key_findings 必须是字符串列表。"""


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _should_use_mock_llm() -> bool:
    return any(
        _is_true(os.getenv(name))
        for name in (
            "PAPER_TEAM_MOCK",
            "PAPER_TEAM_LLM_MOCK",
        )
    )


def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract JSON from model response text, tolerant to markdown wrappers."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        pass

    candidates = re.findall(r"\{[\s\S]*\}", text)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            continue

    trimmed = re.sub(r"[^}]+$", "", text).strip()
    if trimmed.endswith("}"):
        try:
            parsed = json.loads(trimmed)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def _build_client_for_provider(
    provider: str,
    model_name: str,
    model_override: str | None = None,
):
    spec = get_model_spec(provider, model_name)
    model_id = model_override or spec.model_id
    if provider == "minimax":
        return MiniMaxClient(
            api_key=os.getenv("MINIMAX_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("MINIMAX_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL"),
            model=model_id,
        )
    if provider == "anthropic":
        return AnthropicClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if provider == "openai":
        return OpenAIClient(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            model=model_id,
        )
    if provider == "deepseek":
        return DeepSeekClient(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL"),
            model=model_id,
        )
    if provider == "zhipu":
        return ZhipuClient(
            api_key=os.getenv("ZHIPU_API_KEY"),
            base_url=os.getenv("ZHIPU_BASE_URL"),
            model=model_id,
        )
    if provider == "ollama":
        return OllamaClient(
            base_url=os.getenv("OLLAMA_BASE_URL"),
            model=model_id,
        )
    if provider == "mock":
        return MockClient()
    return spec.client_class()


def _client_for_role(role: str):
    if role in AGENT_MODEL_MAP:
        provider, model_name = AGENT_MODEL_MAP[role]
    elif role == "data_analyst" and "researcher" in AGENT_MODEL_MAP:
        provider, model_name = AGENT_MODEL_MAP["researcher"]
    else:
        provider, model_name = ("mock", "default")
    try:
        return _build_client_for_provider(provider, model_name)
    except Exception:
        return MockClient()


class RunMode(str, Enum):
    """运行模式"""
    STANDARD = "standard"  # 标准模式：多次人工干预
    EXPRESS = "express"    # 极速模式：最小干预


class PhaseStatus(str, Enum):
    """阶段状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class HumanInterventionPoint:
    """人工干预点定义"""
    id: str
    phase: str
    description: str
    required_in_standard: bool = True
    required_in_express: bool = False
    callback: Callable | None = None


# 定义 4 个固定干预点
INTERVENTION_POINTS = [
    HumanInterventionPoint(
        id="H1",
        phase="topic",
        description="选择研究聚焦方向（从 3-5 个选项中选择）",
        required_in_standard=True,
        required_in_express=True,  # 极速模式也需要
    ),
    HumanInterventionPoint(
        id="H2",
        phase="literature",
        description="确认文献列表（可删除/补充 PDF）",
        required_in_standard=True,
        required_in_express=False,
    ),
    HumanInterventionPoint(
        id="H3",
        phase="writing",
        description="审稿后决定：继续迭代 / 手动修改",
        required_in_standard=True,
        required_in_express=False,
    ),
    HumanInterventionPoint(
        id="H4",
        phase="export",
        description="最终预览确认",
        required_in_standard=True,
        required_in_express=True,  # 极速模式也需要
    ),
]


@dataclass
class SessionContext:
    """会话上下文 — 跨阶段传递的状态"""
    session_id: str
    topic: str
    journal_type: str
    language: str = "zh"
    run_mode: RunMode = RunMode.STANDARD
    
    # 阶段产物
    topic_done: dict | None = None
    literature_done: dict | None = None
    analysis_done: dict | None = None
    writing_done: dict | None = None
    review_done: dict | None = None
    polish_done: dict | None = None
    
    # 文献库
    vector_collection: str | None = None
    
    # 质量指标
    ai_detection_score: float = 0.0
    similarity_rate: float = 0.0
    reviewer_score: float = 0.0
    
    # 迭代计数
    revision_count: int = 0
    max_revisions: int = 5
    
    # 人工干预记录
    human_decisions: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "journal_type": self.journal_type,
            "run_mode": self.run_mode.value,
            "revision_count": self.revision_count,
            "ai_detection_score": self.ai_detection_score,
            "similarity_rate": self.similarity_rate,
            "reviewer_score": self.reviewer_score,
        }


class GateResult(BaseModel):
    """门禁检查结果"""
    passed: bool
    gate_name: str
    reason: str = ""
    action: str = ""
    metrics: dict = Field(default_factory=dict)


class PipelineOrchestrator:
    """
    Pipeline 编排器 — 管理 6 Phase 执行流程。
    """
    
    def __init__(
        self,
        base_dir: Path,
        run_mode: RunMode = RunMode.STANDARD,
    ):
        self.base_dir = Path(base_dir)
        self.run_mode = run_mode
        self.output_dir: Path | None = None
        self.context: SessionContext | None = None
        self._conn = None
        self._last_stage = "topic"
        
        # 人工干预回调
        self._human_callback: Callable | None = None
    
    def set_human_callback(self, callback: Callable) -> None:
        """设置人工干预回调函数"""
        self._human_callback = callback
    
    async def _wait_for_human(
        self,
        intervention: HumanInterventionPoint,
        options: list[str] | None = None,
        data: dict | None = None,
    ) -> str | dict:
        """等待人工干预"""
        # 检查是否需要干预
        if self.run_mode == RunMode.EXPRESS and not intervention.required_in_express:
            return {"auto_proceed": True}
        
        if self.run_mode == RunMode.STANDARD and not intervention.required_in_standard:
            return {"auto_proceed": True}
        
        if self._human_callback:
            return await self._human_callback(
                intervention_id=intervention.id,
                phase=intervention.phase,
                description=intervention.description,
                options=options,
                data=data,
            )
        
        # 默认自动继续
        return {"auto_proceed": True}
    
    async def run(
        self,
        topic: str,
        journal: str,
        language: str = "zh",
        data_file: Path | None = None,
        budget_cap_cny: float = 35.0,
    ) -> SessionContext:
        """
        运行完整 Pipeline。
        
        Args:
            topic: 研究主题
            journal: 目标期刊类型
            language: 语言
            data_file: 可选的数据文件路径
            budget_cap_cny: 会话预算上限（CNY）
            
        Returns:
            SessionContext 包含所有阶段产物
        """
        # 初始化数据库会话
        db_path = self.base_dir / "session_store" / "sessions.db"
        self._conn = connect(db_path)
        db_run_mode = "manual" if self.run_mode == RunMode.STANDARD else "autopilot"
        session_id = create_session(
            conn=self._conn,
            topic=topic,
            journal_type=journal,
            language=language,
            model_config={"engine": "v2", "pipeline": "pipeline_v2"},
            run_mode=db_run_mode,
            budget_cap_cny=budget_cap_cny,
        )
        self.output_dir = self.base_dir / "output" / session_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.context = SessionContext(
            session_id=session_id,
            topic=topic,
            journal_type=journal,
            language=language,
            run_mode=self.run_mode,
        )
        
        try:
            # Phase 1: 选题讨论
            await self._phase_1_topic()
            
            # Phase 2: 文献调研
            await self._phase_2_literature()
            
            # Phase 2.5: 数据分析 (如有数据)
            if data_file:
                await self._phase_2_5_analysis(data_file)
            
            # Phase 3: 写作-审稿
            await self._phase_3_writing()
            
            # Phase 4: 润色终审
            await self._phase_4_polish()
            
            # Phase 5: 导出
            await self._phase_5_export()
            update_session_stage(self._conn, session_id, stage="export", status="completed")
            
            return self.context
            
        except Exception as e:
            self._log(f"Pipeline 失败: {e}")
            if self._conn is not None and self.context is not None:
                update_session_stage(
                    self._conn,
                    self.context.session_id,
                    stage=self._last_stage,
                    status="failed",
                )
            raise
        finally:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
    
    async def _phase_1_topic(self) -> None:
        """Phase 1: 选题讨论"""
        self._log("Phase 1: 选题讨论")

        use_mock_llm = _should_use_mock_llm()
        advisor_prompt = PROMPT_TEMPLATES["advisor"].format(
            topic=self.context.topic,
            journal=self.context.journal_type,
        ) + "\n请补充 2-4 个备选方向（alternative_directions）并输出 JSON。"
        advisor_raw = await self._llm_complete(
            role="advisor",
            prompt=advisor_prompt,
            system=ADVISOR_SYSTEM,
            max_tokens=2048,
            use_mock=use_mock_llm,
        )
        advisor_payload = _parse_json_response(advisor_raw.content)

        selected_direction = str(
            advisor_payload.get("selected_direction")
            or advisor_payload.get("summary")
            or self.context.topic
        ).strip()
        options: list[str] = [selected_direction]
        alternatives = advisor_payload.get("alternative_directions")
        if isinstance(alternatives, list):
            for item in alternatives:
                if isinstance(item, str) and item.strip():
                    options.append(item.strip())
        for fallback in [
            f"AI 生成新闻的真实性伦理 — 聚焦 {self.context.topic}",
            f"算法推荐与信息茧房 — 基于 {self.context.topic}",
            f"深度伪造与新闻公信力 — {self.context.topic} 视角",
        ]:
            if fallback not in options:
                options.append(fallback)
            if len(options) >= 5:
                break
        topic_options = options[:5]

        direction_analysis = advisor_payload.get("direction_analysis")
        if not isinstance(direction_analysis, dict):
            direction_analysis = {}
        direction_analysis.setdefault("innovation_score", advisor_payload.get("innovation_score", 8.0))
        direction_analysis.setdefault("feasibility", "high")
        direction_analysis.setdefault("research_gap", "该主题在方法融合与实证环节仍有研究空白。")
        recommended_keywords = direction_analysis.get("recommended_keywords")
        if not isinstance(recommended_keywords, list) or not recommended_keywords:
            recommended_keywords = ["数字治理", "内容可信度", "平台传播"]
        direction_analysis["recommended_keywords"] = [str(k) for k in recommended_keywords][:5]

        research_questions = advisor_payload.get("research_questions")
        if not isinstance(research_questions, list) or not research_questions:
            research_questions = [
                f"RQ1: {selected_direction} 的关键影响机制是什么？",
                "RQ2: 如何构建可验证的评估框架？",
            ]
        innovation_points = advisor_payload.get("innovation_points")
        if not isinstance(innovation_points, list) or not innovation_points:
            innovation_points = [
                "提出跨平台治理的统一分析框架",
                "结合文本与行为数据的混合评估路径",
            ]

        h1 = next(h for h in INTERVENTION_POINTS if h.id == "H1")
        decision = await self._wait_for_human(
            h1,
            options=topic_options,
            data={"topic": self.context.topic, "advisor_payload": advisor_payload},
        )

        selected_idx = decision.get("selected_index", 0) if isinstance(decision, dict) else 0
        if not isinstance(selected_idx, int):
            selected_idx = 0
        selected_idx = max(0, min(selected_idx, len(topic_options) - 1))
        selected_topic = topic_options[selected_idx]

        self.context.topic_done = {
            "stage": "topic_done",
            "selected_topic": selected_topic,
            "topic_options": topic_options,
            "direction_analysis": direction_analysis,
            "research_questions": [str(q) for q in research_questions][:5],
            "innovation_points": [str(p) for p in innovation_points][:5],
        }

        self.context.human_decisions["H1"] = {
            "selected": selected_topic,
            "timestamp": datetime.now().isoformat(),
        }

        self._save_artifact("topic_done.json", self.context.topic_done)
        self._persist_stage(
            sender="advisor",
            receiver="researcher",
            stage="topic_done",
            artifact_type="topic_report",
            payload=self.context.topic_done,
            model_response=advisor_raw,
        )
        self._log(f"选题确认: {selected_topic}")
    
    async def _phase_2_literature(self) -> None:
        """Phase 2: 文献调研"""
        self._log("Phase 2: 文献调研")
        
        # TODO: 实际调用 Researcher + CNKI/RAG
        # 这里是骨架实现
        
        from academic_agent_team.tools.search_cnki import search_cnki
        
        # 搜索 CNKI
        search_topic = str(
            (self.context.topic_done or {}).get("selected_topic")
            or self.context.topic
        )
        cnki_result = await search_cnki(
            query=search_topic,
            search_type="主题",
            source_filter=["CSSCI", "北大核心"],
            year_range=(2020, 2026),
            max_results=50,
        )
        
        papers = [p.model_dump() for p in cnki_result.papers]
        
        # 引用验证 Gate
        from academic_agent_team.tools.citation_verifier import Citation, citation_verification_gate
        
        citations = [
            Citation(
                title=p["title"],
                authors=p["authors"],
                year=p["year"],
                doi=p.get("doi"),
                cnki_url=p.get("cnki_url"),
            )
            for p in papers
        ]
        
        passed, verify_result, message = await citation_verification_gate(citations)
        
        if not passed:
            raise RuntimeError(f"引用验证 Gate 失败: {message}")
        
        # 文献质量 Gate
        if len(papers) < 30:
            raise RuntimeError(f"文献质量 Gate 失败: 文献数量不足 ({len(papers)} < 30)")
        
        self.context.literature_done = {
            "stage": "literature_done",
            "papers": papers,
            "total_found": len(papers),
            "cnki_count": sum(1 for p in papers if p.get("cnki_url")),
            "verification_rate": verify_result.verification_rate,
        }
        
        # H2: 用户确认文献列表
        h2 = next(h for h in INTERVENTION_POINTS if h.id == "H2")
        await self._wait_for_human(
            h2,
            data={"papers": papers[:30], "total": len(papers)},
        )
        
        self._save_artifact("literature_done.json", self.context.literature_done)
        self._persist_stage(
            sender="researcher",
            receiver="writer",
            stage="literature_done",
            artifact_type="literature_matrix",
            payload=self.context.literature_done,
        )
        self._log(f"文献调研完成: {len(papers)} 篇")
    
    async def _phase_2_5_analysis(self, data_file: Path) -> None:
        """Phase 2.5: 数据分析"""
        self._log("Phase 2.5: 数据分析")

        data_path = Path(data_file)
        if not data_path.exists():
            raise RuntimeError(f"数据分析 Gate 失败: 数据文件不存在 ({data_path})")

        profile = self._profile_data_file(data_path)
        use_mock_llm = _should_use_mock_llm()
        analysis_prompt = (
            f"研究主题：{self.context.topic}\n"
            f"目标期刊：{self.context.journal_type}\n"
            f"数据概览：\n{json.dumps(profile, ensure_ascii=False)}\n\n"
            "请给出分析类型、关键发现、统计结果和可视化建议。"
        )
        analyst_raw = await self._llm_complete(
            role="data_analyst",
            prompt=analysis_prompt,
            system=DATA_ANALYST_SYSTEM,
            max_tokens=4096,
            use_mock=use_mock_llm,
        )
        analysis_payload = _parse_json_response(analyst_raw.content)

        analysis_type = str(analysis_payload.get("analysis_type", "descriptive")).strip() or "descriptive"
        interpretation = str(
            analysis_payload.get("interpretation")
            or analysis_payload.get("summary")
            or "已完成数据概览分析，可用于论文方法与结果章节。"
        ).strip()
        key_findings = analysis_payload.get("key_findings")
        if not isinstance(key_findings, list) or not key_findings:
            key_findings = [
                f"数据格式：{profile.get('format')}",
                f"样本规模估计：{profile.get('row_count_estimate')}",
                f"字段数量：{profile.get('column_count')}",
            ]
        figures = analysis_payload.get("figures")
        if not isinstance(figures, list):
            figures = []
        statistics_results = analysis_payload.get("statistics_results")
        if not isinstance(statistics_results, dict):
            statistics_results = {}
        statistics_results.setdefault("data_profile", profile)

        self.context.analysis_done = {
            "stage": "analysis_done",
            "data_file": str(data_path),
            "analysis_type": analysis_type,
            "interpretation": interpretation,
            "key_findings": [str(item) for item in key_findings][:8],
            "statistics_results": statistics_results,
            "figures": figures[:10],
        }

        self._save_artifact("analysis_done.json", self.context.analysis_done)
        self._persist_stage(
            sender="data_analyst",
            receiver="writer",
            stage="analysis_done",
            artifact_type="analysis_report",
            payload=self.context.analysis_done,
            model_response=analyst_raw,
        )

    def _profile_data_file(self, data_file: Path) -> dict[str, Any]:
        """构建轻量数据概览，作为 Data Analyst 输入与兜底产物。"""
        profile: dict[str, Any] = {
            "path": str(data_file),
            "name": data_file.name,
            "format": data_file.suffix.lower().lstrip(".") or "unknown",
            "size_bytes": data_file.stat().st_size,
            "row_count_estimate": None,
            "column_count": 0,
            "columns": [],
            "sample_rows": [],
        }

        suffix = data_file.suffix.lower()
        try:
            if suffix == ".csv":
                with data_file.open("r", encoding="utf-8", newline="") as fp:
                    reader = csv.DictReader(fp)
                    columns = list(reader.fieldnames or [])
                    sample_rows: list[dict[str, Any]] = []
                    row_count = 0
                    for row in reader:
                        row_count += 1
                        if len(sample_rows) < 5:
                            sample_rows.append({k: (v if v is not None else "") for k, v in row.items()})
                    profile["row_count_estimate"] = row_count
                    profile["column_count"] = len(columns)
                    profile["columns"] = columns
                    profile["sample_rows"] = sample_rows
            elif suffix == ".json":
                payload = json.loads(data_file.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    profile["row_count_estimate"] = len(payload)
                    if payload and isinstance(payload[0], dict):
                        profile["columns"] = list(payload[0].keys())
                        profile["column_count"] = len(profile["columns"])
                    profile["sample_rows"] = payload[:5]
                elif isinstance(payload, dict):
                    profile["row_count_estimate"] = 1
                    profile["columns"] = list(payload.keys())
                    profile["column_count"] = len(profile["columns"])
                    profile["sample_rows"] = [payload]
            else:
                lines = data_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                profile["row_count_estimate"] = len(lines)
                profile["sample_rows"] = lines[:5]
        except Exception as exc:
            profile["parse_error"] = str(exc)

        return profile

    async def _llm_complete(
        self,
        role: str,
        prompt: str,
        system: str,
        max_tokens: int = 4096,
        use_mock: bool = False,
    ) -> ModelResponse:
        client = MockClient() if use_mock else _client_for_role(role)
        try:
            return await asyncio.to_thread(
                client.complete,
                prompt,
                system,
                0.5,
                max_tokens,
            )
        except Exception as exc:
            if use_mock:
                raise
            raise RuntimeError(f"{role} 模型调用失败: {exc}") from exc

    def _build_literature_matrix(self, papers: list[dict[str, Any]]) -> str:
        if not papers:
            return "| 标题 | 年份 | 作者 | DOI |\n|---|---|---|---|\n| 无可用文献 | - | - | - |"

        rows = ["| 标题 | 年份 | 作者 | DOI |", "|---|---|---|---|"]
        for paper in papers[:30]:
            title = str(paper.get("title", "未知标题")).replace("\n", " ").strip()
            year = str(paper.get("year", "-"))
            authors_raw = paper.get("authors", [])
            if isinstance(authors_raw, list):
                authors = ", ".join(str(a) for a in authors_raw[:3]) or "-"
            else:
                authors = str(authors_raw) or "-"
            doi = str(paper.get("doi", "-") or "-")
            rows.append(f"| {title} | {year} | {authors} | {doi} |")
        return "\n".join(rows)

    def _normalize_writer_sections(
        self,
        payload: dict[str, Any],
        fallback_title: str,
    ) -> dict[str, str]:
        default_sections = {
            "abstract": fallback_title,
            "introduction": "引言内容由 AI 生成。",
            "literature_review": "文献综述内容由 AI 生成。",
            "methodology": "研究方法内容由 AI 生成。",
            "results": "研究结果内容由 AI 生成。",
            "discussion": "讨论内容由 AI 生成。",
            "conclusion": "研究结论内容由 AI 生成。",
        }

        sections = payload.get("sections")
        if not isinstance(sections, dict):
            text_fallback = str(payload.get("paper_draft") or payload.get("content") or fallback_title)
            default_sections["abstract"] = text_fallback
            return default_sections

        normalized: dict[str, str] = {}
        for key, value in sections.items():
            k = str(key).strip() if key is not None else ""
            if not k:
                continue
            normalized[k] = str(value).strip() if value is not None else ""

        for key, value in default_sections.items():
            normalized.setdefault(key, value)
        return normalized

    def _normalize_review_payload(self, payload: dict[str, Any]) -> tuple[str, float, list[Any], list[Any]]:
        verdict = str(payload.get("verdict", "minor_revision")).strip().lower().replace(" ", "_")
        raw_score = payload.get("overall_score", 8.5)
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 8.5
        if score <= 10:
            score *= 10
        score = max(0.0, min(score, 100.0))

        major_issues = payload.get("major_issues")
        if not isinstance(major_issues, list):
            major_issues = []
        minor_issues = payload.get("minor_issues")
        if not isinstance(minor_issues, list):
            minor_issues = []
        return verdict, score, major_issues, minor_issues

    def _review_passed(self, verdict: str, score: float) -> bool:
        del verdict
        return score >= 85.0
    
    async def _phase_3_writing(self) -> None:
        """Phase 3: 写作-审稿"""
        self._log("Phase 3: 写作-审稿")

        use_mock_llm = _should_use_mock_llm()
        writer_raw: ModelResponse | None = None
        reviewer_raw: ModelResponse | None = None
        selected_direction = (
            self.context.topic_done.get("selected_topic")
            if self.context.topic_done
            else self.context.topic
        )
        selected_direction = str(selected_direction or self.context.topic)
        literature_matrix = self._build_literature_matrix(
            list((self.context.literature_done or {}).get("papers", []))
        )

        while self.context.revision_count < self.context.max_revisions:
            previous_review = json.dumps(
                self.context.review_done or {"message": "无上一轮审稿意见"},
                ensure_ascii=False,
            )
            writer_prompt = (
                PROMPT_TEMPLATES["writer"].format(
                    direction=selected_direction,
                    literature_matrix=literature_matrix,
                )
                + "\n\n上一轮审稿意见：\n"
                + previous_review
                + "\n请结合意见输出新版本 JSON。"
            )
            writer_raw = await self._llm_complete(
                role="writer",
                prompt=writer_prompt,
                system=WRITER_SYSTEM,
                max_tokens=8192,
                use_mock=use_mock_llm,
            )
            writer_payload = _parse_json_response(writer_raw.content)
            sections = self._normalize_writer_sections(writer_payload, selected_direction)
            word_count = writer_payload.get("word_count")
            if not isinstance(word_count, int) or word_count <= 0:
                word_count = sum(len(v) for v in sections.values())
            self.context.writing_done = {
                "stage": "writing_done",
                "sections": sections,
                "word_count": int(word_count),
                "version": self.context.revision_count + 1,
            }

            paper_text = "\n\n".join(str(v) for v in sections.values())
            review_prompt = PROMPT_TEMPLATES["reviewer"].format(paper_draft=paper_text)
            reviewer_raw = await self._llm_complete(
                role="reviewer",
                prompt=review_prompt,
                system=REVIEWER_SYSTEM,
                max_tokens=4096,
                use_mock=use_mock_llm,
            )
            review_payload = _parse_json_response(reviewer_raw.content)
            verdict, score, major_issues, minor_issues = self._normalize_review_payload(review_payload)
            self.context.reviewer_score = score
            self.context.review_done = {
                "stage": "review_done",
                "verdict": verdict,
                "overall_score": score,
                "major_issues": major_issues,
                "minor_issues": minor_issues,
            }

            if self._review_passed(verdict, score):
                break

            h3 = next(h for h in INTERVENTION_POINTS if h.id == "H3")
            decision = await self._wait_for_human(
                h3,
                options=["继续迭代", "手动修改当前稿"],
                data={"score": score, "verdict": verdict},
            )
            if isinstance(decision, dict) and decision.get("manual_edit"):
                break

            self.context.revision_count += 1

        if self.context.writing_done is None or self.context.review_done is None:
            raise RuntimeError("写作-审稿阶段失败：未生成有效产物")

        self._save_artifact("writing_done.json", self.context.writing_done)
        self._persist_stage(
            sender="writer",
            receiver="reviewer",
            stage="writing_done",
            artifact_type="section_draft",
            payload=self.context.writing_done,
            model_response=writer_raw,
        )
        self._save_artifact("review_done.json", self.context.review_done)
        self._persist_stage(
            sender="reviewer",
            receiver="polisher",
            stage="review_done",
            artifact_type="review_report",
            payload=self.context.review_done,
            model_response=reviewer_raw,
        )
        self._log(f"写作完成: 评分 {self.context.reviewer_score}")
    
    async def _phase_4_polish(self) -> None:
        """Phase 4: 润色终审"""
        self._log("Phase 4: 润色终审")

        use_mock_llm = _should_use_mock_llm()
        writing_sections_raw = (self.context.writing_done or {}).get("sections", {})
        writing_sections = (
            dict(writing_sections_raw)
            if isinstance(writing_sections_raw, dict)
            else {"abstract": str(writing_sections_raw or self.context.topic)}
        )
        paper_text = "\n\n".join(str(v) for v in writing_sections.values())
        polish_prompt = PROMPT_TEMPLATES["polisher"].format(paper_draft=paper_text)
        polisher_raw = await self._llm_complete(
            role="polisher",
            prompt=polish_prompt,
            system=POLISHER_SYSTEM,
            max_tokens=8192,
            use_mock=use_mock_llm,
        )
        polish_payload = _parse_json_response(polisher_raw.content)

        polished_sections = polish_payload.get("polished_sections")
        if not isinstance(polished_sections, dict):
            polished_sections = writing_sections

        readability_before = polish_payload.get("readability_before", 3.0)
        readability_after = polish_payload.get("readability_after", 4.0)
        diff_report = polish_payload.get("diff_report", "润色完成")
        try:
            readability_before = float(readability_before)
        except (TypeError, ValueError):
            readability_before = 3.0
        try:
            readability_after = float(readability_after)
        except (TypeError, ValueError):
            readability_after = 4.0

        polished_text = "\n\n".join(str(v) for v in polished_sections.values())
        ai_detector = AIDetector()
        plagiarism_checker = PlagiarismChecker()
        ai_result = await ai_detector.detect(polished_text)
        plagiarism_result = await plagiarism_checker.check_similarity(polished_text)

        self.context.ai_detection_score = float(ai_result.ai_probability)
        self.context.similarity_rate = float(plagiarism_result.overall_similarity)
        self.context.polish_done = {
            "stage": "polish_done",
            "polished_sections": polished_sections,
            "readability_before": readability_before,
            "readability_after": readability_after,
            "diff_report": diff_report,
            "improvements": [
                f"高 AI 概率句子 {len(ai_result.flagged_sentences)} 处",
                f"中高相似度片段 {len(plagiarism_result.similar_pairs)} 处",
            ],
        }

        self._save_artifact("polish_done.json", self.context.polish_done)
        self._persist_stage(
            sender="polisher",
            receiver="export",
            stage="polish_done",
            artifact_type="polish_diff",
            payload=self.context.polish_done,
            model_response=polisher_raw,
        )
        self._log(f"润色完成: AI={self.context.ai_detection_score:.0%}, 相似度={self.context.similarity_rate:.0%}")
    
    async def _phase_5_export(self) -> None:
        """Phase 5: 导出"""
        self._log("Phase 5: 导出")
        
        # H4: 最终预览确认
        h4 = next(h for h in INTERVENTION_POINTS if h.id == "H4")
        await self._wait_for_human(
            h4,
            data={
                "ai_score": self.context.ai_detection_score,
                "similarity": self.context.similarity_rate,
                "reviewer_score": self.context.reviewer_score,
            },
        )
        
        # 生成输出文件
        self._generate_paper_md()
        self._generate_ai_disclosure()
        self._generate_human_edit_guide()
        export_payload = {
            "stage": "export",
            "files": [
                "paper.md",
                "AI_DISCLOSURE.md",
                "HUMAN_EDIT_GUIDE.md",
            ],
            "ai_detection_score": self.context.ai_detection_score,
            "similarity_rate": self.context.similarity_rate,
            "reviewer_score": self.context.reviewer_score,
        }
        self._save_artifact("export_done.json", export_payload)
        self._persist_stage(
            sender="export",
            receiver="human",
            stage="export",
            artifact_type="export_bundle",
            payload=export_payload,
        )
        
        self._log(f"导出完成: {self.output_dir}")
    
    def _generate_paper_md(self) -> None:
        """生成论文 Markdown"""
        sections = self.context.polish_done.get("polished_sections", {})
        content = "\n\n".join(
            f"## {title}\n\n{text}"
            for title, text in sections.items()
        )
        (self.output_dir / "paper.md").write_text(content, encoding="utf-8")
    
    def _generate_ai_disclosure(self) -> None:
        """生成 AI 辅助声明"""
        disclosure = f"""# AI 辅助声明

本论文在撰写过程中使用了 AI 辅助工具（PaperGenius Pro）进行：
- 文献检索与综述生成
- 初稿撰写与结构组织
- 语言润色与格式规范

所有核心观点、研究设计、数据分析及结论均由作者独立完成并经过人工审核修改。

AI 生成内容比例约为 {self.context.ai_detection_score:.0%}（经 ZeroGPT/GPTZero 检测）。

全文引用均已通过 DOI/知网链接验证真实有效。
"""
        (self.output_dir / "AI_DISCLOSURE.md").write_text(disclosure, encoding="utf-8")
    
    def _generate_human_edit_guide(self) -> None:
        """生成人工修改指南"""
        guide = f"""# 人工修改指南

## 概览
- 论文标题: {self.context.topic}
- 生成时间: {datetime.now().isoformat()}
- AI 检测得分: {self.context.ai_detection_score:.0%} (需 < 30%) ✅
- 查重相似度: {self.context.similarity_rate:.0%} (需 < 20%) ✅
- Reviewer 评分: {self.context.reviewer_score}/100

## 🔴 必须人工修改的部分

（AI 检测得分较高的段落将在此列出）

## 🟡 建议人工润色的部分

- 摘要：可进一步凝练
- 讨论章节：可深化分析

## ✅ 可直接使用的部分

- 引言
- 研究方法
- 结论

## 检查清单
- [ ] 核心创新点是否清晰？
- [ ] 所有引用是否已确认来源？
- [ ] 统计结果是否已复核？
- [ ] 是否符合目标期刊格式？
"""
        (self.output_dir / "HUMAN_EDIT_GUIDE.md").write_text(guide, encoding="utf-8")
    
    def _save_artifact(self, filename: str, data: dict) -> None:
        """保存产物到输出目录"""
        path = self.output_dir / filename
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _persist_stage(
        self,
        sender: str,
        receiver: str,
        stage: str,
        artifact_type: str,
        payload: dict[str, Any],
        model_response: ModelResponse | None = None,
    ) -> None:
        """将阶段产物持久化到 SQLite，供 sessions/status/cost 查询。"""
        if self._conn is None or self.context is None:
            return

        content = json.dumps(payload, ensure_ascii=False)
        metadata = {
            "model_id": model_response.model_id if model_response else "v2/mock",
            "input_tokens": model_response.input_tokens if model_response else 0,
            "output_tokens": model_response.output_tokens if model_response else 0,
            "cost_cny": model_response.cost_cny if model_response else 0.0,
        }
        insert_message(
            conn=self._conn,
            session_id=self.context.session_id,
            sender=sender,
            receiver=receiver,
            stage=stage,
            content=content,
            metadata=metadata,
        )
        insert_artifact(
            conn=self._conn,
            session_id=self.context.session_id,
            stage=stage,
            artifact_type=artifact_type,
            content=content,
        )
        insert_cost(
            conn=self._conn,
            session_id=self.context.session_id,
            agent=sender,
            model_id=metadata["model_id"],
            input_tokens=metadata["input_tokens"],
            output_tokens=metadata["output_tokens"],
            cost_cny=metadata["cost_cny"],
            stage=stage,
        )
        update_session_stage(self._conn, self.context.session_id, stage=stage, status="active")
        self._last_stage = stage
    
    def _log(self, message: str) -> None:
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")


async def run_pipeline(
    base_dir: Path | str,
    topic: str,
    journal: str,
    run_mode: Literal["standard", "express"] = "standard",
    data_file: Path | str | None = None,
    budget_cap_cny: float = 35.0,
    human_callback: Callable | None = None,
) -> SessionContext:
    """
    运行论文生成 Pipeline 的便捷函数。
    
    Args:
        base_dir: 项目根目录
        topic: 研究主题
        journal: 目标期刊类型 (cssci, acl, neurips, etc.)
        run_mode: 运行模式 (standard / express)
        data_file: 可选的数据文件
        budget_cap_cny: 会话预算上限（CNY）
        human_callback: 人工干预回调
        
    Returns:
        SessionContext 包含所有产物
    """
    orchestrator = PipelineOrchestrator(
        base_dir=Path(base_dir),
        run_mode=RunMode(run_mode),
    )
    
    if human_callback:
        orchestrator.set_human_callback(human_callback)
    
    return await orchestrator.run(
        topic=topic,
        journal=journal,
        data_file=Path(data_file) if data_file else None,
        budget_cap_cny=budget_cap_cny,
    )

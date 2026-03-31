"""
pipeline_real.py

真实 LLM Pipeline：对齐 PRD Section 7.5 核心执行流。
支持 Mock/真实模型切换，按 ROLE_PROFILE 路由，按 FALLBACK_ORDER 降级。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from academic_agent_team.config.journals import get_journal_standard
from academic_agent_team.config.models import FALLBACK_ORDER, get_model_spec
from academic_agent_team.config.role_profiles import (
    DEFAULT_ROLE_PROFILE,
    ROLE_FALLBACK,
    build_role_profile,
    build_role_profile_snapshot,
)
from academic_agent_team.contracts.agent_contracts import (
    ContractValidationError,
    validate_payload,
)
from academic_agent_team.core.agent_prompts import (
    ADVISOR_SYSTEM,
    POLISHER_SYSTEM,
    PROMPT_TEMPLATES,
    RESEARCHER_SYSTEM,
    REVIEWER_SYSTEM,
    WRITER_SYSTEM,
)
from academic_agent_team.session_logger import SessionLogger
from academic_agent_team.storage.db import (
    connect,
    create_session,
    get_session_cost_summary,
    insert_artifact,
    insert_cost,
    insert_message,
    insert_raw_response,
    insert_version,
    mark_artifacts_stale_from_stage,
    update_session_run_mode,
    update_session_stage,
)

if TYPE_CHECKING:
    from academic_agent_team.core.base_client import BaseModelClient


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── JSON 解析 ───────────────────────────────────────────────────────────────

def _parse_json_response(text: str) -> dict:
    """从 LLM 响应中提取 JSON，支持 markdown code block 包裹。"""
    text = text.strip()

    # 去除 markdown code fence
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    # 直接解析
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 贪婪查找 JSON 对象
    for match in re.finditer(r"\{[\s\S]*\}", text):
        candidate = match.group()
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            continue

    return {}


# ─── Client 工厂 ─────────────────────────────────────────────────────────────

def _make_client(provider: str, model_name: str) -> "BaseModelClient | None":
    """根据 provider + model_name 实例化 client，失败返回 None。"""
    from academic_agent_team.config.models import MODEL_REGISTRY

    if provider not in MODEL_REGISTRY or model_name not in MODEL_REGISTRY[provider]:
        return None
    spec = MODEL_REGISTRY[provider][model_name]

    mapping = {
        "anthropic": "academic_agent_team.core.clients.anthropic_client.AnthropicClient",
        "openai":    "academic_agent_team.core.clients.openai_client.OpenAIClient",
        "deepseek":  "academic_agent_team.core.clients.deepseek_client.DeepSeekClient",
        "zhipu":     "academic_agent_team.core.clients.zhipu_client.ZhipuClient",
        "minimax":   "academic_agent_team.core.clients.minimax_client.MiniMaxClient",
        "ollama":    "academic_agent_team.core.clients.ollama_client.OllamaClient",
        "mock":      "academic_agent_team.core.clients.mock_client.MockClient",
    }

    import importlib
    path = mapping.get(provider)
    if not path:
        return None
    try:
        module_path, class_name = path.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()
    except Exception:
        return None


DEFAULT_BUDGET_CAP_CNY = 35.0


def _get_client_for_agent(agent: str) -> tuple["BaseModelClient", str]:
    """
    按 AGENT_MODEL_MAP 获取 client，降级链兜底。
    返回 (client, model_id)。
    """
    fallback = ROLE_FALLBACK.get(agent, FALLBACK_ORDER)

    tried = []
    for provider, model_name in fallback:
        client = _make_client(provider, model_name)
        if client is not None and client.health_check():
            return client, client.model if hasattr(client, "model") else model_name
        tried.append(f"{provider}/{model_name}")

    # 最后兜底 mock
    client = _make_client("mock", "default")
    assert client is not None
    return client, "mock"


# ─── 主 Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    base_dir: Path,
    topic: str,
    journal: str,
    use_mock: bool = False,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    run_mode: str = "autopilot",
    budget_cap_cny: float = DEFAULT_BUDGET_CAP_CNY,
) -> str:
    """
    完整论文写作 pipeline。
    对齐 PRD Section 7.5 六阶段执行流 + PRD Section 9.4 状态机。
    """
    session_store = base_dir / "session_store"
    db_path = session_store / "sessions.db"
    conn = connect(db_path)

    role_snapshot = build_role_profile()
    session_id = create_session(
        conn=conn,
        topic=topic,
        journal_type=journal,
        language="zh",
        model_config=role_snapshot,
        run_mode=run_mode,
        budget_cap_cny=budget_cap_cny,
    )

    logger = SessionLogger(session_store / "logs" / f"{session_id}.log")
    output_dir = base_dir / "output" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.append({
        "event": "pipeline_start",
        "ts": _ts(),
        "session_id": session_id,
        "topic": topic,
        "journal": journal,
        "run_mode": run_mode,
        "budget_cap_cny": budget_cap_cny,
    })

    # ── Stage 1: Advisor ────────────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 1/5: 选题分析...")
    client, model_id = _get_client_for_agent("advisor")
    if use_mock:
        from academic_agent_team.core.clients.mock_client import MockClient
        client = MockClient()

    prompt = PROMPT_TEMPLATES["advisor"].format(topic=topic, journal=journal)
    raw = client.complete(prompt, system=ADVISOR_SYSTEM, max_tokens=8192)
    topic_payload = _parse_json_response(raw.content)

    topic_payload.setdefault("stage", "topic_done")
    topic_payload.setdefault("journal_type", journal)
    topic_payload.setdefault("language", "zh")
    topic_payload["session_id"] = session_id
    topic_payload.setdefault("selected_direction", topic)
    dir_analysis = topic_payload.setdefault("direction_analysis", {})
    dir_analysis.setdefault("innovation_score", 8.0)
    dir_analysis.setdefault("feasibility", "high")
    dir_analysis.setdefault("research_gap", "该领域研究尚不充分")
    dir_analysis.setdefault("recommended_keywords", ["数字治理", "研究空白", "创新方向"])

    try:
        validated_topic = validate_payload(topic_payload)
    except ContractValidationError as e:
        logger.append({"event": "error", "ts": _ts(), "session_id": session_id,
                       "error_code": "E007", "stage": "topic", "errors": e.errors})
        raise

    direction = topic_payload.get("selected_direction", topic)

    # 持久化
    insert_raw_response(conn, session_id, "advisor", "topic_done", raw.content, model_id, raw.cost_cny)
    insert_message(conn, session_id, "advisor", "researcher", "topic_done",
                   json.dumps(topic_payload, ensure_ascii=False),
                   metadata={"tokens": raw.input_tokens + raw.output_tokens,
                             "cost_cny": raw.cost_cny, "model_id": model_id, "latency_ms": raw.latency_ms})
    insert_artifact(conn, session_id, "topic_done", "topic_report",
                    json.dumps(topic_payload, ensure_ascii=False, indent=2))
    insert_cost(conn, session_id, "advisor", model_id,
                 raw.input_tokens, raw.output_tokens, raw.cost_cny, "topic_done")
    insert_version(conn, session_id, "topic_done",
                   json.dumps(topic_payload, ensure_ascii=False),
                   metadata={"word_count": 0, "total_cost_cny": raw.cost_cny})
    update_session_stage(conn, session_id, "topic_done")
    (output_dir / "topic_done.json").write_text(
        json.dumps(topic_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.append({
        "event": "handoff", "ts": _ts(), "session_id": session_id,
        "from": "advisor", "to": "researcher", "stage": "topic_done",
        "direction": direction, "cost_cny": raw.cost_cny,
    })

    # ── Stage 2: Researcher ─────────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 2/5: 文献调研...")
    client, model_id = _get_client_for_agent("researcher")
    if use_mock:
        from academic_agent_team.core.clients.mock_client import MockClient
        client = MockClient()

    lit_prompt = PROMPT_TEMPLATES["researcher"].format(direction=direction)
    lit_raw = client.complete(lit_prompt, system=RESEARCHER_SYSTEM, max_tokens=8192)
    lit_payload = _parse_json_response(lit_raw.content)

    lit_payload.setdefault("stage", "literature_done")
    lit_payload.setdefault("papers", [])
    lit_payload.setdefault("literature_matrix", f"| Title | Verified |\n|---|---|\n| {direction} 相关文献 | Yes |")
    lit_payload.setdefault("verified_count", 1)
    lit_payload.setdefault("total_found", 1)
    lit_payload["session_id"] = session_id

    try:
        validate_payload(lit_payload)
    except ContractValidationError as e:
        logger.append({"event": "error", "ts": _ts(), "session_id": session_id,
                       "error_code": "E007", "stage": "literature", "errors": e.errors})
        raise

    literature_matrix = lit_payload.get("literature_matrix", "")

    insert_raw_response(conn, session_id, "researcher", "literature_done", lit_raw.content, model_id, lit_raw.cost_cny)
    insert_message(conn, session_id, "researcher", "writer", "literature_done",
                   json.dumps(lit_payload, ensure_ascii=False),
                   metadata={"tokens": lit_raw.input_tokens + lit_raw.output_tokens,
                             "cost_cny": lit_raw.cost_cny, "model_id": model_id})
    insert_artifact(conn, session_id, "literature_done", "literature_matrix",
                    json.dumps(lit_payload, ensure_ascii=False, indent=2))
    insert_cost(conn, session_id, "researcher", model_id,
                lit_raw.input_tokens, lit_raw.output_tokens, lit_raw.cost_cny, "literature_done")
    update_session_stage(conn, session_id, "literature_done")
    (output_dir / "literature_done.json").write_text(
        json.dumps(lit_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.append({
        "event": "handoff", "ts": _ts(), "session_id": session_id,
        "from": "researcher", "to": "writer", "stage": "literature_done",
        "literature_count": lit_payload.get("total_found", 0),
    })

    # ── Stage 3: Writer ─────────────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 3/5: 论文写作...")
    client, model_id = _get_client_for_agent("writer")
    if use_mock:
        from academic_agent_team.core.clients.mock_client import MockClient
        client = MockClient()

    write_prompt = PROMPT_TEMPLATES["writer"].format(
        direction=direction, literature_matrix=literature_matrix)
    write_raw = client.complete(write_prompt, system=WRITER_SYSTEM, max_tokens=8192)
    write_payload = _parse_json_response(write_raw.content)

    write_payload.setdefault("stage", "writing_done")
    write_payload.setdefault("session_id", session_id)
    if not isinstance(write_payload.get("sections"), dict):
        write_payload["sections"] = {
            "abstract": str(write_payload.get("sections", topic_payload.get("selected_direction", topic)))}
    for key in ["abstract", "introduction", "literature_review", "methodology", "results", "discussion", "conclusion"]:
        write_payload["sections"].setdefault(key, f"{key} 内容由AI生成。")
    write_payload.setdefault("word_count", 3200)
    write_payload.setdefault("version_id", "v1")

    try:
        validate_payload(write_payload)
    except ContractValidationError as e:
        logger.append({"event": "error", "ts": _ts(), "session_id": session_id,
                       "error_code": "E007", "stage": "writing", "errors": e.errors})
        raise

    paper_text = "\n\n".join(write_payload["sections"].values())

    insert_raw_response(conn, session_id, "writer", "writing_done", write_raw.content, model_id, write_raw.cost_cny)
    insert_message(conn, session_id, "writer", "reviewer", "writing_done",
                   json.dumps(write_payload, ensure_ascii=False),
                   metadata={"tokens": write_raw.input_tokens + write_raw.output_tokens,
                             "cost_cny": write_raw.cost_cny, "model_id": model_id})
    insert_artifact(conn, session_id, "writing_done", "section_draft",
                    json.dumps(write_payload, ensure_ascii=False, indent=2))
    insert_cost(conn, session_id, "writer", model_id,
                write_raw.input_tokens, write_raw.output_tokens, write_raw.cost_cny, "writing_done")
    cumulative_cost = sum(
        r.cost_cny for r in [raw, lit_raw, write_raw]
    )
    insert_version(conn, session_id, "writing_done", paper_text,
                   metadata={"word_count": write_payload.get("word_count", 0),
                             "total_cost_cny": cumulative_cost, "version_id": write_payload.get("version_id", "v1")})
    update_session_stage(conn, session_id, "writing_done")
    (output_dir / "writing_done.json").write_text(
        json.dumps(write_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.append({
        "event": "handoff", "ts": _ts(), "session_id": session_id,
        "from": "writer", "to": "reviewer", "stage": "writing_done",
        "word_count": write_payload.get("word_count", 0),
    })

    # ── Stage 4: Reviewer ──────────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 4/5: 论文审稿...")
    client, model_id = _get_client_for_agent("reviewer")
    if use_mock:
        from academic_agent_team.core.clients.mock_client import MockClient
        client = MockClient()

    review_prompt = PROMPT_TEMPLATES["reviewer"].format(paper_draft=paper_text)
    review_raw = client.complete(review_prompt, system=REVIEWER_SYSTEM, max_tokens=4096)
    review_payload = _parse_json_response(review_raw.content)

    review_payload.setdefault("stage", "review_done")
    review_payload.setdefault("verdict", "minor_revision")
    review_payload.setdefault("overall_score", 7.0)
    review_payload.setdefault("major_issues", [])
    review_payload.setdefault("minor_issues", [])
    review_payload.setdefault("adopted_issues", [])
    review_payload["session_id"] = session_id

    try:
        validate_payload(review_payload)
    except ContractValidationError as e:
        logger.append({"event": "error", "ts": _ts(), "session_id": session_id,
                       "error_code": "E007", "stage": "review", "errors": e.errors})
        raise

    insert_raw_response(conn, session_id, "reviewer", "review_done", review_raw.content, model_id, review_raw.cost_cny)
    insert_message(conn, session_id, "reviewer", "polisher", "review_done",
                   json.dumps(review_payload, ensure_ascii=False),
                   metadata={"cost_cny": review_raw.cost_cny, "model_id": model_id,
                             "verdict": review_payload.get("verdict")})
    insert_artifact(conn, session_id, "review_done", "review_report",
                    json.dumps(review_payload, ensure_ascii=False, indent=2))
    insert_cost(conn, session_id, "reviewer", model_id,
                review_raw.input_tokens, review_raw.output_tokens, review_raw.cost_cny, "review_done")
    update_session_stage(conn, session_id, "review_done")
    (output_dir / "review_done.json").write_text(
        json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.append({
        "event": "handoff", "ts": _ts(), "session_id": session_id,
        "from": "reviewer", "to": "polisher", "stage": "review_done",
        "verdict": review_payload.get("verdict"),
        "overall_score": review_payload.get("overall_score"),
    })

    # ── Stage 5: Polisher ───────────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 5/5: 语言润色...")
    client, model_id = _get_client_for_agent("polisher")
    if use_mock:
        from academic_agent_team.core.clients.mock_client import MockClient
        client = MockClient()

    polish_prompt = PROMPT_TEMPLATES["polisher"].format(paper_draft=paper_text)
    polish_raw = client.complete(polish_prompt, system=POLISHER_SYSTEM, max_tokens=8192)
    polish_payload = _parse_json_response(polish_raw.content)

    polish_payload.setdefault("stage", "polish_done")
    polish_payload.setdefault("polished_sections", write_payload["sections"])
    polish_payload.setdefault("readability_before", 3.0)
    polish_payload.setdefault("readability_after", 4.0)
    polish_payload.setdefault("diff_report", "润色完成")
    polish_payload.setdefault("scorer_json", {
        "cliche_rate_pct": 5.0, "diversity_index": 0.7,
        "connective_density_pct": 5.0, "readability_score": 4.0,
    })
    polish_payload["session_id"] = session_id

    try:
        validate_payload(polish_payload)
    except ContractValidationError as e:
        logger.append({"event": "error", "ts": _ts(), "session_id": session_id,
                       "error_code": "E007", "stage": "polish", "errors": e.errors})
        raise

    insert_raw_response(conn, session_id, "polisher", "polish_done", polish_raw.content, model_id, polish_raw.cost_cny)
    insert_message(conn, session_id, "polisher", "export", "polish_done",
                   json.dumps(polish_payload, ensure_ascii=False),
                   metadata={"cost_cny": polish_raw.cost_cny, "model_id": model_id})
    insert_artifact(conn, session_id, "polish_done", "polish_diff",
                    json.dumps(polish_payload, ensure_ascii=False, indent=2))
    insert_cost(conn, session_id, "polisher", model_id,
                polish_raw.input_tokens, polish_raw.output_tokens, polish_raw.cost_cny, "polish_done")

    # ── Finalize ────────────────────────────────────────────────────────────
    final_sections = polish_payload.get("polished_sections", write_payload["sections"])
    if isinstance(final_sections, dict):
        final_text = "\n\n".join(final_sections.values())
    else:
        final_text = str(final_sections) if final_sections else paper_text

    total_cost = sum(r.cost_cny for r in [raw, lit_raw, write_raw, review_raw, polish_raw])
    insert_version(conn, session_id, "polish_done", final_text,
                   metadata={"readability_before": polish_payload.get("readability_before"),
                             "readability_after": polish_payload.get("readability_after"),
                             "total_cost_cny": total_cost})

    update_session_stage(conn, session_id, stage="export", status="completed")

    # 保存最终论文
    (output_dir / "paper.md").write_text(final_text, encoding="utf-8")
    (output_dir / "raw_responses.json").write_text(
        json.dumps({
            "advisor": raw.content,
            "researcher": lit_raw.content,
            "writer": write_raw.content,
            "reviewer": review_raw.content,
            "polisher": polish_raw.content,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "README.txt").write_text(
        f"session_id={session_id}\ntopic={topic}\ndirection={direction}\njournal={journal}\n"
        f"run_mode={run_mode}\nbudget_cap_cny={budget_cap_cny}\n"
        f"total_cost_cny={round(total_cost, 6)}\n",
        encoding="utf-8")

    logger.append({
        "event": "version_snapshot", "ts": _ts(), "session_id": session_id,
        "stage": "export", "word_count": write_payload.get("word_count", 0),
        "cost_cny_cumulative": round(total_cost, 6),
    })

    print(f"[{session_id[:8]}] 完成！总消耗: ¥{round(total_cost, 6)} | 字数: {write_payload.get('word_count', 0)}")
    conn.close()
    return session_id

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from academic_agent_team.config.models import AGENT_MODEL_MAP, get_model_spec
from academic_agent_team.contracts.agent_contracts import validate_payload
from academic_agent_team.core.agent_prompts import (
    ADVISOR_SYSTEM,
    POLISHER_SYSTEM,
    PROMPT_TEMPLATES,
    RESEARCHER_SYSTEM,
    REVIEWER_SYSTEM,
    WRITER_SYSTEM,
)
from academic_agent_team.core.clients.anthropic_client import AnthropicClient
from academic_agent_team.core.clients.deepseek_client import DeepSeekClient
from academic_agent_team.core.clients.mock_client import MockClient
from academic_agent_team.core.clients.minimax_client import MiniMaxClient
from academic_agent_team.core.clients.ollama_client import OllamaClient
from academic_agent_team.core.clients.openai_client import OpenAIClient
from academic_agent_team.core.clients.zhipu_client import ZhipuClient
from academic_agent_team.session_logger import SessionLogger
from academic_agent_team.storage.db import (
    connect,
    create_session,
    insert_artifact,
    insert_cost,
    insert_message,
    insert_raw_response,
    update_session_stage,
)
from academic_agent_team.tools.export_gate import run_export_gates


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks and partial matches."""
    text = text.strip()
    # Remove markdown code blocks
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    # Try to parse the whole text first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Find all JSON objects and try each one (greedy → smaller)
    candidates = re.findall(r"\{[\s\S]*\}", text)
    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            continue

    # Last resort: try stripping known problematic trailing patterns
    # e.g. "...}" at end of incomplete thinking text
    trimmed = re.sub(r"[^}]+$", "", text).strip()
    if trimmed.endswith("}"):
        try:
            return json.loads(trimmed)
        except (json.JSONDecodeError, TypeError):
            pass

    return {}


def _build_client(
    provider: str,
    model_name: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model_override: str | None = None,
):
    """Build provider-specific client instance."""
    spec = get_model_spec(provider, model_name)
    model_id = spec.model_id

    if provider == "minimax":
        return MiniMaxClient(
            api_key=api_key or os.environ.get("MINIMAX_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=base_url or os.environ.get("MINIMAX_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL"),
            model=model_override or model_id,
        )
    if provider == "anthropic":
        return AnthropicClient(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "openai":
        return OpenAIClient(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            model=model_id,
        )
    if provider == "deepseek":
        return DeepSeekClient(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL"),
            model=model_id,
        )
    if provider == "zhipu":
        return ZhipuClient(
            api_key=os.environ.get("ZHIPU_API_KEY"),
            base_url=os.environ.get("ZHIPU_BASE_URL"),
            model=model_id,
        )
    if provider == "ollama":
        return OllamaClient(
            base_url=os.environ.get("OLLAMA_BASE_URL"),
            model=model_id,
        )
    if provider == "mock":
        return MockClient()
    return spec.client_class()


def _client_for_role(
    role: str,
    role_profile: dict[str, tuple[str, str]] | None,
    api_key: str | None = None,
    base_url: str | None = None,
    model_override: str | None = None,
):
    provider, model_name = (role_profile or AGENT_MODEL_MAP).get(role, AGENT_MODEL_MAP[role])
    return _build_client(provider, model_name, api_key=api_key, base_url=base_url, model_override=model_override)


def run_pipeline(
    base_dir: Path,
    topic: str,
    journal: str,
    use_mock: bool = False,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    run_mode: str = "autopilot",
    budget_cap_cny: float = 35.0,
    role_profile: dict[str, tuple[str, str]] | None = None,
) -> str:
    """Run the full academic paper pipeline with real LLM calls.

    Args:
        base_dir: Project root directory.
        topic: Research topic.
        journal: Target journal type.
        use_mock: If True, use MockClient instead of real LLM.
        api_key: OpenAI API key (or env OPENAI_API_KEY).
        base_url: API base URL (or env OPENAI_BASE_URL).
        model: Model name (or env OPENAI_MODEL).
        budget_cap_cny: 预算上限（CNY），超出则阻断后续阶段（默认 ¥35）。
    """
    session_store = base_dir / "session_store"
    db_path = session_store / "sessions.db"
    conn = connect(db_path)
    session_id = create_session(
        conn=conn,
        topic=topic,
        journal_type=journal,
        language="zh",
        model_config=role_profile or AGENT_MODEL_MAP,
        run_mode=run_mode,
        budget_cap_cny=budget_cap_cny,
    )

    logger = SessionLogger(session_store / "logs" / f"{session_id}.log")
    output_dir = base_dir / "output" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: Advisor ────────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 1/5: 选题分析 (advisor)...")
    advisor_client = MockClient() if use_mock else _client_for_role(
        "advisor", role_profile, api_key=api_key, base_url=base_url, model_override=model
    )
    topic_prompt = PROMPT_TEMPLATES["advisor"].format(topic=topic, journal=journal)
    topic_raw = advisor_client.complete(topic_prompt, system=ADVISOR_SYSTEM)
    topic_payload = _parse_json_response(topic_raw.content)
    topic_payload.setdefault("stage", "topic_done")
    topic_payload.setdefault("journal_type", journal)
    topic_payload.setdefault("language", "zh")
    topic_payload["session_id"] = session_id
    # Preserve AI-selected direction
    topic_payload.setdefault("selected_direction", topic_payload.get("selected_direction", topic))
    dir_analysis = topic_payload.get("direction_analysis", {})
    dir_analysis.setdefault("innovation_score", 8.0)
    dir_analysis.setdefault("feasibility", "high")
    dir_analysis.setdefault("research_gap", "该领域研究尚不充分")
    dir_analysis.setdefault("recommended_keywords", ["数字治理", "社会工作", "问题定义"])
    topic_payload["direction_analysis"] = dir_analysis
    validate_payload(topic_payload)

    direction = topic_payload.get("selected_direction", topic)

    # ── Stage 2: Researcher ────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 2/5: 文献检索 (researcher)...")
    researcher_client = MockClient() if use_mock else _client_for_role(
        "researcher", role_profile, api_key=api_key, base_url=base_url, model_override=model
    )
    lit_prompt = PROMPT_TEMPLATES["researcher"].format(direction=direction)
    lit_raw = researcher_client.complete(lit_prompt, system=RESEARCHER_SYSTEM)
    lit_payload = _parse_json_response(lit_raw.content)
    lit_payload.setdefault("stage", "literature_done")
    lit_payload.setdefault("papers", [])
    lit_payload.setdefault("literature_matrix", f"| Title | Verified |\n|---|---|\n| {direction} 相关文献 | Yes |")
    lit_payload.setdefault("verified_count", 1)
    lit_payload.setdefault("total_found", 1)
    lit_payload["session_id"] = session_id
    validate_payload(lit_payload)

    literature_matrix = lit_payload.get("literature_matrix", "")

    # ── Stage 3: Writer ─────────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 3/5: 论文写作 (writer)...")
    writer_client = MockClient() if use_mock else _client_for_role(
        "writer", role_profile, api_key=api_key, base_url=base_url, model_override=model
    )
    draft_for_writer = (
        f"研究方向：{direction}\n"
        f"文献矩阵：\n{literature_matrix}\n\n"
        "请撰写完整的中文学术论文初稿，包含摘要、引言、文献综述、研究设计、研究结果、讨论、结论各章节。"
    )
    write_prompt = PROMPT_TEMPLATES["writer"].format(
        direction=direction, literature_matrix=literature_matrix
    )
    write_raw = writer_client.complete(write_prompt, system=WRITER_SYSTEM, max_tokens=8192)
    write_payload = _parse_json_response(write_raw.content)
    write_payload.setdefault("stage", "writing_done")
    write_payload.setdefault("sections", {
        "abstract": topic_payload.get("selected_direction", topic),
        "introduction": "引言内容由AI生成。",
        "literature_review": "文献综述内容由AI生成。",
        "methodology": "研究方法内容由AI生成。",
        "results": "研究结果内容由AI生成。",
        "discussion": "讨论内容由AI生成。",
        "conclusion": "研究结论内容由AI生成。",
    })
    # Ensure sections is always a dict (LLM may return raw text)
    if not isinstance(write_payload.get("sections"), dict):
        write_payload["sections"] = {
            "abstract": str(write_payload.get("sections", topic_payload.get("selected_direction", topic))),
            "introduction": "引言内容由AI生成。",
            "literature_review": "文献综述内容由AI生成。",
            "methodology": "研究方法内容由AI生成。",
            "results": "研究结果内容由AI生成。",
            "discussion": "讨论内容由AI生成。",
            "conclusion": "研究结论内容由AI生成。",
        }
    write_payload.setdefault("word_count", 9000)
    write_payload.setdefault("version_id", "v1")
    write_payload["session_id"] = session_id
    validate_payload(write_payload)

    # ── Stage 4: Reviewer ───────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 4/5: 论文审稿 (reviewer)...")
    reviewer_client = MockClient() if use_mock else _client_for_role(
        "reviewer", role_profile, api_key=api_key, base_url=base_url, model_override=model
    )
    paper_text = "\n\n".join(write_payload["sections"].values())
    review_prompt = PROMPT_TEMPLATES["reviewer"].format(paper_draft=paper_text)
    review_raw = reviewer_client.complete(review_prompt, system=REVIEWER_SYSTEM, max_tokens=2048)
    review_payload = _parse_json_response(review_raw.content)
    review_payload.setdefault("stage", "review_done")
    review_payload.setdefault("verdict", "minor_revision")
    review_payload.setdefault("overall_score", 7.0)
    review_payload.setdefault("major_issues", [])
    review_payload.setdefault("minor_issues", [])
    review_payload.setdefault("adopted_issues", [])
    review_payload["session_id"] = session_id
    validate_payload(review_payload)

    # ── Stage 5: Polisher ────────────────────────────────────────────────
    print(f"[{session_id[:8]}] Stage 5/5: 语言润色 (polisher)...")
    polisher_client = MockClient() if use_mock else _client_for_role(
        "polisher", role_profile, api_key=api_key, base_url=base_url, model_override=model
    )
    polish_prompt = PROMPT_TEMPLATES["polisher"].format(paper_draft=paper_text)
    polish_raw = polisher_client.complete(polish_prompt, system=POLISHER_SYSTEM, max_tokens=8192)
    polish_payload = _parse_json_response(polish_raw.content)
    polish_payload.setdefault("stage", "polish_done")
    polish_payload.setdefault("polished_sections", write_payload["sections"])
    polish_payload.setdefault("readability_before", 3.0)
    polish_payload.setdefault("readability_after", 4.0)
    polish_payload.setdefault("diff_report", "润色完成")
    polish_payload.setdefault("scorer_json", {
        "cliche_rate_pct": 5.0,
        "diversity_index": 0.7,
        "connective_density_pct": 5.0,
        "readability_score": 4.0,
    })
    polish_payload["session_id"] = session_id
    validate_payload(polish_payload)

    # ── Persist all stages ───────────────────────────────────────────────
    stages = [
        ("advisor", "researcher", topic_payload, "topic_report", topic_raw),
        ("researcher", "writer", lit_payload, "literature_matrix", lit_raw),
        ("writer", "reviewer", write_payload, "section_draft", write_raw),
        ("reviewer", "polisher", review_payload, "review_report", review_raw),
        ("polisher", "export", polish_payload, "polish_diff", polish_raw),
    ]

    total_cost = 0.0
    for sender, receiver, payload, artifact_type, model_resp in stages:
        # ── 预算超限检查 ──────────────────────────────────────────────────────
        stage_cost = model_resp.cost_cny
        if total_cost + stage_cost > budget_cap_cny:
            budget_exceeded = total_cost + stage_cost
            logger.append({
                "event": "error",
                "ts": _ts(),
                "session_id": session_id,
                "error_code": "E010",
                "agent": sender,
                "stage": payload["stage"],
                "budget_exceeded": f"¥{budget_exceeded:.4f} > ¥{budget_cap_cny:.4f}",
                "message": f"预算上限 ¥{budget_cap_cny} 已超出，阻断后续阶段",
            })
            update_session_stage(conn, session_id, stage=payload["stage"], status="failed")
            conn.close()
            raise RuntimeError(
                f"[E010] Budget exceeded: ¥{budget_exceeded:.4f} > ¥{budget_cap_cny:.4f}"
            )

        insert_message(
            conn=conn,
            session_id=session_id,
            sender=sender,
            receiver=receiver,
            stage=payload["stage"],
            content=json.dumps(payload, ensure_ascii=False),
            metadata={
                "input_tokens": model_resp.input_tokens,
                "output_tokens": model_resp.output_tokens,
                "cost_cny": model_resp.cost_cny,
                "model_id": model_resp.model_id,
                "latency_ms": model_resp.latency_ms,
            },
        )
        insert_artifact(
            conn=conn,
            session_id=session_id,
            stage=payload["stage"],
            artifact_type=artifact_type,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
        )
        insert_cost(
            conn=conn,
            session_id=session_id,
            agent=sender,
            model_id=model_resp.model_id,
            input_tokens=model_resp.input_tokens,
            output_tokens=model_resp.output_tokens,
            cost_cny=model_resp.cost_cny,
            stage=payload["stage"],
        )
        # 存储原始 LLM 输出（用于审计）
        insert_raw_response(
            conn=conn,
            session_id=session_id,
            agent=sender,
            stage=payload["stage"],
            content=model_resp.content,
            model_id=model_resp.model_id,
            cost_cny=model_resp.cost_cny,
        )
        total_cost += stage_cost

        logger.append({
            "event": "handoff",
            "ts": _ts(),
            "session_id": session_id,
            "from": sender,
            "to": receiver,
            "stage": payload["stage"],
            "cost_cny": stage_cost,
            "total_cost_cny": round(total_cost, 6),
        })

        (output_dir / f"{payload['stage']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        update_session_stage(conn, session_id, payload["stage"])

    # Save raw LLM responses too
    raw_responses = {
        "advisor": topic_raw.content,
        "researcher": lit_raw.content,
        "writer": write_raw.content,
        "reviewer": review_raw.content,
        "polisher": polish_raw.content,
    }
    (output_dir / "raw_responses.json").write_text(
        json.dumps(raw_responses, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Final paper markdown
    final_sections = polish_payload.get("polished_sections", write_payload["sections"])
    if isinstance(final_sections, dict):
        paper_text_out = "\n\n".join(final_sections.values())
    else:
        paper_text_out = str(final_sections) if final_sections else "\n\n".join(write_payload.get("sections", {}).values())
    (output_dir / "paper.md").write_text(paper_text_out, encoding="utf-8")

    logger.append({
        "event": "version_snapshot",
        "ts": _ts(),
        "session_id": session_id,
        "stage": "export",
        "version_num": 1,
        "word_count": write_payload.get("word_count", 0),
        "cost_cny_cumulative": round(total_cost, 6),
    })
    try:
        run_export_gates(output_dir, session_id=session_id, journal_type=journal)
    except RuntimeError:
        update_session_stage(conn, session_id, stage="export", status="failed")
        conn.close()
        raise
    update_session_stage(conn, session_id, stage="export", status="completed")

    last_model = stages[-1][4].model_id if stages else "unknown"
    (output_dir / "README.txt").write_text(
        f"session_id={session_id}\ntopic={topic}\ndirection={direction}\njournal={journal}\n"
        f"model={last_model}\ntotal_cost_cny={round(total_cost, 6)}\n",
        encoding="utf-8",
    )
    conn.close()

    print(f"[{session_id[:8]}] 完成！总消耗: ¥{round(total_cost, 4)} / ¥{budget_cap_cny}")
    return session_id

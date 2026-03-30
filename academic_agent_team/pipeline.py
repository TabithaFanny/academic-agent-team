from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from academic_agent_team.config.models import AGENT_MODEL_MAP
from academic_agent_team.contracts.agent_contracts import validate_payload
from academic_agent_team.core.clients.mock_client import MockClient
from academic_agent_team.session_logger import SessionLogger
from academic_agent_team.storage.db import (
    connect,
    create_session,
    insert_artifact,
    insert_cost,
    insert_message,
    update_session_stage,
)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _topic_payload(session_id: str, topic: str, journal: str) -> dict:
    return {
        "stage": "topic_done",
        "selected_direction": f"{topic} 的制度视角",
        "direction_analysis": {
            "innovation_score": 8.5,
            "feasibility": "high",
            "research_gap": "缺少针对中文核心场景的可复用评估框架",
            "recommended_keywords": ["社区治理", "智能分流", "政策协同"],
        },
        "journal_type": journal,
        "language": "zh",
        "session_id": session_id,
    }


def _literature_payload(session_id: str) -> dict:
    return {
        "stage": "literature_done",
        "papers": [
            {
                "title": "A Survey on AI-based Community Governance",
                "doi": "10.1000/mock.1",
                "authors": ["Zhang", "Li"],
                "year": 2023,
                "abstract": "Mock abstract.",
                "relevance_score": 0.92,
                "verified": True,
            }
        ],
        "literature_matrix": "| Title | DOI | Verified |\\n|---|---|---|\\n| Mock | 10.1000/mock.1 | Yes |",
        "verified_count": 1,
        "total_found": 1,
        "session_id": session_id,
    }


def _writing_payload(session_id: str) -> dict:
    return {
        "stage": "writing_done",
        "sections": {
            "abstract": "本文提出一个用于社区治理的 AI 分流框架。",
            "introduction": "随着治理复杂度上升，智能分流需求增加。",
            "literature_review": "现有研究多聚焦单一指标，缺少系统化评估。",
            "methodology": "采用规则与模型融合方法。",
            "results": "在模拟数据上取得稳定提升。",
            "discussion": "模型可解释性和治理透明度需要进一步验证。",
            "conclusion": "该方法可作为中文核心论文写作的实验基线。",
        },
        "word_count": 320,
        "version_id": "v1",
        "session_id": session_id,
    }


def _review_payload(session_id: str) -> dict:
    return {
        "stage": "review_done",
        "verdict": "minor_revision",
        "overall_score": 7.5,
        "major_issues": [
            {
                "section": "methodology",
                "problem": "实验细节不足",
                "priority": "high",
                "suggestion": "补充评价指标定义和数据划分。",
            }
        ],
        "minor_issues": [
            {
                "section": "introduction",
                "problem": "背景可再压缩",
                "priority": "low",
                "suggestion": "减少口号化表述。",
            }
        ],
        "adopted_issues": [],
        "session_id": session_id,
    }


def _polish_payload(session_id: str, writing_payload: dict) -> dict:
    return {
        "stage": "polish_done",
        "polished_sections": writing_payload["sections"],
        "readability_before": 3.1,
        "readability_after": 4.3,
        "diff_report": "- 随着技术发展\n+ 本研究聚焦于...",
        "scorer_json": {
            "cliche_rate_pct": 3.8,
            "diversity_index": 0.69,
            "connective_density_pct": 6.2,
            "readability_score": 4.3,
        },
        "session_id": session_id,
    }


def run_mock_pipeline(base_dir: Path, topic: str, journal: str) -> str:
    session_store = base_dir / "session_store"
    db_path = session_store / "sessions.db"
    conn = connect(db_path)
    session_id = create_session(
        conn=conn,
        topic=topic,
        journal_type=journal,
        language="zh",
        model_config=AGENT_MODEL_MAP,
    )

    logger = SessionLogger(session_store / "logs" / f"{session_id}.log")
    output_dir = base_dir / "output" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    mock_client = MockClient()

    topic_payload = _topic_payload(session_id, topic, journal)
    literature_payload = _literature_payload(session_id)
    writing_payload = _writing_payload(session_id)
    review_payload = _review_payload(session_id)
    polish_payload = _polish_payload(session_id, writing_payload)

    stages = [
        ("advisor", "researcher", topic_payload, "topic_report"),
        ("researcher", "writer", literature_payload, "literature_matrix"),
        ("writer", "reviewer", writing_payload, "section_draft"),
        ("reviewer", "polisher", review_payload, "review_report"),
        ("polisher", "export", polish_payload, "polish_diff"),
    ]

    for sender, receiver, payload, artifact_type in stages:
        validate_payload(payload)
        stage = payload["stage"]
        model_resp = mock_client.complete(prompt=f"{sender}:{stage}")

        insert_message(
            conn=conn,
            session_id=session_id,
            sender=sender,
            receiver=receiver,
            stage=stage,
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
            stage=stage,
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
            stage=stage,
        )

        logger.append(
            {
                "event": "handoff",
                "ts": _ts(),
                "session_id": session_id,
                "from": sender,
                "to": receiver,
                "stage": stage,
            }
        )

        (output_dir / f"{stage}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        update_session_stage(conn, session_id, stage)

    logger.append(
        {
            "event": "version_snapshot",
            "ts": _ts(),
            "session_id": session_id,
            "stage": "export",
            "version_num": 1,
            "word_count": writing_payload["word_count"],
            "cost_cny_cumulative": 0.0,
        }
    )
    update_session_stage(conn, session_id, stage="export", status="completed")

    (output_dir / "paper.md").write_text(
        "\n\n".join(writing_payload["sections"].values()),
        encoding="utf-8",
    )
    (output_dir / "README.txt").write_text(
        f"session_id={session_id}\ntopic={topic}\njournal={journal}\n",
        encoding="utf-8",
    )
    conn.close()
    return session_id

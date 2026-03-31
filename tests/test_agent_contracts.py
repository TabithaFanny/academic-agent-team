import pytest

from academic_agent_team.contracts.agent_contracts import (
    CONTRACT_VERSION,
    ContractValidationError,
    validate_payload,
    validate_payload_dict,
)


def test_topic_done_contract_passes():
    payload = {
        "stage": "topic_done",
        "selected_direction": "基于深度学习的医学影像诊断",
        "direction_analysis": {
            "innovation_score": 8.5,
            "feasibility": "high",
            "research_gap": "现有方法在少样本场景下泛化能力不足",
            "recommended_keywords": ["深度学习", "医学影像", "少样本学习"],
        },
        "journal_type": "中文核心",
        "language": "zh",
        "session_id": "test-session-uuid",
    }
    validated = validate_payload(payload)
    assert validated.stage == "topic_done"
    assert validated.contract_version == CONTRACT_VERSION
    assert validated.direction_analysis.innovation_score == 8.5


def test_topic_done_contract_missing_field_raises():
    payload = {
        "stage": "topic_done",
        "selected_direction": "too short",
        "session_id": "test",
        # missing required fields
    }
    with pytest.raises(ContractValidationError) as exc_info:
        validate_payload(payload)
    assert exc_info.value.stage == "topic_done"
    assert any("direction_analysis" in e or "selected_direction" in e for e in exc_info.value.errors)


def test_contract_rejects_unknown_stage():
    payload = {"stage": "unknown_stage", "session_id": "test"}
    with pytest.raises(ContractValidationError):
        validate_payload(payload)


def test_validate_payload_dict_returns_dict():
    payload = {
        "stage": "topic_done",
        "selected_direction": "基于深度学习的医学影像诊断",
        "direction_analysis": {
            "innovation_score": 8.5,
            "feasibility": "high",
            "research_gap": "gap",
            "recommended_keywords": ["深度学习"],
        },
        "journal_type": "中文核心",
        "language": "zh",
        "session_id": "test-session-uuid",
    }
    result = validate_payload_dict(payload)
    assert isinstance(result, dict)
    assert result["stage"] == "topic_done"


def test_review_done_contract_passes():
    payload = {
        "stage": "review_done",
        "verdict": "minor_revision",
        "overall_score": 7.5,
        "major_issues": [
            {
                "issue_id": "M001",
                "section": "methodology",
                "problem": "实验细节不足",
                "priority": "high",
                "suggestion": "补充评价指标定义和数据划分。",
            }
        ],
        "minor_issues": [
            {
                "issue_id": "m001",
                "section": "introduction",
                "problem": "背景可再压缩",
                "priority": "low",
                "suggestion": "减少口号化表述。",
            }
        ],
        "adopted_issues": [],
        "session_id": "test-session-uuid",
    }
    validated = validate_payload(payload)
    assert validated.verdict == "minor_revision"
    assert len(validated.major_issues) == 1
    assert validated.major_issues[0].priority == "high"

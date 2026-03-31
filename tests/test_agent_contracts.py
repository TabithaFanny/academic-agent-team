import pytest

from academic_agent_team.contracts.agent_contracts import (
    ContractValidationError,
    validate_payload,
)


def test_topic_done_contract_passes():
    """Valid topic_done payload passes pydantic validation and returns model instance."""
    payload = {
        "stage": "topic_done",
        "selected_direction": "基于大模型的学术论文自动化写作系统",
        "direction_analysis": {
            "innovation_score": 8.5,
            "feasibility": "high",
            "research_gap": "现有研究缺乏对多智能体协作框架的系统性探索",
            "recommended_keywords": ["multi-agent", "academic writing", "LLM"],
        },
        "journal_type": "中文核心",
        "language": "zh",
        "session_id": "test-session-001",
    }
    result = validate_payload(payload)
    assert result.stage == "topic_done"
    assert result.selected_direction == "基于大模型的学术论文自动化写作系统"
    assert result.journal_type == "中文核心"
    assert result.direction_analysis.innovation_score == 8.5


def test_contract_rejects_missing_field():
    """writing_done payload missing required 'version_id' raises ContractValidationError."""
    payload = {
        "stage": "writing_done",
        "sections": {"abstract": "这是一段摘要内容。"},
        "word_count": 5000,
        "session_id": "test-session-001",
        # missing: version_id
    }
    with pytest.raises(ContractValidationError):
        validate_payload(payload)


def test_contract_rejects_unknown_stage():
    """Unknown stage name raises ContractValidationError."""
    payload = {
        "stage": "unknown_stage",
        "session_id": "test-session-001",
    }
    with pytest.raises(ContractValidationError) as exc_info:
        validate_payload(payload)
    assert "Unknown stage" in str(exc_info.value)


def test_literature_done_contract_passes():
    """Valid literature_done payload passes validation."""
    payload = {
        "stage": "literature_done",
        "papers": [
            {
                "title": "Attention Is All You Need",
                "doi": "10.48550/arXiv.1706.03762",
                "authors": ["Vaswani et al."],
                "year": 2017,
                "abstract": "We propose a new network architecture...",
                "relevance_score": 0.9,
                "verified": True,
            },
        ],
        "literature_matrix": "| Paper | Method | Result |\n|---|---|---|",
        "verified_count": 1,
        "total_found": 1,
        "session_id": "test-session-001",
    }
    result = validate_payload(payload)
    assert result.stage == "literature_done"
    assert result.verified_count == 1


def test_contract_rejects_invalid_verdict():
    """review_done with invalid verdict enum value raises ContractValidationError."""
    payload = {
        "stage": "review_done",
        "verdict": "invalid_verdict",  # must be one of Verdict enum values
        "overall_score": 7.5,
        "major_issues": [],
        "minor_issues": [],
        "adopted_issues": [],
        "session_id": "test-session-001",
    }
    with pytest.raises(ContractValidationError):
        validate_payload(payload)


def test_polish_done_contract_passes():
    """Valid polish_done payload passes validation."""
    payload = {
        "stage": "polish_done",
        "polished_sections": {"abstract": "润色后的摘要内容。"},
        "readability_before": 3.2,
        "readability_after": 4.1,
        "diff_report": "修改了5处用词，增强了逻辑连接。",
        "scorer_json": {
            "cliche_rate_pct": 5.0,
            "diversity_index": 0.7,
            "connective_density_pct": 12.0,
            "readability_score": 4.1,
        },
        "session_id": "test-session-001",
    }
    result = validate_payload(payload)
    assert result.stage == "polish_done"
    assert result.readability_after > result.readability_before

import pytest

from academic_agent_team.contracts.agent_contracts import ContractError, validate_payload


def test_topic_done_contract_passes():
    payload = {
        "stage": "topic_done",
        "selected_direction": "direction",
        "direction_analysis": {"innovation_score": 8.5},
        "journal_type": "中文核心",
        "language": "zh",
        "session_id": "uuid",
    }
    validate_payload(payload)


def test_contract_rejects_missing_field():
    payload = {
        "stage": "writing_done",
        "sections": {},
        "word_count": 12,
        "session_id": "uuid",
    }
    with pytest.raises(ContractError):
        validate_payload(payload)

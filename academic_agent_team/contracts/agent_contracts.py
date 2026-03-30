from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractError(ValueError):
    stage: str
    missing_field: str

    def __str__(self) -> str:
        return f"Contract validation failed: stage={self.stage} missing={self.missing_field}"


REQUIRED_FIELDS = {
    "topic_done": [
        "stage",
        "selected_direction",
        "direction_analysis",
        "journal_type",
        "language",
        "session_id",
    ],
    "literature_done": [
        "stage",
        "papers",
        "literature_matrix",
        "verified_count",
        "total_found",
        "session_id",
    ],
    "writing_done": [
        "stage",
        "sections",
        "word_count",
        "version_id",
        "session_id",
    ],
    "review_done": [
        "stage",
        "verdict",
        "overall_score",
        "major_issues",
        "minor_issues",
        "adopted_issues",
        "session_id",
    ],
    "polish_done": [
        "stage",
        "polished_sections",
        "readability_before",
        "readability_after",
        "diff_report",
        "scorer_json",
        "session_id",
    ],
}


def validate_payload(payload: dict) -> None:
    stage = payload.get("stage")
    if stage not in REQUIRED_FIELDS:
        raise ValueError(f"Unknown stage: {stage!r}")
    for field in REQUIRED_FIELDS[stage]:
        if field not in payload:
            raise ContractError(stage=stage, missing_field=field)

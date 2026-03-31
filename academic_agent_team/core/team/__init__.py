"""
core/team/__init__.py
"""

from __future__ import annotations

from academic_agent_team.core.team.graph_flow_team import (
    AcademicTeam,
    build_academic_team,
)

__all__ = ["AcademicTeam", "build_academic_team"]

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass
class DraftEvaluationItem:
    athlete_id: Optional[str] = None
    skill_id: Optional[str] = None
    rating: Optional[int] = None
    comments: Optional[str] = None


@dataclass
class DraftEvaluation:
    org_id: str
    team_id: Optional[str]
    coach_id: Optional[str]
    scorecard_template_id: Optional[str] = None
    evaluation_date: str = field(default_factory=lambda: date.today().isoformat())
    notes: Optional[str] = None
    evaluation_items: List[DraftEvaluationItem] = field(default_factory=list)


@dataclass
class SessionState:
    session_id: str
    access_token: str
    org_id: str
    team_id: Optional[str]
    coach_id: Optional[str]

    audio_format: str = "pcm16le"
    sample_rate_hz: int = 16000
    channels: int = 1

    templates: List[Dict] = field(default_factory=list)
    categories_by_template: Dict[str, List[Dict]] = field(default_factory=dict)
    subskills_by_category: Dict[str, List[Dict]] = field(default_factory=dict)

    draft: Optional[DraftEvaluation] = None

    template_candidates: List[Dict] = field(default_factory=list)
    team_candidates: List[Dict] = field(default_factory=list)
    athlete_candidates: List[Dict] = field(default_factory=list)
    skill_candidates: List[Dict] = field(default_factory=list)

    missing_fields: List[str] = field(default_factory=list)
    ambiguous_fields: List[str] = field(default_factory=list)
    clarification_question: Optional[str] = None

    transcript_segments: List[str] = field(default_factory=list)
    last_user_text: Optional[str] = None
    last_agent_text: Optional[str] = None

    ready_for_confirmation: bool = False
    confirmed_by_user: bool = False
    clarification_turns: int = 0


def new_session_state(
    session_id: str,
    access_token: str,
    org_id: str,
    team_id: Optional[str],
    coach_id: Optional[str],
) -> SessionState:
    draft = DraftEvaluation(
        org_id=org_id,
        team_id=team_id,
        coach_id=coach_id,
        evaluation_items=[],
    )
    return SessionState(
        session_id=session_id,
        access_token=access_token,
        org_id=org_id,
        team_id=team_id,
        coach_id=coach_id,
        draft=draft,
    )

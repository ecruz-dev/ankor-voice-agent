from __future__ import annotations

from typing import List, Optional, TypedDict


class ScorecardTemplate(TypedDict, total=False):
    id: str
    org_id: str
    sport_id: Optional[str]
    name: str
    description: Optional[str]
    is_active: bool
    created_by: Optional[str]
    created_at: str
    updated_at: str


class ScorecardListOutput(TypedDict, total=False):
    ok: bool
    count: int
    items: List[ScorecardTemplate]


class ScorecardCategory(TypedDict, total=False):
    id: str
    template_id: str
    name: str
    description: Optional[str]
    position: int
    created_at: Optional[str]


class ScorecardCategoriesOutput(TypedDict, total=False):
    ok: bool
    count: int
    items: List[ScorecardCategory]


class ScorecardSubskill(TypedDict, total=False):
    id: str
    category_id: str
    skill_id: str
    name: str
    description: Optional[str]
    position: int
    rating_min: int
    rating_max: int
    created_at: str


class ScorecardSubskillsOutput(TypedDict, total=False):
    ok: bool
    count: int
    items: List[ScorecardSubskill]


class Team(TypedDict, total=False):
    id: str
    org_id: str
    sport_id: Optional[str]
    name: str
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class TeamsListOutput(TypedDict, total=False):
    ok: bool
    data: List[Team]


class Athlete(TypedDict, total=False):
    team_id: str
    id: str
    org_id: str
    user_id: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: Optional[str]
    phone: Optional[str]
    graduation_year: Optional[int]
    cell_number: Optional[str]
    position_id: Optional[str]
    position: Optional[str]


class AthletesByTeamOutput(TypedDict, total=False):
    ok: bool
    count: int
    data: List[Athlete]


class EvaluationItem(TypedDict, total=False):
    id: str
    rating: int
    athlete_id: str
    created_at: str
    evaluation_id: str
    recommended_skill_id: Optional[str]
    skill_id: str
    comments: Optional[str]


class Evaluation(TypedDict, total=False):
    id: str
    notes: Optional[str]
    org_id: str
    status: str
    coach_id: str
    sport_id: Optional[str]
    created_at: str
    scorecard_template_id: str
    team_id: str
    evaluation_items: List[EvaluationItem]


class EvaluationsBulkCreateOutput(TypedDict, total=False):
    ok: bool
    count: int
    data: List[Evaluation]

from __future__ import annotations

from typing import List, Optional, TypedDict


class ScorecardListInput(TypedDict, total=False):
    org_id: str
    limit: int
    offset: int


class ScorecardCategoriesInput(TypedDict, total=False):
    org_id: str
    scorecard_template_id: str
    limit: int
    offset: int


class ScorecardSubskillsInput(TypedDict, total=False):
    org_id: str
    category_id: str
    limit: int
    offset: int


class TeamsListInput(TypedDict, total=False):
    org_id: str


class AthletesByTeamInput(TypedDict, total=False):
    org_id: str
    team_id: str


class EvaluationItemInput(TypedDict, total=False):
    athlete_id: str
    skill_id: str
    rating: int
    comments: Optional[str]


class EvaluationInput(TypedDict, total=False):
    org_id: str
    scorecard_template_id: str
    team_id: str
    coach_id: str
    notes: Optional[str]
    evaluation_items: List[EvaluationItemInput]


class EvaluationsBulkCreateInput(TypedDict, total=False):
    evaluations: List[EvaluationInput]

from __future__ import annotations

from typing import List, Optional

from app.integrations.ankor_api import AnkorApiClient
from app.schemas.tool_inputs import EvaluationInput
from app.schemas.tool_outputs import (
    AthletesByTeamOutput,
    EvaluationsBulkCreateOutput,
    ScorecardCategoriesOutput,
    ScorecardListOutput,
    ScorecardSubskillsOutput,
    TeamsListOutput,
)
from app.session_state import SessionState


def _require_same(name: str, expected: Optional[str], actual: Optional[str]) -> None:
    if expected and actual and expected != actual:
        raise ValueError(f"{name} does not match session context")


def _resolve_required(name: str, value: Optional[str], fallback: Optional[str]) -> str:
    if value:
        return value
    if fallback:
        return fallback
    raise ValueError(f"{name} is required")


def build_tools(client: AnkorApiClient, state: SessionState) -> List[object]:
    async def scorecard_list(
        org_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ScorecardListOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        return await client.scorecard_list(
            access_token=state.access_token,
            org_id=resolved_org_id,
            limit=limit,
            offset=offset,
        )

    async def scorecard_categories(
        scorecard_template_id: str,
        org_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> ScorecardCategoriesOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        return await client.scorecard_categories(
            access_token=state.access_token,
            org_id=resolved_org_id,
            scorecard_template_id=scorecard_template_id,
            limit=limit,
            offset=offset,
        )

    async def scorecard_subskills(
        category_id: str,
        org_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> ScorecardSubskillsOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        return await client.scorecard_subskills(
            access_token=state.access_token,
            org_id=resolved_org_id,
            category_id=category_id,
            limit=limit,
            offset=offset,
        )

    async def teams_list(
        org_id: Optional[str] = None,
    ) -> TeamsListOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        return await client.teams_list(
            access_token=state.access_token,
            org_id=resolved_org_id,
        )

    async def athletes_by_team(
        team_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> AthletesByTeamOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        resolved_team_id = _resolve_required("team_id", team_id, state.team_id)
        _require_same("team_id", state.team_id, team_id)
        return await client.athletes_by_team(
            access_token=state.access_token,
            org_id=resolved_org_id,
            team_id=resolved_team_id,
        )

    async def evaluations_bulk_create(
        evaluations: List[EvaluationInput],
        org_id: Optional[str] = None,
    ) -> EvaluationsBulkCreateOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)

        normalized_evaluations: List[EvaluationInput] = []
        for evaluation in evaluations:
            _require_same("org_id", resolved_org_id, evaluation.get("org_id"))
            _require_same("team_id", state.team_id, evaluation.get("team_id"))
            _require_same("coach_id", state.coach_id, evaluation.get("coach_id"))

            normalized = dict(evaluation)
            normalized["org_id"] = resolved_org_id
            if state.team_id and not normalized.get("team_id"):
                normalized["team_id"] = state.team_id
            if state.coach_id and not normalized.get("coach_id"):
                normalized["coach_id"] = state.coach_id
            normalized_evaluations.append(normalized)

        return await client.evaluations_bulk_create(
            access_token=state.access_token,
            org_id=resolved_org_id,
            payload={"evaluations": normalized_evaluations},
        )

    return [
        scorecard_list,
        scorecard_categories,
        scorecard_subskills,
        teams_list,
        athletes_by_team,
        evaluations_bulk_create,
    ]

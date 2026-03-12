from __future__ import annotations

from typing import Any, Dict, List, Optional

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

MAX_TOOL_ITEMS = 25
MAX_EVALUATION_ITEMS = 10


def _require_same(name: str, expected: Optional[str], actual: Optional[str]) -> None:
    if expected and actual and expected != actual:
        raise ValueError(f"{name} does not match session context")


def _resolve_required(name: str, value: Optional[str], fallback: Optional[str]) -> str:
    if value:
        return value
    if fallback:
        return fallback
    raise ValueError(f"{name} is required")


def _normalize_evaluation_items(evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_items = evaluation.get("evaluation_items")
    if not raw_items:
        raw_items = evaluation.get("scores")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("evaluation_items is required and must be a non-empty array")

    fallback_athlete_id = evaluation.get("athlete_id")
    normalized_items: List[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Each evaluation item must be an object")

        athlete_id = item.get("athlete_id") or fallback_athlete_id
        skill_id = item.get("skill_id") or item.get("scorecard_subskill_id")
        rating = item.get("rating")
        comments = item.get("comments")

        if not athlete_id:
            raise ValueError("evaluation_items[].athlete_id is required")
        if not skill_id:
            raise ValueError("evaluation_items[].skill_id is required")
        if isinstance(rating, bool) or not isinstance(rating, (int, float)):
            raise ValueError("evaluation_items[].rating must be a number from 1 to 5")
        if rating < 1 or rating > 5:
            raise ValueError("evaluation_items[].rating must be between 1 and 5")
        normalized_rating = int(rating)

        normalized_item: Dict[str, Any] = {
            "athlete_id": athlete_id,
            "skill_id": skill_id,
            "rating": normalized_rating,
        }
        if comments is not None:
            normalized_item["comments"] = comments
        normalized_items.append(normalized_item)

    return normalized_items


def _filter_items(
    items: List[Dict[str, Any]],
    field_name: str,
    expected_value: Optional[str],
) -> List[Dict[str, Any]]:
    if not expected_value:
        return items
    return [item for item in items if item.get(field_name) == expected_value]


def _compact_item(
    item: Dict[str, Any],
    allowed_fields: List[str],
    *,
    truncate_text_fields: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for field_name in allowed_fields:
        value = item.get(field_name)
        if value is None:
            continue
        max_len = (truncate_text_fields or {}).get(field_name)
        if max_len and isinstance(value, str) and len(value) > max_len:
            truncate_at = max(max_len - 3, 0)
            value = value[:truncate_at].rstrip() + "..."
        compact[field_name] = value
    return compact


def _shape_list_payload(
    raw_items: Any,
    *,
    allowed_fields: List[str],
    response_key: str,
    filter_field: Optional[str] = None,
    filter_value: Optional[str] = None,
    max_items: int = MAX_TOOL_ITEMS,
    truncate_text_fields: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    items = raw_items if isinstance(raw_items, list) else []
    filtered_items = (
        _filter_items(items, filter_field, filter_value) if filter_field else items
    )
    limited_items = filtered_items[:max_items]
    shaped_items = [
        _compact_item(
            item,
            allowed_fields,
            truncate_text_fields=truncate_text_fields,
        )
        for item in limited_items
        if isinstance(item, dict)
    ]
    payload: Dict[str, Any] = {
        "count": len(filtered_items),
        response_key: shaped_items,
    }
    if len(filtered_items) > len(limited_items):
        payload["truncated"] = True
        payload["returned_count"] = len(limited_items)
    return payload


def _shape_scorecard_list_output(
    result: Dict[str, Any],
    *,
    scorecard_template_id: Optional[str],
) -> ScorecardListOutput:
    payload = _shape_list_payload(
        result.get("items"),
        allowed_fields=["id", "org_id", "name", "description", "is_active"],
        response_key="items",
        filter_field="id",
        filter_value=scorecard_template_id,
        truncate_text_fields={"description": 160},
    )
    payload["ok"] = bool(result.get("ok", True))
    return payload


def _shape_scorecard_categories_output(
    result: Dict[str, Any],
) -> ScorecardCategoriesOutput:
    payload = _shape_list_payload(
        result.get("items"),
        allowed_fields=["id", "template_id", "name", "position", "description"],
        response_key="items",
        truncate_text_fields={"description": 160},
    )
    payload["ok"] = bool(result.get("ok", True))
    return payload


def _shape_scorecard_subskills_output(
    result: Dict[str, Any],
    *,
    skill_id: Optional[str],
) -> ScorecardSubskillsOutput:
    payload = _shape_list_payload(
        result.get("items"),
        allowed_fields=[
            "id",
            "category_id",
            "skill_id",
            "name",
            "position",
            "rating_min",
            "rating_max",
            "description",
        ],
        response_key="items",
        filter_field="skill_id",
        filter_value=skill_id,
        truncate_text_fields={"description": 160},
    )
    payload["ok"] = bool(result.get("ok", True))
    return payload


def _shape_teams_output(
    result: Dict[str, Any],
    *,
    team_id: Optional[str],
) -> TeamsListOutput:
    payload = _shape_list_payload(
        result.get("data"),
        allowed_fields=["id", "org_id", "name", "is_active"],
        response_key="data",
        filter_field="id",
        filter_value=team_id,
    )
    payload["ok"] = bool(result.get("ok", True))
    return payload


def _shape_athletes_output(
    result: Dict[str, Any],
    *,
    athlete_id: Optional[str],
) -> AthletesByTeamOutput:
    payload = _shape_list_payload(
        result.get("data"),
        allowed_fields=[
            "id",
            "team_id",
            "org_id",
            "full_name",
            "first_name",
            "last_name",
            "position",
            "graduation_year",
        ],
        response_key="data",
        filter_field="id",
        filter_value=athlete_id,
    )
    payload["ok"] = bool(result.get("ok", True))
    return payload


def _shape_bulk_create_output(
    result: Dict[str, Any],
) -> EvaluationsBulkCreateOutput:
    raw_evaluations = result.get("data")
    evaluations = raw_evaluations if isinstance(raw_evaluations, list) else []
    compact_evaluations: List[Dict[str, Any]] = []
    for evaluation in evaluations[:MAX_TOOL_ITEMS]:
        if not isinstance(evaluation, dict):
            continue
        compact_evaluation = _compact_item(
            evaluation,
            [
                "id",
                "org_id",
                "scorecard_template_id",
                "team_id",
                "coach_id",
                "status",
                "notes",
            ],
            truncate_text_fields={"notes": 160},
        )
        items = evaluation.get("evaluation_items")
        if isinstance(items, list) and items:
            compact_evaluation["evaluation_items"] = [
                _compact_item(
                    item,
                    ["id", "athlete_id", "skill_id", "rating", "comments"],
                    truncate_text_fields={"comments": 160},
                )
                for item in items[:MAX_EVALUATION_ITEMS]
                if isinstance(item, dict)
            ]
            if len(items) > MAX_EVALUATION_ITEMS:
                compact_evaluation["evaluation_items_truncated"] = True
        compact_evaluations.append(compact_evaluation)

    payload: Dict[str, Any] = {
        "ok": bool(result.get("ok", True)),
        "count": len(evaluations),
        "data": compact_evaluations,
    }
    if len(evaluations) > len(compact_evaluations):
        payload["truncated"] = True
        payload["returned_count"] = len(compact_evaluations)
    return payload


def build_tools(client: AnkorApiClient, state: SessionState) -> List[object]:
    async def scorecard_list(
        org_id: Optional[str] = None,
        scorecard_template_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ScorecardListOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        result = await client.scorecard_list(
            access_token=state.access_token,
            org_id=resolved_org_id,
            limit=limit,
            offset=offset,
        )
        return _shape_scorecard_list_output(
            result,
            scorecard_template_id=scorecard_template_id,
        )

    async def scorecard_categories(
        scorecard_template_id: str,
        org_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> ScorecardCategoriesOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        result = await client.scorecard_categories(
            access_token=state.access_token,
            org_id=resolved_org_id,
            scorecard_template_id=scorecard_template_id,
            limit=limit,
            offset=offset,
        )
        return _shape_scorecard_categories_output(result)

    async def scorecard_subskills(
        category_id: str,
        org_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> ScorecardSubskillsOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        result = await client.scorecard_subskills(
            access_token=state.access_token,
            org_id=resolved_org_id,
            category_id=category_id,
            limit=limit,
            offset=offset,
        )
        return _shape_scorecard_subskills_output(result, skill_id=skill_id)

    async def teams_list(
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> TeamsListOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        result = await client.teams_list(
            access_token=state.access_token,
            org_id=resolved_org_id,
        )
        return _shape_teams_output(result, team_id=team_id)

    async def athletes_by_team(
        team_id: Optional[str] = None,
        org_id: Optional[str] = None,
        athlete_id: Optional[str] = None,
    ) -> AthletesByTeamOutput:
        _require_same("org_id", state.org_id, org_id)
        resolved_org_id = _resolve_required("org_id", org_id, state.org_id)
        resolved_team_id = _resolve_required("team_id", team_id, state.team_id)
        _require_same("team_id", state.team_id, team_id)
        result = await client.athletes_by_team(
            access_token=state.access_token,
            org_id=resolved_org_id,
            team_id=resolved_team_id,
        )
        return _shape_athletes_output(result, athlete_id=athlete_id)

    async def evaluations_bulk_create(
        evaluations: Optional[List[Dict[str, Any]]] = None,
        org_id: Optional[str] = None,
        scorecard_template_id: Optional[str] = None,
        team_id: Optional[str] = None,
        coach_id: Optional[str] = None,
        notes: Optional[str] = None,
        athlete_id: Optional[str] = None,
        evaluation_items: Optional[List[Dict[str, Any]]] = None,
        scores: Optional[List[Dict[str, Any]]] = None,
    ) -> EvaluationsBulkCreateOutput:
        """
        Create evaluations.

        Preferred payload shape:
        {
          "evaluations": [
            {
              "org_id": "...",
              "scorecard_template_id": "...",
              "team_id": "...",
              "coach_id": "...",
              "notes": "...",
              "evaluation_items": [
                {"athlete_id": "...", "skill_id": "...", "rating": 3, "comments": "..."}
              ]
            }
          ]
        }

        Compatibility:
        - Accepts legacy "scores" and maps to "evaluation_items".
        - Accepts "scorecard_subskill_id" and maps to "skill_id".
        - Accepts top-level fields and constructs a single-item evaluations list.
        """
        try:
            _require_same("org_id", state.org_id, org_id)
            resolved_org_id = _resolve_required("org_id", org_id, state.org_id)

            if not evaluations:
                synthesized: Dict[str, Any] = {
                    "org_id": resolved_org_id,
                    "scorecard_template_id": scorecard_template_id,
                    "team_id": team_id or state.team_id,
                    "coach_id": coach_id or state.coach_id,
                    "notes": notes,
                    "athlete_id": athlete_id,
                    "evaluation_items": evaluation_items,
                    "scores": scores,
                }
                evaluations = [synthesized]

            if not isinstance(evaluations, list) or not evaluations:
                raise ValueError("evaluations must be a non-empty array")

            normalized_evaluations: List[EvaluationInput] = []
            for evaluation in evaluations:
                if not isinstance(evaluation, dict):
                    raise ValueError("Each evaluation must be an object")
                _require_same("org_id", resolved_org_id, evaluation.get("org_id"))
                _require_same("team_id", state.team_id, evaluation.get("team_id"))
                _require_same("coach_id", state.coach_id, evaluation.get("coach_id"))

                normalized = dict(evaluation)
                normalized["org_id"] = resolved_org_id
                if state.team_id and not normalized.get("team_id"):
                    normalized["team_id"] = state.team_id
                if state.coach_id and not normalized.get("coach_id"):
                    normalized["coach_id"] = state.coach_id
                normalized["evaluation_items"] = _normalize_evaluation_items(normalized)
                # Drop unsupported or legacy fields before sending to API.
                normalized.pop("scores", None)
                normalized.pop("athlete_id", None)
                normalized.pop("effective_date", None)
                normalized_evaluations.append(normalized)

            result = await client.evaluations_bulk_create(
                access_token=state.access_token,
                org_id=resolved_org_id,
                payload={"evaluations": normalized_evaluations},
            )
            return _shape_bulk_create_output(result)
        except ValueError as exc:
            return {
                "ok": False,
                "count": 0,
                "data": [],
                "error": str(exc),
            }

    return [
        scorecard_list,
        scorecard_categories,
        scorecard_subskills,
        teams_list,
        athletes_by_team,
        evaluations_bulk_create,
    ]

from __future__ import annotations

import asyncio
import unittest

from app.adk.tools import build_tools
from app.session_state import new_session_state


class StubClient:
    def __init__(self) -> None:
        self.calls = []

    async def scorecard_list(self, **kwargs):
        self.calls.append(("scorecard_list", kwargs))
        return {
            "ok": True,
            "items": [
                {
                    "id": f"template-{index}",
                    "org_id": "org-1",
                    "name": f"Template {index}",
                    "description": "d" * 240,
                    "is_active": True,
                    "created_at": "2026-03-12T00:00:00Z",
                }
                for index in range(30)
            ],
        }

    async def scorecard_categories(self, **kwargs):
        self.calls.append(("scorecard_categories", kwargs))
        return {
            "ok": True,
            "items": [
                {
                    "id": "category-1",
                    "template_id": "template-1",
                    "name": "Shooting",
                    "description": "x" * 220,
                    "position": 1,
                    "created_at": "2026-03-12T00:00:00Z",
                }
            ],
        }

    async def scorecard_subskills(self, **kwargs):
        self.calls.append(("scorecard_subskills", kwargs))
        return {
            "ok": True,
            "items": [
                {
                    "id": "subskill-1",
                    "category_id": "category-1",
                    "skill_id": "skill-1",
                    "name": "Footwork",
                    "description": "y" * 220,
                    "position": 1,
                    "rating_min": 1,
                    "rating_max": 5,
                },
                {
                    "id": "subskill-2",
                    "category_id": "category-1",
                    "skill_id": "skill-2",
                    "name": "Release",
                    "description": "z" * 220,
                    "position": 2,
                    "rating_min": 1,
                    "rating_max": 5,
                },
            ],
        }

    async def teams_list(self, **kwargs):
        self.calls.append(("teams_list", kwargs))
        return {
            "ok": True,
            "data": [
                {
                    "id": f"team-{index}",
                    "org_id": "org-1",
                    "name": f"Team {index}",
                    "is_active": True,
                    "created_at": "2026-03-12T00:00:00Z",
                }
                for index in range(40)
            ],
        }

    async def athletes_by_team(self, **kwargs):
        self.calls.append(("athletes_by_team", kwargs))
        return {
            "ok": True,
            "data": [
                {
                    "id": "athlete-1",
                    "team_id": "team-1",
                    "org_id": "org-1",
                    "full_name": "Athlete One",
                    "position": "Guard",
                    "graduation_year": 2027,
                    "phone": "hidden",
                },
                {
                    "id": "athlete-2",
                    "team_id": "team-1",
                    "org_id": "org-1",
                    "full_name": "Athlete Two",
                    "position": "Forward",
                    "graduation_year": 2028,
                    "phone": "hidden",
                },
            ],
        }

    async def evaluations_bulk_create(self, **kwargs):
        self.calls.append(("evaluations_bulk_create", kwargs))
        return {
            "ok": True,
            "count": 1,
            "data": [
                {
                    "id": "evaluation-1",
                    "org_id": "org-1",
                    "scorecard_template_id": "template-1",
                    "team_id": "team-1",
                    "coach_id": "coach-1",
                    "status": "created",
                    "notes": "n" * 220,
                    "evaluation_items": [
                        {
                            "id": "item-1",
                            "athlete_id": "athlete-1",
                            "skill_id": "skill-1",
                            "rating": 4,
                            "comments": "c" * 220,
                            "created_at": "2026-03-12T00:00:00Z",
                        }
                    ],
                }
            ],
        }


def _tool_map(client: StubClient):
    state = new_session_state(
        session_id="session-1",
        access_token="token",
        org_id="org-1",
        team_id="team-1",
        coach_id="coach-1",
    )
    return {tool.__name__: tool for tool in build_tools(client, state)}


class ToolTests(unittest.TestCase):
    def test_scorecard_list_filters_and_truncates(self) -> None:
        client = StubClient()
        tools = _tool_map(client)

        result = asyncio.run(
            tools["scorecard_list"](
                org_id="org-1",
                scorecard_template_id="template-27",
                limit=200,
            )
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["items"],
            [
                {
                    "id": "template-27",
                    "org_id": "org-1",
                    "name": "Template 27",
                    "description": ("d" * 157) + "...",
                    "is_active": True,
                }
            ],
        )

    def test_teams_and_athletes_are_filtered_to_exact_ids(self) -> None:
        client = StubClient()
        tools = _tool_map(client)

        teams = asyncio.run(tools["teams_list"](org_id="org-1", team_id="team-7"))
        athletes = asyncio.run(
            tools["athletes_by_team"](
                org_id="org-1",
                team_id="team-1",
                athlete_id="athlete-2",
            )
        )

        self.assertEqual(
            teams["data"],
            [
                {
                    "id": "team-7",
                    "org_id": "org-1",
                    "name": "Team 7",
                    "is_active": True,
                }
            ],
        )
        self.assertEqual(
            athletes["data"],
            [
                {
                    "id": "athlete-2",
                    "team_id": "team-1",
                    "org_id": "org-1",
                    "full_name": "Athlete Two",
                    "position": "Forward",
                    "graduation_year": 2028,
                }
            ],
        )

    def test_scorecard_subskills_filter_to_requested_skill(self) -> None:
        client = StubClient()
        tools = _tool_map(client)

        result = asyncio.run(
            tools["scorecard_subskills"](
                org_id="org-1",
                category_id="category-1",
                skill_id="skill-2",
            )
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["items"],
            [
                {
                    "id": "subskill-2",
                    "category_id": "category-1",
                    "skill_id": "skill-2",
                    "name": "Release",
                    "position": 2,
                    "rating_min": 1,
                    "rating_max": 5,
                    "description": ("z" * 157) + "...",
                }
            ],
        )

    def test_bulk_create_returns_compact_payload(self) -> None:
        client = StubClient()
        tools = _tool_map(client)

        result = asyncio.run(
            tools["evaluations_bulk_create"](
                org_id="org-1",
                scorecard_template_id="template-1",
                team_id="team-1",
                athlete_id="athlete-1",
                scores=[{"skill_id": "skill-1", "rating": 4}],
            )
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["data"],
            [
                {
                    "id": "evaluation-1",
                    "org_id": "org-1",
                    "scorecard_template_id": "template-1",
                    "team_id": "team-1",
                    "coach_id": "coach-1",
                    "status": "created",
                    "notes": ("n" * 157) + "...",
                    "evaluation_items": [
                        {
                            "id": "item-1",
                            "athlete_id": "athlete-1",
                            "skill_id": "skill-1",
                            "rating": 4,
                            "comments": ("c" * 157) + "...",
                        }
                    ],
                }
            ],
        )

        method, kwargs = client.calls[-1]
        self.assertEqual(method, "evaluations_bulk_create")
        self.assertEqual(
            kwargs["payload"],
            {
                "evaluations": [
                    {
                        "org_id": "org-1",
                        "scorecard_template_id": "template-1",
                        "team_id": "team-1",
                        "coach_id": "coach-1",
                        "notes": None,
                        "evaluation_items": [
                            {
                                "athlete_id": "athlete-1",
                                "skill_id": "skill-1",
                                "rating": 4,
                            }
                        ],
                    }
                ]
            },
        )

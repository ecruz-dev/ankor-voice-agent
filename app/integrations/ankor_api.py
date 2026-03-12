from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger("ankor_voice_agent.integrations.ankor_api")


class AnkorApiError(RuntimeError):
    def __init__(self, status_code: int, url: str, detail: str) -> None:
        super().__init__(f"Ankor API error {status_code} for {url}: {detail}")
        self.status_code = status_code
        self.url = url
        self.detail = detail


class AnkorApiClient:
    def __init__(self, base_url: str, timeout_s: float = 20.0) -> None:
        normalized_base = base_url.rstrip("/") + "/"
        self._client = httpx.AsyncClient(
            base_url=normalized_base,
            timeout=timeout_s,
            headers={"Accept": "application/json"},
        )

    async def __aenter__(self) -> "AnkorApiClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _auth_headers(access_token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path[1:] if path.startswith("/") else path

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_path = self._normalize_path(path)
        logger.info(
            "ANKOR API request method=%s path=%s params=%s json=%s",
            method,
            normalized_path,
            params,
            json,
        )
        started = time.perf_counter()
        response = await self._client.request(
            method=method,
            url=normalized_path,
            headers=self._auth_headers(access_token),
            params=params,
            json=json,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "ANKOR API response method=%s url=%s status=%s elapsed_ms=%s",
            method,
            str(response.url),
            response.status_code,
            elapsed_ms,
        )
        if response.status_code >= 400:
            detail = response.text.strip() or "Unknown error"
            logger.error(
                "ANKOR API error method=%s url=%s status=%s params=%s json=%s detail=%s",
                method,
                str(response.url),
                response.status_code,
                params,
                json,
                detail,
            )
            raise AnkorApiError(response.status_code, str(response.url), detail)
        try:
            return response.json()
        except ValueError as exc:
            raise AnkorApiError(
                response.status_code,
                str(response.url),
                "Invalid JSON response",
            ) from exc

    async def scorecard_list(
        self,
        access_token: str,
        org_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        return await self._request(
            method="GET",
            path="scorecard/list",
            access_token=access_token,
            params={"org_id": org_id, "limit": limit, "offset": offset},
        )

    async def scorecard_categories(
        self,
        access_token: str,
        org_id: str,
        scorecard_template_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        return await self._request(
            method="GET",
            path="scorecard/categories",
            access_token=access_token,
            params={
                "org_id": org_id,
                "scorecard_template_id": scorecard_template_id,
                "limit": limit,
                "offset": offset,
            },
        )

    async def scorecard_subskills(
        self,
        access_token: str,
        org_id: str,
        category_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        return await self._request(
            method="GET",
            path="scorecard/subskills",
            access_token=access_token,
            params={
                "org_id": org_id,
                "category_id": category_id,
                "limit": limit,
                "offset": offset,
            },
        )

    async def teams_list(
        self,
        access_token: str,
        org_id: str,
    ) -> Dict[str, Any]:
        return await self._request(
            method="GET",
            path="teams/list",
            access_token=access_token,
            params={"org_id": org_id},
        )

    async def athletes_by_team(
        self,
        access_token: str,
        org_id: str,
        team_id: Optional[str],
    ) -> Dict[str, Any]:
        if not team_id:
            raise ValueError("team_id is required to list athletes by team")
        return await self._request(
            method="GET",
            path="teams/athletes-by-team",
            access_token=access_token,
            params={"org_id": org_id, "team_id": team_id},
        )

    async def evaluations_bulk_create(
        self,
        access_token: str,
        org_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await self._request(
            method="POST",
            path="evaluations/bulk-create",
            access_token=access_token,
            params={"org_id": org_id},
            json=payload,
        )

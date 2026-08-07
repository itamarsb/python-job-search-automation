from __future__ import annotations

import os
from typing import Any

import requests


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class SerpApiError(RuntimeError):
    """Erro retornado durante uma consulta à SerpApi."""


def search_google_jobs(
    query: str,
    location: str,
    language: str = "pt-br",
    country: str = "br",
    pages: int = 1,
) -> list[dict[str, Any]]:
    api_key = os.getenv("SERPAPI_API_KEY")

    if not api_key:
        raise SerpApiError(
            "A variável de ambiente SERPAPI_API_KEY não foi definida."
        )

    jobs: list[dict[str, Any]] = []
    next_page_token: str | None = None

    for _ in range(max(1, pages)):
        params: dict[str, Any] = {
            "engine": "google_jobs",
            "api_key": api_key,
            "q": query,
            "location": location,
            "hl": language,
            "gl": country,
        }

        if next_page_token:
            params["next_page_token"] = next_page_token

        try:
            response = requests.get(
                SERPAPI_ENDPOINT,
                params=params,
                timeout=45,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SerpApiError(
                f"Falha ao consultar a SerpApi: {exc}"
            ) from exc

        payload = response.json()

        if error := payload.get("error"):
            raise SerpApiError(f"Erro retornado pela SerpApi: {error}")

        jobs.extend(payload.get("jobs_results", []))

        pagination = payload.get("serpapi_pagination", {})
        next_page_token = pagination.get("next_page_token")

        if not next_page_token:
            break

    return jobs

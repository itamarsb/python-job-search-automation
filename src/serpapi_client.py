from __future__ import annotations

import os
import time
from typing import Any

import requests


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class SerpApiError(RuntimeError):
    """Erro retornado durante uma consulta à SerpApi."""


def search_google_jobs(
    query: str,
    location: str = "",
    language: str = "pt",
    country: str = "br",
    pages: int = 1,
    remote_only: bool = False,
    date_posted: str | None = None,
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
    "hl": language,
    "gl": country,
}

        if date_posted:
            params["chips"] = f"date_posted:{date_posted}"

        # Só envia location quando realmente existir um valor.
        if location and location.strip():
            params["location"] = location.strip()

        if next_page_token:
            params["next_page_token"] = next_page_token

        response = None

        # Até 3 tentativas em caso de timeout ou falha temporária.
        for attempt in range(1, 4):
            try:
                response = requests.get(
                    SERPAPI_ENDPOINT,
                    params=params,
                    timeout=60,
                )
                response.raise_for_status()
                break

            except requests.Timeout:
                if attempt == 3:
                    raise SerpApiError(
                        "A consulta à SerpApi excedeu o tempo limite após 3 tentativas."
                    )

                time.sleep(attempt * 2)

            except requests.RequestException as exc:
                raise SerpApiError(
                    f"Falha ao consultar a SerpApi: {exc}"
                ) from exc

        if response is None:
            raise SerpApiError(
                "Não foi possível obter resposta da SerpApi."
            )

        payload = response.json()

        error = payload.get("error")

        # Ausência de resultados não é falha da aplicação.
        if error:
            if "hasn't returned any results" in error.lower():
                return jobs

            raise SerpApiError(
                f"Erro retornado pela SerpApi: {error}"
            )

        jobs.extend(payload.get("jobs_results", []))

        pagination = payload.get("serpapi_pagination", {})
        next_page_token = pagination.get("next_page_token")

        if not next_page_token:
            break

    return jobs
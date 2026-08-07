from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    return without_accents.casefold().strip()


def regex_matches(text: str, patterns: list[str]) -> list[str]:
    matches: list[str] = []

    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                matches.append(pattern)
        except re.error as exc:
            raise ValueError(
                f"Expressão regular inválida: {pattern!r}: {exc}"
            ) from exc

    return matches


def extract_sources(job: dict[str, Any]) -> list[str]:
    sources: list[str] = []

    via = job.get("via")
    if via:
        sources.append(str(via))

    for option in job.get("apply_options", []):
        title = option.get("title")
        link = option.get("link")

        if title:
            sources.append(str(title))

        if link:
            sources.append(str(link))

    return sources


def is_from_linkedin(job: dict[str, Any]) -> bool:
    sources = " ".join(extract_sources(job))
    return "linkedin" in normalize_text(sources)


def evaluate_job(
    job: dict[str, Any],
    search_config: dict[str, Any],
    linkedin_only: bool = False,
) -> dict[str, Any]:
    title = str(job.get("title", ""))
    company = str(job.get("company_name", ""))
    location = str(job.get("location", ""))
    description = str(job.get("description", ""))

    searchable_text = normalize_text(
        f"{title} {company} {location} {description}"
    )

    include_patterns = search_config.get("include_patterns", [])
    exclude_patterns = search_config.get("exclude_patterns", [])

    include_matches = regex_matches(searchable_text, include_patterns)
    exclude_matches = regex_matches(searchable_text, exclude_patterns)

    blocked_companies = {
        normalize_text(item)
        for item in search_config.get("blocked_companies", [])
    }

    preferred_companies = {
        normalize_text(item)
        for item in search_config.get("preferred_companies", [])
    }

    normalized_company = normalize_text(company)
    linkedin_source = is_from_linkedin(job)

    rejection_reasons: list[str] = []

    if include_patterns and not include_matches:
        rejection_reasons.append("Nenhum padrão obrigatório encontrado")

    if exclude_matches:
        rejection_reasons.append(
            f"Padrões de exclusão encontrados: {exclude_matches}"
        )

    if normalized_company in blocked_companies:
        rejection_reasons.append("Empresa bloqueada")

    if linkedin_only and not linkedin_source:
        rejection_reasons.append("A vaga não possui origem LinkedIn identificada")

    score = len(include_matches) * 10

    if normalized_company in preferred_companies:
        score += 25

    if linkedin_source:
        score += 5

    return {
        "approved": not rejection_reasons,
        "score": score,
        "include_matches": include_matches,
        "exclude_matches": exclude_matches,
        "rejection_reasons": rejection_reasons,
        "linkedin_source": linkedin_source,
    }

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("data/jobs.db")


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                fingerprint TEXT PRIMARY KEY,
                search_name TEXT NOT NULL,
                job_id TEXT,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                source TEXT,
                apply_link TEXT,
                posted_at TEXT,
                detected_at TEXT NOT NULL,
                score INTEGER NOT NULL,
                linkedin_source INTEGER NOT NULL,
                raw_json TEXT NOT NULL
            )
            """
        )


def create_fingerprint(job: dict[str, Any]) -> str:
    source_value = "|".join(
        [
            str(job.get("job_id", "")),
            str(job.get("title", "")),
            str(job.get("company_name", "")),
            str(job.get("location", "")),
        ]
    )

    return hashlib.sha256(
        source_value.casefold().encode("utf-8")
    ).hexdigest()


def get_apply_link(job: dict[str, Any]) -> str:
    for option in job.get("apply_options", []):
        if option.get("link"):
            return str(option["link"])

    related_links = job.get("related_links", [])

    for related_link in related_links:
        if related_link.get("link"):
            return str(related_link["link"])

    return ""


def insert_job(
    job: dict[str, Any],
    search_name: str,
    score: int,
    linkedin_source: bool,
) -> bool:
    fingerprint = create_fingerprint(job)

    detected_at = datetime.now(timezone.utc).isoformat()

    detected_extensions = job.get("detected_extensions", {})
    posted_at = detected_extensions.get("posted_at", "")

    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO jobs (
                fingerprint,
                search_name,
                job_id,
                title,
                company,
                location,
                source,
                apply_link,
                posted_at,
                detected_at,
                score,
                linkedin_source,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fingerprint,
                search_name,
                job.get("job_id"),
                job.get("title", ""),
                job.get("company_name", ""),
                job.get("location", ""),
                job.get("via", ""),
                get_apply_link(job),
                posted_at,
                detected_at,
                score,
                int(linkedin_source),
                json.dumps(job, ensure_ascii=False),
            ),
        )

        return cursor.rowcount == 1

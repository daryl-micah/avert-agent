"""Thin query helpers over the migrations/0001_init.sql schema.

No ORM (STRUCTURE §2) — this is a set of plain-SQL functions, not a model
layer. Callers pass an open psycopg connection.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from avert.models.change_event_schema import ChangeEvent

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(conn: psycopg.Connection) -> None:
    """Applies every migrations/*.sql file in order. Week 1 has one
    migration and no tracking table — safe to call once against a fresh
    database; not idempotent against an already-migrated one."""
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.execute(path.read_text())
    conn.commit()


def upsert_repository(conn: psycopg.Connection, name: str) -> int:
    row = conn.execute(
        """
        INSERT INTO repository (name) VALUES (%s)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (name,),
    ).fetchone()
    return row[0]


def indexed_file_hashes(conn: psycopg.Connection, repository_id: int) -> dict[str, str]:
    """Maps path -> content_hash for every file currently indexed for this
    repository. The incremental re-index diff base (SPEC §8.2)."""
    rows = conn.execute(
        "SELECT path, content_hash FROM indexed_file WHERE repository_id = %s",
        (repository_id,),
    ).fetchall()
    return dict(rows)


def upsert_indexed_file(
    conn: psycopg.Connection,
    *,
    repository_id: int,
    path: str,
    language: str,
    content_hash: str,
    commit_sha: str | None,
) -> int:
    row = conn.execute(
        """
        INSERT INTO indexed_file (repository_id, path, language, content_hash, commit_sha, updated_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (repository_id, path) DO UPDATE
            SET language = EXCLUDED.language,
                content_hash = EXCLUDED.content_hash,
                commit_sha = EXCLUDED.commit_sha,
                updated_at = now()
        RETURNING id
        """,
        (repository_id, path, language, content_hash, commit_sha),
    ).fetchone()
    return row[0]


def delete_indexed_file(conn: psycopg.Connection, *, repository_id: int, path: str) -> None:
    """Removes a file and, via ON DELETE CASCADE, its call sites."""
    conn.execute(
        "DELETE FROM indexed_file WHERE repository_id = %s AND path = %s",
        (repository_id, path),
    )


def delete_call_sites_for_file(conn: psycopg.Connection, indexed_file_id: int) -> None:
    conn.execute("DELETE FROM call_site WHERE indexed_file_id = %s", (indexed_file_id,))


def upsert_surface(
    conn: psycopg.Connection,
    *,
    provider: str,
    resource: str,
    operation: str | None,
    field_path: str | None,
    value: str | None,
) -> int:
    row = conn.execute(
        """
        INSERT INTO surface (provider, resource, operation, field_path, value)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (provider, resource, operation, field_path, value)
            DO UPDATE SET provider = EXCLUDED.provider
        RETURNING id
        """,
        (provider, resource, operation, field_path, value),
    ).fetchone()
    return row[0]


def insert_call_site(
    conn: psycopg.Connection,
    *,
    indexed_file_id: int,
    surface_id: int,
    line_start: int,
    line_end: int,
    api_version: str | None,
    value_binding: str,
    confidence: float,
    extractor: str,
) -> int:
    row = conn.execute(
        """
        INSERT INTO call_site
            (indexed_file_id, surface_id, line_start, line_end, api_version, value_binding, confidence, extractor)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (indexed_file_id, surface_id, line_start, line_end, api_version, value_binding, confidence, extractor),
    ).fetchone()
    return row[0]


def upsert_change_event(conn: psycopg.Connection, event: ChangeEvent, *, fingerprint: str) -> int:
    surface_id = upsert_surface(conn, **event.surface.model_dump())
    replacement_surface_id = None
    if event.replacement_surface is not None:
        replacement_surface_id = upsert_surface(conn, **event.replacement_surface.model_dump())
    row = conn.execute(
        """
        INSERT INTO change_event
            (surface_id, replacement_surface_id, change_type, severity, source, confidence, summary,
             announced_at, effective_at, applies_from, applies_to, detected_at, provenance, fingerprint)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET
            confidence = EXCLUDED.confidence, summary = EXCLUDED.summary,
            announced_at = EXCLUDED.announced_at, effective_at = EXCLUDED.effective_at,
            detected_at = EXCLUDED.detected_at, provenance = EXCLUDED.provenance
        RETURNING id
        """,
        (
            surface_id, replacement_surface_id, event.change_type, event.severity, event.source,
            event.confidence, event.summary, event.announced_at, event.effective_at,
            event.applies_from, event.applies_to, event.detected_at, event.provenance.model_dump_json(), fingerprint,
        ),
    ).fetchone()
    return row[0]

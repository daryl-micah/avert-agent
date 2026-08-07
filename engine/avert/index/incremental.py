"""Incremental re-indexing (SPEC §8.2 — "non-negotiable from day one").

Keyed on file content hash: unchanged files are skipped entirely, changed
files are re-parsed and their call sites replaced (not duplicated), and
files no longer present are removed via ON DELETE CASCADE.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import psycopg

from avert import db
from avert.index.candidates import find_candidates
from avert.index.parse import extract_call_sites


@dataclass
class IncrementalStats:
    parsed: int = 0
    skipped: int = 0
    deleted: int = 0
    call_sites_written: int = 0


def incremental_index(
    conn: psycopg.Connection, root: Path, *, repo: str, commit: str | None = None
) -> IncrementalStats:
    root = root.resolve()
    stats = IncrementalStats()

    repository_id = db.upsert_repository(conn, repo)
    previous_hashes = db.indexed_file_hashes(conn, repository_id)

    seen_paths: set[str] = set()

    for candidate in find_candidates(root):
        rel_path = str(candidate.path.relative_to(root))
        seen_paths.add(rel_path)
        source = candidate.path.read_bytes()
        content_hash = hashlib.sha256(source).hexdigest()

        if previous_hashes.get(rel_path) == content_hash:
            stats.skipped += 1
            continue

        call_sites = extract_call_sites(
            file_path=rel_path,
            language=candidate.language,
            source=source,
            repo=repo,
            commit_sha=commit,
        )

        indexed_file_id = db.upsert_indexed_file(
            conn,
            repository_id=repository_id,
            path=rel_path,
            language=candidate.language,
            content_hash=content_hash,
            commit_sha=commit,
        )
        # Replace, not append — re-parsing a changed file must not
        # duplicate rows from its previous version.
        db.delete_call_sites_for_file(conn, indexed_file_id)

        for cs in call_sites:
            surface_id = db.upsert_surface(
                conn,
                provider=cs.surface.provider,
                resource=cs.surface.resource,
                operation=cs.surface.operation,
                field_path=cs.surface.field_path,
                value=cs.surface.value,
            )
            db.insert_call_site(
                conn,
                indexed_file_id=indexed_file_id,
                surface_id=surface_id,
                line_start=cs.line_start,
                line_end=cs.line_end,
                api_version=cs.api_version,
                value_binding=cs.value_binding,
                confidence=cs.confidence,
                extractor=cs.extractor,
            )
            stats.call_sites_written += 1

        stats.parsed += 1

    for stale_path in set(previous_hashes) - seen_paths:
        db.delete_indexed_file(conn, repository_id=repository_id, path=stale_path)
        stats.deleted += 1

    conn.commit()
    return stats

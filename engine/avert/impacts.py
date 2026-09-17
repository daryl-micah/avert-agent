"""Layer 2 change feed (SPEC §5.2): persisted change events joined to the
call sites they affect, through avert.join. The blast-radius statement is
built here so every consumer (dashboard, alert) says the same thing."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import psycopg

from avert.join import ImpactMatch, impacted_call_sites
from avert.models.change_event_schema import ChangeEvent, Provenance
from avert.models.impact_schema import Impact, ImpactReport, Match
from avert.models.surface_id_schema import SurfaceID


def load_change_events(conn: psycopg.Connection) -> list[tuple[int, ChangeEvent]]:
    rows = conn.execute(
        """
        SELECT e.id, e.change_type, e.severity, e.source, e.confidence, e.summary,
               e.announced_at, e.effective_at, e.applies_from, e.applies_to, e.detected_at,
               e.provenance,
               s.provider, s.resource, s.operation, s.field_path, s.value,
               r.provider, r.resource, r.operation, r.field_path, r.value
        FROM change_event e
        JOIN surface s ON s.id = e.surface_id
        LEFT JOIN surface r ON r.id = e.replacement_surface_id
        ORDER BY e.effective_at NULLS LAST, e.id
        """
    ).fetchall()
    events = []
    for row in rows:
        (
            event_id, change_type, severity, source, confidence, summary,
            announced_at, effective_at, applies_from, applies_to, detected_at, provenance,
        ) = row[:12]
        surface = SurfaceID(
            provider=row[12], resource=row[13], operation=row[14], field_path=row[15], value=row[16]
        )
        replacement = (
            SurfaceID(
                provider=row[17], resource=row[18], operation=row[19], field_path=row[20], value=row[21]
            )
            if row[17] is not None
            else None
        )
        if isinstance(provenance, str):
            provenance = json.loads(provenance)
        events.append((
            event_id,
            ChangeEvent(
                surface=surface, replacement_surface=replacement, change_type=change_type,
                severity=severity, source=source, confidence=confidence, summary=summary,
                announced_at=announced_at, effective_at=effective_at, applies_from=applies_from,
                applies_to=applies_to, detected_at=detected_at, provenance=Provenance(**provenance),
            ),
        ))
    return events


def build_impact_report(
    conn: psycopg.Connection,
    *,
    github_installation_id: int | None = None,
    now: datetime | None = None,
) -> ImpactReport:
    impacts = []
    for event_id, event in load_change_events(conn):
        matches = matches_for_event(conn, event_id, github_installation_id)
        impacts.append(Impact(event=event, blast_radius=blast_radius(matches), matches=matches))
    return ImpactReport(generated_at=now or datetime.now(UTC), impacts=impacts)


def blast_radius(matches: list[Match]) -> str:
    if not matches:
        return "no tracked call sites affected"
    files = {(m.repo, m.file_path) for m in matches}
    repos = {m.repo for m in matches}
    possible = sum(m.match_kind == "possible" for m in matches)
    statement = (
        f"{_count(len(matches), 'call site')} in {_count(len(files), 'file')} "
        f"across {_count(len(repos), 'repository', 'repositories')}"
    )
    return f"{statement} ({possible} possible)" if possible else statement


def matches_for_event(conn: psycopg.Connection, event_id: int, installation: int | None) -> list[Match]:
    repo_by_file = _repository_names(conn, installation)
    matches = []
    for match in impacted_call_sites(conn, event_id):
        repo = repo_by_file.get(match.call_site_id)
        if repo is None:
            continue
        matches.append(_to_match(repo, match))
    return matches


def _repository_names(conn: psycopg.Connection, installation: int | None) -> dict[int, str]:
    """call_site.id -> repository name, restricted to one installation when given."""
    rows = conn.execute(
        """
        SELECT cs.id, r.name
        FROM call_site cs
        JOIN indexed_file f ON f.id = cs.indexed_file_id
        JOIN repository r ON r.id = f.repository_id
        WHERE %(installation)s::bigint IS NULL OR r.github_installation_id = %(installation)s
        """,
        {"installation": installation},
    ).fetchall()
    return dict(rows)


def _to_match(repo: str, match: ImpactMatch) -> Match:
    return Match(
        repo=repo, file_path=match.file_path, line_start=match.line_start, line_end=match.line_end,
        match_kind=match.match_kind, confidence=match.confidence,
    )


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"

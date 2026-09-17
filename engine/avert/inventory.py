"""Layer 1 inventory (SPEC §5.1) read from Postgres.

Lifecycle status is the impact join's surface match (avert.join) applied per
call site, so the dashboard and impact alerts share one definition of
"affected". Nothing here is recomputed by the app.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import psycopg

from avert.join import MATCH_KIND_SQL, SURFACE_MATCH_SQL
from avert.models.inventory_schema import Dependency, Inventory, Location
from avert.models.surface_id_schema import SurfaceID

_STATUS_RANK = {"retired": 0, "retiring": 1, "unknown": 2, "current": 3}


def build_inventory(
    conn: psycopg.Connection,
    *,
    github_installation_id: int | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> Inventory:
    today = today or datetime.now(UTC).date()
    repositories = [
        row[0]
        for row in conn.execute(
            """
            SELECT name FROM repository
            WHERE %(installation)s::bigint IS NULL OR github_installation_id = %(installation)s
            ORDER BY name
            """,
            {"installation": github_installation_id},
        ).fetchall()
    ]
    rows = conn.execute(
        f"""
        SELECT r.name, f.path, cs.line_start, cs.confidence, cs.value_binding,
               ss.provider, ss.resource, ss.operation, ss.field_path, ss.value,
               m.match_kind, m.effective_at, m.replacement
        FROM call_site cs
        JOIN indexed_file f ON f.id = cs.indexed_file_id
        JOIN repository r ON r.id = f.repository_id
        JOIN surface ss ON ss.id = cs.surface_id
        LEFT JOIN LATERAL (
            SELECT {MATCH_KIND_SQL} AS match_kind, e.effective_at, rs.value AS replacement
            FROM change_event e
            JOIN surface es ON es.id = e.surface_id
            LEFT JOIN surface rs ON rs.id = e.replacement_surface_id
            WHERE {SURFACE_MATCH_SQL}
            ORDER BY e.effective_at NULLS LAST, e.id
            LIMIT 1
        ) m ON TRUE
        WHERE %(installation)s::bigint IS NULL OR r.github_installation_id = %(installation)s
        ORDER BY r.name, f.path, cs.line_start
        """,
        {"installation": github_installation_id},
    ).fetchall()

    dependencies: dict[tuple, Dependency] = {}
    attention = 0
    for (
        repo, path, line, confidence, value_binding,
        provider, resource, operation, field_path, value,
        match_kind, effective_at, replacement,
    ) in rows:
        status = _status(match_kind, effective_at, today)
        attention += status in {"retiring", "retired"}
        key = (provider, resource, operation, field_path, value, value_binding)
        location = Location(repo=repo, file_path=path, line=line, confidence=confidence)
        dependency = dependencies.get(key)
        if dependency is None:
            dependencies[key] = Dependency(
                surface=SurfaceID(
                    provider=provider, resource=resource, operation=operation,
                    field_path=field_path, value=value,
                ),
                value_binding=value_binding, status=status,
                effective_at=effective_at if status != "current" else None,
                replacement=replacement if status != "current" else None,
                locations=[location],
            )
        else:
            dependency.locations.append(location)

    ordered = sorted(
        dependencies.values(),
        key=lambda d: (_STATUS_RANK[d.status], d.surface.provider, d.surface.resource, d.surface.value or ""),
    )
    return Inventory(
        generated_at=now or datetime.now(UTC),
        repositories=repositories,
        providers=sorted({d.surface.provider for d in ordered}),
        call_site_count=len(rows),
        attention_count=attention,
        dependencies=ordered,
    )


def _status(match_kind: str | None, effective_at: date | None, today: date) -> str:
    if match_kind is None:
        return "current"
    if match_kind == "possible":
        return "unknown"
    return "retired" if effective_at is not None and effective_at <= today else "retiring"

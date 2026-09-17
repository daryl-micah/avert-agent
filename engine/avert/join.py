"""Impact join: SQL identity matching, never a model call."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class ImpactMatch:
    event_id: int
    call_site_id: int
    file_path: str
    line_start: int
    line_end: int
    match_kind: str  # definite | possible
    confidence: float


# The identity match between a change event's surface (es) and a call site's
# surface (ss). Shared with avert.inventory so the dashboard's lifecycle
# status can only ever disagree with an impact alert by a bug here.
SURFACE_MATCH_SQL = """
      es.provider = ss.provider
      AND es.resource = ss.resource
      AND es.operation IS NOT DISTINCT FROM ss.operation
      AND es.field_path IS NOT DISTINCT FROM ss.field_path
      AND (
        es.value IS NULL
        OR (cs.value_binding = 'literal' AND ss.value = es.value)
        OR cs.value_binding = 'dynamic'
      )
"""

MATCH_KIND_SQL = """
      CASE
        WHEN es.value IS NULL THEN 'definite'
        WHEN cs.value_binding = 'literal' AND ss.value = es.value THEN 'definite'
        WHEN cs.value_binding = 'dynamic' THEN 'possible'
      END
"""


def impacted_call_sites(conn: psycopg.Connection, event_id: int) -> list[ImpactMatch]:
    """Returns exact and dynamic impacts for one persisted event.

    Version-range filtering is intentionally absent for week two: its current
    model lifecycle records apply to every provider API version.
    """
    rows = conn.execute(
        f"""
        SELECT e.id, cs.id, f.path, cs.line_start, cs.line_end,
               {MATCH_KIND_SQL} AS match_kind,
               LEAST(e.confidence, cs.confidence) AS confidence
        FROM change_event e
        JOIN surface es ON es.id = e.surface_id
        JOIN call_site cs ON TRUE
        JOIN surface ss ON ss.id = cs.surface_id
        JOIN indexed_file f ON f.id = cs.indexed_file_id
        WHERE e.id = %s
          AND {SURFACE_MATCH_SQL}
        ORDER BY f.path, cs.line_start
        """,
        (event_id,),
    ).fetchall()
    return [ImpactMatch(*row) for row in rows]

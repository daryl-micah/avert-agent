"""Alert routing (SPEC §5.2): one webhook delivery per (change event,
repository) that has at least one affected call site, recorded in
alert_delivery so re-runs are silent."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

import psycopg

from avert.impacts import blast_radius, load_change_events, matches_for_event
from avert.models.impact_schema import Match

Sender = Callable[[str, dict], None]


@dataclass(frozen=True)
class AlertStats:
    delivered: int = 0
    skipped: int = 0


def post_json(url: str, payload: dict) -> None:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status >= 300:
            raise RuntimeError(f"webhook returned {response.status}")


def deliver_alerts(
    conn: psycopg.Connection,
    *,
    webhook_url: str,
    send: Sender = post_json,
    channel: str = "webhook",
) -> AlertStats:
    repository_ids = dict(conn.execute("SELECT name, id FROM repository").fetchall())
    delivered = skipped = 0
    for event_id, event in load_change_events(conn):
        by_repo: dict[str, list[Match]] = {}
        for match in matches_for_event(conn, event_id, None):
            by_repo.setdefault(match.repo, []).append(match)
        for repo, matches in sorted(by_repo.items()):
            already = conn.execute(
                """
                SELECT 1 FROM alert_delivery
                WHERE change_event_id = %s AND repository_id = %s AND channel = %s
                """,
                (event_id, repository_ids[repo], channel),
            ).fetchone()
            if already:
                skipped += 1
                continue
            send(webhook_url, _payload(repo, event, matches))
            conn.execute(
                """
                INSERT INTO alert_delivery (change_event_id, repository_id, channel)
                VALUES (%s, %s, %s)
                """,
                (event_id, repository_ids[repo], channel),
            )
            conn.commit()
            delivered += 1
    return AlertStats(delivered=delivered, skipped=skipped)


def _payload(repo: str, event, matches: list[Match]) -> dict:
    radius = blast_radius(matches)
    replacement = event.replacement_surface.value if event.replacement_surface else None
    effective = f" effective {event.effective_at}" if event.effective_at else ""
    action = f"Migrate to {replacement}." if replacement else "Review the affected call sites."
    text = (
        f"[{event.severity}] {repo}: {event.summary or event.change_type}{effective}. "
        f"{radius}. {action}"
    )
    return {
        "text": text,
        "repo": repo,
        "severity": event.severity,
        "change_type": event.change_type,
        "effective_at": str(event.effective_at) if event.effective_at else None,
        "surface": event.surface.model_dump(),
        "replacement": replacement,
        "blast_radius": radius,
        "matches": [m.model_dump() for m in matches],
        "source_url": str(event.provenance.source_url),
    }

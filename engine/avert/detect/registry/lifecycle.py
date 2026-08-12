from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from avert.models.change_event_schema import ChangeEvent, Provenance
from avert.models.surface_id_schema import SurfaceID

_REGISTRY_PATH = Path(__file__).with_name("models.json")


def load_events(path: Path = _REGISTRY_PATH, *, now: datetime | None = None) -> list[ChangeEvent]:
    """Loads committed lifecycle records as normalized change events."""
    detected_at = now or datetime.now(UTC)
    records = json.loads(path.read_text())
    events: list[ChangeEvent] = []
    for record in records:
        surface = SurfaceID(
            provider=record["provider"], resource=record["resource"], operation=record["operation"],
            field_path="model", value=record["model"],
        )
        replacement = SurfaceID(
            provider=record["provider"], resource=record["resource"], operation=record["operation"],
            field_path="model", value=record["replacement"],
        )
        events.append(ChangeEvent(
            surface=surface, replacement_surface=replacement, change_type="model_retired",
            severity="breaking", source="model_registry", confidence=1.0,
            summary=f'{record["model"]} retires; migrate to {record["replacement"]}.',
            announced_at=record["announced_at"], effective_at=record["effective_at"],
            detected_at=detected_at, provenance=Provenance(source_url=record["source_url"]),
        ))
    return events

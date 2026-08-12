from __future__ import annotations

import hashlib

from avert.models.change_event_schema import ChangeEvent


def fingerprint(event: ChangeEvent) -> str:
    """Stable ingestion key; updates to descriptive metadata replace the same event."""
    payload = "|".join(
        [
            event.source,
            event.change_type,
            event.surface.provider,
            event.surface.resource,
            event.surface.operation or "",
            event.surface.field_path or "",
            event.surface.value or "",
            str(event.effective_at or ""),
            str(event.provenance.source_url),
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()

from datetime import UTC, datetime

from avert.detect.events import fingerprint
from avert.detect.registry import load_events


def test_registry_emits_source_linked_model_events():
    events = load_events(now=datetime(2026, 8, 12, tzinfo=UTC))

    assert {event.surface.provider for event in events} == {"openai", "anthropic"}
    assert all(event.change_type == "model_retired" for event in events)
    assert all(event.replacement_surface is not None for event in events)
    assert len({fingerprint(event) for event in events}) == len(events)

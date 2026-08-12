from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from avert.models.change_event_schema import ChangeEvent, Provenance
from avert.models.surface_id_schema import SurfaceID

from . import python_surface, ts_surface
from .surface import PublicMember

_PACKAGE_PROVIDERS = {
    ("pypi", "openai"): "openai",
    ("npm", "openai"): "openai",
    ("pypi", "anthropic"): "anthropic",
    ("npm", "@anthropic-ai/sdk"): "anthropic",
}

_MEMBER_SURFACES = {
    "openai": {
        "chat.completions.create": ("chat.completions", "create"),
        "chat.completions.completions.create": ("chat.completions", "create"),
        "responses.create": ("responses", "create"),
    },
    "anthropic": {"messages.create": ("messages", "create")},
}


def diff_artifacts(
    *, ecosystem: str, package: str, from_path: Path, to_path: Path,
    from_version: str, to_version: str, source_url: str,
) -> list[ChangeEvent]:
    provider = _PACKAGE_PROVIDERS.get((ecosystem, package))
    if provider is None:
        raise ValueError(f"unsupported package: {ecosystem}:{package}")
    extractor = python_surface.extract if ecosystem == "pypi" else ts_surface.extract
    before = {member.path: member for member in extractor(from_path)}
    after = {member.path: member for member in extractor(to_path)}
    provenance = Provenance(
        source_url=source_url, package_ecosystem=ecosystem, package_name=package,
        from_version=from_version, to_version=to_version,
    )
    events: list[ChangeEvent] = []
    for path in sorted(before.keys() - after.keys()):
        events.extend(_event_for(provider, before[path], "surface_removed", provenance))
    for path in sorted(after.keys() - before.keys()):
        events.extend(_event_for(provider, after[path], "surface_added", provenance))
    for path in sorted(before.keys() & after.keys()):
        old, new = before[path], after[path]
        if old.signature != new.signature:
            events.extend(_event_for(provider, new, "type_changed", provenance))
        elif old.required is False and new.required is True:
            events.extend(_event_for(provider, new, "requiredness_changed", provenance))
    return events


def _event_for(provider: str, member: PublicMember, change_type: str, provenance: Provenance) -> list[ChangeEvent]:
    normalized = _surface_for_member(provider, member.path)
    if normalized is None:
        return []
    resource, operation = normalized
    breaking = change_type != "surface_added"
    return [ChangeEvent(
        surface=SurfaceID(provider=provider, resource=resource, operation=operation, field_path=None, value=None),
        change_type=change_type, severity="breaking" if breaking else "info", source="sdk_diff",
        confidence=1.0, summary=f"SDK {change_type.replace('_', ' ')}: {member.path}",
        detected_at=datetime.now(UTC), provenance=provenance,
    )]


def _surface_for_member(provider: str, path: str) -> tuple[str, str] | None:
    lower = path.lower()
    for suffix, surface in _MEMBER_SURFACES[provider].items():
        if lower.endswith(suffix):
            return surface
    return None

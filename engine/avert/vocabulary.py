"""Loads the controlled vocabulary (shared/vocabulary/providers.json, SPEC §6.1).

See docs/decisions/0001-vocabulary-placement.md for why this lives in shared/
and is loaded by both index/ and (later) detect/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_VOCAB_PATH = Path(__file__).resolve().parents[2] / "shared" / "vocabulary" / "providers.json"


@dataclass(frozen=True)
class SurfaceMatch:
    provider: str
    resource: str
    operation: str
    ambiguous: bool = False


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_VOCAB_PATH.read_text())


@lru_cache(maxsize=1)
def _resource_operation_index() -> dict[str, SurfaceMatch]:
    """Maps "resource.operation" -> SurfaceMatch.

    Resources are disjoint across the two hardcoded providers (SPEC §15), so a
    resource.operation suffix uniquely identifies a provider without needing
    import-graph analysis. Revisit this lookup (not just the vocabulary file)
    if a future provider shares a resource name with an existing one.
    """
    vocab = _load()
    ambiguous_resources = set(vocab.get("$ambiguous_resources", {}))
    index: dict[str, SurfaceMatch] = {}
    for provider, spec in vocab.items():
        if provider.startswith("$"):
            continue
        for resource, operations in spec["resources"].items():
            for operation in operations:
                key = f"{resource}.{operation}"
                if key in index:
                    raise ValueError(f"ambiguous resource.operation across providers: {key}")
                index[key] = SurfaceMatch(
                    provider=provider,
                    resource=resource,
                    operation=operation,
                    ambiguous=resource in ambiguous_resources,
                )
    return index


def match_callee(dotted_path: str) -> SurfaceMatch | None:
    """Longest resource.operation suffix of dotted_path that's in the
    vocabulary, e.g. "client.chat.completions.create" -> chat.completions/create.
    Returns None if no suffix matches (not a tracked call)."""
    parts = dotted_path.split(".")
    index = _resource_operation_index()
    for start in range(len(parts) - 1):
        suffix = ".".join(parts[start:])
        if suffix in index:
            return index[suffix]
    return None

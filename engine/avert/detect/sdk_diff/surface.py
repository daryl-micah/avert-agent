from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class PublicMember:
    path: str
    kind: str
    signature: str
    required: bool | None = None

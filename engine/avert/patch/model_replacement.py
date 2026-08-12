"""Read-only, guarded patches for literal model lifecycle replacements."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path

from avert.index.parse.extractor import locate_literal_model_argument
from avert.models.call_site_schema import CallSite
from avert.models.change_event_schema import ChangeEvent


@dataclass(frozen=True)
class PatchProposal:
    file_path: str
    line_start: int
    original_hash: str
    old_model: str
    new_model: str
    start_byte: int
    end_byte: int
    diff: str

    def patched_source(self, repo_root: Path) -> bytes:
        """Returns patched bytes after confirming the source has not changed."""
        source = _source_for(repo_root, self.file_path)
        if hashlib.sha256(source).hexdigest() != self.original_hash:
            raise ValueError(f"source changed since indexing: {self.file_path}")
        if source[self.start_byte : self.end_byte] != self.old_model.encode():
            raise ValueError(f"model literal changed since proposal: {self.file_path}")
        return source[: self.start_byte] + self.new_model.encode() + source[self.end_byte :]


def generate_model_replacement(
    repo_root: Path, event: ChangeEvent, call_site: CallSite
) -> PatchProposal | None:
    """Proposes one exact literal-model replacement, or declines safely.

    Dynamic values, stale files, unmatched events, and unsupported change
    types deliberately return ``None``. This layer never writes the repo.
    """
    if (
        event.change_type not in {"model_deprecated", "model_retired"}
        or event.replacement_surface is None
        or call_site.value_binding != "literal"
        or call_site.surface != event.surface
        or event.replacement_surface.value is None
    ):
        return None

    source = _source_for(repo_root, call_site.file_path)
    original_hash = hashlib.sha256(source).hexdigest()
    if original_hash != call_site.file_content_hash:
        return None

    value_range = locate_literal_model_argument(
        file_path=call_site.file_path, language=call_site.language, source=source, call_site=call_site
    )
    if value_range is None:
        return None
    start_byte, end_byte = value_range
    old_model = call_site.surface.value
    assert old_model is not None
    if source[start_byte:end_byte] != old_model.encode():
        return None

    new_model = event.replacement_surface.value
    patched = source[:start_byte] + new_model.encode() + source[end_byte:]
    diff = "".join(
        difflib.unified_diff(
            source.decode().splitlines(keepends=True),
            patched.decode().splitlines(keepends=True),
            fromfile=f"a/{call_site.file_path}", tofile=f"b/{call_site.file_path}",
        )
    )
    return PatchProposal(
        file_path=call_site.file_path,
        line_start=call_site.line_start,
        original_hash=original_hash,
        old_model=old_model,
        new_model=new_model,
        start_byte=start_byte,
        end_byte=end_byte,
        diff=diff,
    )


def _source_for(repo_root: Path, file_path: str) -> bytes:
    root = repo_root.resolve()
    path = (root / file_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"call site is outside repository: {file_path}")
    return path.read_bytes()

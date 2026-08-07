from __future__ import annotations

from pathlib import Path

from avert.index.candidates import find_candidates
from avert.index.parse import extract_call_sites
from avert.models.call_site_schema import CallSite


def run_index(root: Path, *, repo: str, commit: str | None = None) -> list[CallSite]:
    """Runs the full static funnel (SPEC §8.1 steps 1-2: ripgrep candidates,
    then tree-sitter extraction) against a repository root."""
    root = root.resolve()
    call_sites: list[CallSite] = []
    for candidate in find_candidates(root):
        source = candidate.path.read_bytes()
        rel_path = str(candidate.path.relative_to(root))
        call_sites.extend(
            extract_call_sites(
                file_path=rel_path,
                language=candidate.language,
                source=source,
                repo=repo,
                commit_sha=commit,
            )
        )
    return call_sites


__all__ = ["extract_call_sites", "find_candidates", "run_index"]

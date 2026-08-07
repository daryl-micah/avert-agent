"""Candidate file identification via ripgrep (SPEC §8.1 step 1).

Cheap, free pre-filter: reduces a whole repository to the files worth
running tree-sitter over. Patterns are markers (SDK names, method chains,
API hosts), not full call syntax — precision is parse/extractor.py's job.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

CANDIDATE_PATTERNS = [
    r"\bopenai\b",
    r"\bOpenAI\b",
    r"\banthropic\b",
    r"\bAnthropic\b",
    r"chat\.completions",
    r"messages\.(create|stream|count_tokens)",
    r"responses\.create",
    r"api\.openai\.com",
    r"api\.anthropic\.com",
]

LANGUAGE_GLOBS: dict[str, list[str]] = {
    "python": ["*.py"],
    "typescript": ["*.ts", "*.tsx"],
}

EXCLUDE_GLOBS = [
    "!node_modules/**",
    "!.venv/**",
    "!venv/**",
    "!vendor/**",
    "!dist/**",
    "!build/**",
    "!.git/**",
]


@dataclass(frozen=True)
class CandidateFile:
    path: Path
    language: str


def find_candidates(root: Path) -> list[CandidateFile]:
    """Runs ripgrep once per language glob, returns files with at least one
    marker hit. Respects .gitignore automatically (ripgrep default)."""
    results: dict[Path, str] = {}
    for language, globs in LANGUAGE_GLOBS.items():
        for glob in globs:
            for path in _rg_files(root, glob):
                results.setdefault(path, language)
    return [CandidateFile(path=p, language=lang) for p, lang in sorted(results.items())]


def _rg_files(root: Path, glob: str) -> list[Path]:
    pattern = "|".join(CANDIDATE_PATTERNS)
    cmd = ["rg", "--json", "-e", pattern, "--glob", glob]
    for exclude in EXCLUDE_GLOBS:
        cmd += ["--glob", exclude]
    cmd.append(".")

    # --glob patterns are resolved relative to the process cwd, not the
    # search-root argument — run inside root so "!node_modules/**" etc.
    # actually match.
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=root, check=False)
    # ripgrep exits 1 when there are simply no matches — not an error.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"ripgrep failed ({proc.returncode}): {proc.stderr}")

    paths: set[Path] = set()
    for line in proc.stdout.splitlines():
        if not line:
            continue
        event = json.loads(line)
        if event.get("type") == "match":
            rel = event["data"]["path"]["text"]
            paths.add((root / rel).resolve())
    return sorted(paths)

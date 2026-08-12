"""Ephemeral verification for deterministic remediation proposals."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from avert.index import run_index
from avert.models.change_event_schema import ChangeEvent
from avert.patch.model_replacement import PatchProposal

_COPY_IGNORES = shutil.ignore_patterns(".git", ".venv", "node_modules", "__pycache__")
_MAX_OUTPUT = 4_000


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class VerificationEvidence:
    proposal: PatchProposal
    checks: tuple[VerificationCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2) + "\n"


def verify_proposal(
    repo_root: Path,
    event: ChangeEvent,
    proposal: PatchProposal,
    *,
    commands: Sequence[Sequence[str]] = (),
    timeout_seconds: int = 60,
) -> VerificationEvidence:
    """Verifies a proposal in a disposable copy of ``repo_root``.

    Commands are argv sequences and run without a shell. A command's output is
    bounded in the returned evidence; the original checkout is never changed.
    """
    try:
        patched_source = proposal.patched_source(repo_root)
    except ValueError as exc:
        return VerificationEvidence(
            proposal=proposal,
            checks=(VerificationCheck("patch_application", False, str(exc)),),
        )

    with tempfile.TemporaryDirectory(prefix="avert-verify-") as temp_dir:
        workspace = Path(temp_dir) / "repo"
        shutil.copytree(repo_root, workspace, ignore=_COPY_IGNORES)
        target = _workspace_path(workspace, proposal.file_path)
        target.write_bytes(patched_source)

        checks = [VerificationCheck("patch_application", True, "applied in temporary workspace")]
        checks.append(_replacement_check(workspace, event, proposal))
        if not all(check.passed for check in checks):
            return VerificationEvidence(proposal=proposal, checks=tuple(checks))
        checks.extend(_run_command(workspace, command, timeout_seconds) for command in commands)
        return VerificationEvidence(proposal=proposal, checks=tuple(checks))


def _replacement_check(
    workspace: Path, event: ChangeEvent, proposal: PatchProposal
) -> VerificationCheck:
    replacement = event.replacement_surface
    if replacement is None:
        return VerificationCheck("replacement_index", False, "event has no replacement surface")
    try:
        sites = run_index(workspace, repo="verification")
    except (OSError, RuntimeError, ValueError) as exc:
        return VerificationCheck("replacement_index", False, f"re-indexing failed: {exc}")
    matches = [
        site for site in sites
        if site.file_path == proposal.file_path
        and site.line_start == proposal.line_start
        and site.surface == replacement
    ]
    if not matches:
        return VerificationCheck("replacement_index", False, "replacement was not indexed at patched call site")
    return VerificationCheck("replacement_index", True, "replacement indexed at patched call site")


def _run_command(workspace: Path, command: Sequence[str], timeout_seconds: int) -> VerificationCheck:
    if not command:
        return VerificationCheck("command", False, "empty command")
    name = f"command:{command[0]}"
    try:
        result = subprocess.run(
            command, cwd=workspace, capture_output=True, text=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired:
        return VerificationCheck(name, False, f"timed out after {timeout_seconds}s")
    except OSError as exc:
        return VerificationCheck(name, False, str(exc))
    output = (result.stdout + result.stderr).strip()
    if len(output) > _MAX_OUTPUT:
        output = output[:_MAX_OUTPUT] + "\n[output truncated]"
    detail = output or f"exit code {result.returncode}"
    return VerificationCheck(name, result.returncode == 0, detail)


def _workspace_path(workspace: Path, file_path: str) -> Path:
    path = (workspace / file_path).resolve()
    if not path.is_relative_to(workspace):
        raise ValueError(f"proposal is outside repository: {file_path}")
    return path

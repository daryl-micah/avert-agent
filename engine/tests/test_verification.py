import sys
from pathlib import Path

from avert.detect.registry import load_events
from avert.index.parse import extract_call_sites
from avert.patch import generate_model_replacement
from avert.verify import verify_proposal


def _event():
    return next(event for event in load_events() if event.surface.provider == "openai")


def _proposal(repo_root: Path):
    source_path = repo_root / "src" / "llm.py"
    source_path.parent.mkdir()
    source_path.write_text('client.chat.completions.create(model="gpt-4-0613", messages=[])\n')
    site = extract_call_sites(
        file_path="src/llm.py", language="python", source=source_path.read_bytes(),
        repo="acme/widgets", commit_sha="deadbeef",
    )[0]
    proposal = generate_model_replacement(repo_root, _event(), site)
    assert proposal is not None
    return proposal


def test_verification_applies_only_in_temporary_workspace(tmp_path):
    proposal = _proposal(tmp_path)

    evidence = verify_proposal(
        tmp_path, _event(), proposal,
        commands=[(sys.executable, "-c", "from pathlib import Path; assert 'gpt-5.6-sol' in Path('src/llm.py').read_text()")],
    )

    assert evidence.passed
    assert [check.name for check in evidence.checks] == [
        "patch_application", "replacement_index", f"command:{sys.executable}",
    ]
    assert "gpt-4-0613" in (tmp_path / "src" / "llm.py").read_text()
    assert '"checks"' in evidence.to_json()


def test_verification_records_failing_commands(tmp_path):
    proposal = _proposal(tmp_path)

    evidence = verify_proposal(tmp_path, _event(), proposal, commands=[(sys.executable, "-c", "raise SystemExit(3)")])

    assert not evidence.passed
    assert evidence.checks[-1].name == f"command:{sys.executable}"
    assert evidence.checks[-1].detail == "exit code 3"


def test_verification_stops_when_source_has_changed(tmp_path):
    proposal = _proposal(tmp_path)
    (tmp_path / "src" / "llm.py").write_text('client.chat.completions.create(model="gpt-4o", messages=[])\n')

    evidence = verify_proposal(tmp_path, _event(), proposal)

    assert not evidence.passed
    assert evidence.checks == (evidence.checks[0],)
    assert evidence.checks[0].name == "patch_application"

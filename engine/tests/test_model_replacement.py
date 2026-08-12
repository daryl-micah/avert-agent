from pathlib import Path

import pytest

from avert.detect.registry import load_events
from avert.index.parse import extract_call_sites
from avert.patch import generate_model_replacement


def _event():
    return next(event for event in load_events() if event.surface.provider == "openai")


def _site(path: Path, language: str):
    source = path.read_bytes()
    return extract_call_sites(
        file_path=str(path.relative_to(path.parents[1])), language=language, source=source,
        repo="acme/widgets", commit_sha="deadbeef",
    )[0]


def test_python_literal_patch_preserves_source_checkout(tmp_path):
    source_path = tmp_path / "src" / "llm.py"
    source_path.parent.mkdir()
    source_path.write_text(
        'client.chat.completions.create(model="gpt-4-0613", messages=[])\n'
        '# gpt-4-0613 remains an unrelated comment\n'
    )
    site = _site(source_path, "python")

    proposal = generate_model_replacement(tmp_path, _event(), site)

    assert proposal is not None
    assert source_path.read_text().count("gpt-4-0613") == 2
    assert 'model="gpt-5.6-sol"' in proposal.patched_source(tmp_path).decode()
    assert "# gpt-4-0613 remains" in proposal.patched_source(tmp_path).decode()
    assert '-client.chat.completions.create(model="gpt-4-0613", messages=[])' in proposal.diff
    assert '+client.chat.completions.create(model="gpt-5.6-sol", messages=[])' in proposal.diff


def test_typescript_template_literal_patch_preserves_delimiter(tmp_path):
    source_path = tmp_path / "src" / "llm.ts"
    source_path.parent.mkdir()
    source_path.write_text('client.chat.completions.create({ model: `gpt-4-0613` });\n')
    site = _site(source_path, "typescript")

    proposal = generate_model_replacement(tmp_path, _event(), site)

    assert proposal is not None
    assert "model: `gpt-5.6-sol`" in proposal.patched_source(tmp_path).decode()


def test_dynamic_and_stale_call_sites_are_declined(tmp_path):
    source_path = tmp_path / "src" / "llm.py"
    source_path.parent.mkdir()
    source_path.write_text("client.chat.completions.create(model=model_name, messages=[])\n")
    dynamic_site = _site(source_path, "python")
    assert generate_model_replacement(tmp_path, _event(), dynamic_site) is None

    source_path.write_text('client.chat.completions.create(model="gpt-4-0613", messages=[])\n')
    stale_site = _site(source_path, "python")
    source_path.write_text('client.chat.completions.create(model="gpt-4o", messages=[])\n')
    assert generate_model_replacement(tmp_path, _event(), stale_site) is None


def test_same_line_model_calls_are_declined_as_ambiguous(tmp_path):
    source_path = tmp_path / "src" / "llm.py"
    source_path.parent.mkdir()
    source_path.write_text(
        'first = client.chat.completions.create(model="gpt-4-0613", messages=[]); '
        'second = client.chat.completions.create(model="gpt-4-0613", messages=[])\n'
    )
    site = _site(source_path, "python")

    assert generate_model_replacement(tmp_path, _event(), site) is None


def test_proposal_refuses_to_apply_after_source_changes(tmp_path):
    source_path = tmp_path / "src" / "llm.py"
    source_path.parent.mkdir()
    source_path.write_text('client.chat.completions.create(model="gpt-4-0613", messages=[])\n')
    proposal = generate_model_replacement(tmp_path, _event(), _site(source_path, "python"))
    assert proposal is not None

    source_path.write_text('client.chat.completions.create(model="gpt-4o", messages=[])\n')
    with pytest.raises(ValueError, match="source changed since indexing"):
        proposal.patched_source(tmp_path)

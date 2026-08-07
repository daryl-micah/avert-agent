from pathlib import Path

from avert.index.candidates import find_candidates


def test_finds_python_and_typescript_candidates(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "llm.py").write_text(
        'client.chat.completions.create(model="gpt-4-0613")\n'
    )
    (tmp_path / "src" / "unrelated.py").write_text("print('hello')\n")
    (tmp_path / "src" / "llm.ts").write_text(
        'client.chat.completions.create({ model: "gpt-4-0613" });\n'
    )

    candidates = find_candidates(tmp_path)
    matched_names = {c.path.name for c in candidates}

    assert "llm.py" in matched_names
    assert "llm.ts" in matched_names
    assert "unrelated.py" not in matched_names


def test_excludes_vendored_directories(tmp_path: Path):
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.ts").write_text(
        'client.chat.completions.create({ model: "gpt-4-0613" });\n'
    )

    candidates = find_candidates(tmp_path)
    assert candidates == []

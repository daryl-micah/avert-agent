import json
import sys

from avert.cli import main
from avert.detect.registry import load_events


def test_remediate_writes_verified_diff_and_evidence(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = repo / "src" / "llm.py"
    source.write_text('client.chat.completions.create(model="gpt-4-0613", messages=[])\n')
    event_path = tmp_path / "event.json"
    event_path.write_text(next(event for event in load_events() if event.surface.provider == "openai").model_dump_json())
    out_dir = tmp_path / "out"
    check = f'{sys.executable} -c "from pathlib import Path; assert \'gpt-5.6-sol\' in Path(\'src/llm.py\').read_text()"'
    monkeypatch.setattr(
        sys, "argv",
        ["avert", "remediate", str(repo), "--event", str(event_path), "--out", str(out_dir), "--check", check],
    )

    assert main() == 0

    assert "1 patch proposals, 1 verified" in capsys.readouterr().out
    assert "gpt-5.6-sol" in (out_dir / "src__llm.py.L1.diff").read_text()
    evidence = json.loads((out_dir / "src__llm.py.L1.evidence.json").read_text())
    assert all(check["passed"] for check in evidence["checks"])
    assert "gpt-4-0613" in source.read_text()

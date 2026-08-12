import json
import sys

import pytest

from avert.cli import main
from avert.experiment3 import format_report, run_experiment


def test_historical_model_cases_are_mechanically_verified():
    report = run_experiment()

    assert len(report.cases) == 10
    assert report.all_verified
    assert report.graded_cases == 0
    assert report.merge_as_is_rate is None
    assert "10/10 cases mechanically verified" in format_report(report)


def test_manual_grades_control_merge_as_is_rate(tmp_path):
    grades_path = tmp_path / "grades.json"
    grades_path.write_text(json.dumps({
        "openai-gpt-4-0613": "merge_as_is",
        "anthropic-claude-3-opus": "wrong",
        "anthropic-sonnet-3-5-june": "merge_as_is",
        "anthropic-sonnet-3-5-october": "merge_as_is",
        "anthropic-sonnet-3-7": "merge_as_is",
        "anthropic-haiku-3-5": "merge_as_is",
        "anthropic-haiku-3": "merge_as_is",
        "anthropic-sonnet-4": "merge_as_is",
        "anthropic-opus-4": "merge_as_is",
        "anthropic-opus-4-1": "merge_as_is",
    }))

    report = run_experiment(grades_path=grades_path)

    assert report.merge_as_is_rate == 0.9
    assert "merge-as-is rate: 90%" in format_report(report)


def test_invalid_manual_grade_is_rejected(tmp_path):
    grades_path = tmp_path / "grades.json"
    grades_path.write_text(json.dumps({"openai-gpt-4-0613": "looks-good"}))

    with pytest.raises(ValueError, match="grades must map"):
        run_experiment(grades_path=grades_path)


def test_experiment_cli_writes_pending_grade_report(tmp_path, monkeypatch, capsys):
    out_path = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["avert", "experiment3", "--out", str(out_path)])

    assert main() == 0

    report = json.loads(out_path.read_text())
    assert report["graded_cases"] == 0
    assert report["merge_as_is_rate"] is None
    assert "merge-as-is rate: pending" in capsys.readouterr().out

"""Experiment 2 (SPEC §15): the extractor's precision/recall floor.

Week 1 has no classify.py (STRUCTURE §5) — this measures the static funnel
(ripgrep + tree-sitter) alone, steps 1-2 of SPEC §8.1's five-step funnel.
"typed_sdk" is what that floor should get right. The other four fixtures
are SPEC §8.3's named hard classes and are expected to score zero recall
at this stage — each assertion below is a deliberate regression lock, not
a bug: it documents exactly what the LLM tiers (steps 3-5) still need to
cover, and will need a conscious update if a later change starts catching
one of these classes.
"""

from pathlib import Path

from avert.index import run_index
from avert.score import load_labels, score

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
GROUND_TRUTH_DIR = Path(__file__).parent.parent / "ground_truth"


def _score_fixture(name: str):
    root = FIXTURES_DIR / name
    predictions = run_index(root, repo=name)
    labels = load_labels(GROUND_TRUTH_DIR / f"{name}.jsonl")
    return score(labels, predictions)


def test_typed_sdk_is_fully_recovered():
    report = _score_fixture("typed_sdk")
    assert report.overall.recall == 1.0
    assert report.overall.precision == 1.0


def test_raw_fetch_is_a_known_miss():
    report = _score_fixture("raw_fetch")
    assert report.overall.recall == 0.0
    assert report.overall.false_positives == 0


def test_config_assembled_is_a_known_miss():
    report = _score_fixture("config_assembled")
    assert report.overall.recall == 0.0
    assert report.overall.false_positives == 0


def test_yaml_literal_is_a_known_miss():
    report = _score_fixture("yaml_literal")
    assert report.overall.recall == 0.0
    assert report.overall.false_positives == 0


def test_vendored_is_a_known_miss():
    report = _score_fixture("vendored")
    assert report.overall.recall == 0.0
    assert report.overall.false_positives == 0


def test_typed_sdk_value_binding_breakdown():
    report = _score_fixture("typed_sdk")
    assert report.by_value_binding["literal"].true_positives == 3
    assert report.by_value_binding["dynamic"].true_positives == 2
    assert report.by_value_binding["absent"].true_positives == 1

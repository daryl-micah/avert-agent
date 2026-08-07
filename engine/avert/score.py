"""Experiment-2 scoring: precision and recall against hand-labelled ground
truth (SPEC §15 experiment 2; STRUCTURE §5 — measure both, not recall alone).

A Label is deliberately its own format, not a CallSite: ground truth
includes cases the extractor is known not to detect (SPEC §8.3's hard
classes — raw fetch, config-assembled endpoints, YAML literals, vendored
code), some of which aren't even Python or TypeScript source, so they can't
be expressed as a CallSite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from avert.models.call_site_schema import CallSite


@dataclass(frozen=True)
class Label:
    file_path: str
    line: int
    difficulty: str
    expect_detected: bool
    provider: str | None = None
    resource: str | None = None
    operation: str | None = None
    field_path: str | None = None
    value: str | None = None
    value_binding: str | None = None
    note: str | None = None


def load_labels(path: Path) -> list[Label]:
    labels = []
    for line in path.read_text().splitlines():
        if line.strip():
            labels.append(Label(**json.loads(line)))
    return labels


def load_predictions(path: Path) -> list[CallSite]:
    predictions = []
    for line in path.read_text().splitlines():
        if line.strip():
            predictions.append(CallSite.model_validate_json(line))
    return predictions


def label_template(cs: CallSite) -> str:
    """A label pre-filled from a prediction — expect_detected defaults to
    true. Reviewer flips it to false for anything that isn't a real API
    call and hand-adds a line for anything the extractor missed."""
    label = Label(
        file_path=cs.file_path,
        line=cs.line_start,
        difficulty="unclassified",
        expect_detected=True,
        provider=cs.surface.provider,
        resource=cs.surface.resource,
        operation=cs.surface.operation,
        field_path=cs.surface.field_path,
        value=cs.surface.value,
        value_binding=cs.value_binding,
    )
    return json.dumps(label.__dict__)


def _label_matches(label: Label, cs: CallSite) -> bool:
    if label.file_path != cs.file_path:
        return False
    if not (cs.line_start <= label.line <= cs.line_end):
        return False
    if label.provider and label.provider != cs.surface.provider:
        return False
    if label.resource and label.resource != cs.surface.resource:
        return False
    if label.operation and label.operation != cs.surface.operation:
        return False
    if label.field_path and label.field_path != cs.surface.field_path:
        return False
    return not (label.value is not None and label.value != cs.surface.value)


@dataclass
class ScoreBucket:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float | None:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else None

    @property
    def recall(self) -> float | None:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)


@dataclass
class ScoreReport:
    overall: ScoreBucket = field(default_factory=ScoreBucket)
    by_difficulty: dict[str, ScoreBucket] = field(default_factory=dict)
    by_language: dict[str, ScoreBucket] = field(default_factory=dict)
    by_value_binding: dict[str, ScoreBucket] = field(default_factory=dict)
    unmatched_predictions: list[CallSite] = field(default_factory=list)
    missed_labels: list[Label] = field(default_factory=list)


def score(labels: list[Label], predictions: list[CallSite]) -> ScoreReport:
    report = ScoreReport()
    matched: set[int] = set()

    for label in (label for label in labels if label.expect_detected):
        match_idx = next(
            (i for i, cs in enumerate(predictions) if i not in matched and _label_matches(label, cs)),
            None,
        )
        difficulty_bucket = report.by_difficulty.setdefault(label.difficulty, ScoreBucket())
        if match_idx is not None:
            matched.add(match_idx)
            cs = predictions[match_idx]
            report.overall.true_positives += 1
            difficulty_bucket.true_positives += 1
            report.by_language.setdefault(cs.language, ScoreBucket()).true_positives += 1
            report.by_value_binding.setdefault(cs.value_binding, ScoreBucket()).true_positives += 1
        else:
            report.overall.false_negatives += 1
            difficulty_bucket.false_negatives += 1
            report.missed_labels.append(label)

    # by_difficulty has no false-positive counterpart: difficulty is a
    # property of a label, and an unmatched prediction isn't tied to one.
    for i, cs in enumerate(predictions):
        if i in matched:
            continue
        report.overall.false_positives += 1
        report.by_language.setdefault(cs.language, ScoreBucket()).false_positives += 1
        report.by_value_binding.setdefault(cs.value_binding, ScoreBucket()).false_positives += 1
        report.unmatched_predictions.append(cs)

    return report


def _fmt(bucket: ScoreBucket) -> str:
    def pct(x: float | None) -> str:
        return f"{x:.0%}" if x is not None else "n/a"

    return (
        f"precision={pct(bucket.precision)} recall={pct(bucket.recall)} f1={pct(bucket.f1)} "
        f"(tp={bucket.true_positives} fp={bucket.false_positives} fn={bucket.false_negatives})"
    )


def format_report(report: ScoreReport) -> str:
    lines = [f"overall: {_fmt(report.overall)}", "", "by difficulty:"]
    for difficulty, bucket in sorted(report.by_difficulty.items()):
        lines.append(f"  {difficulty}: {_fmt(bucket)}")
    lines.append("")
    lines.append("by language:")
    for language, bucket in sorted(report.by_language.items()):
        lines.append(f"  {language}: {_fmt(bucket)}")
    lines.append("")
    lines.append("by value_binding:")
    for binding, bucket in sorted(report.by_value_binding.items()):
        lines.append(f"  {binding}: {_fmt(bucket)}")
    if report.missed_labels:
        lines.append("")
        lines.append("missed (false negatives):")
        for label in report.missed_labels:
            lines.append(f"  {label.file_path}:{label.line} [{label.difficulty}] {label.note or ''}")
    if report.unmatched_predictions:
        lines.append("")
        lines.append("unexpected (false positives):")
        for cs in report.unmatched_predictions:
            lines.append(f"  {cs.file_path}:{cs.line_start} {cs.surface.provider}/{cs.surface.resource}")
    return "\n".join(lines)

"""Week-three historical model-deprecation remediation experiment."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from avert.detect.registry import load_events
from avert.index import run_index
from avert.patch import generate_model_replacement
from avert.verify import verify_proposal

_DEFAULT_CASES = Path(__file__).parents[1] / "tests" / "fixtures" / "experiment3" / "cases.json"
_VALID_GRADES = {"merge_as_is", "merge_with_edits", "wrong"}


@dataclass(frozen=True)
class ExperimentCaseResult:
    case_id: str
    source_url: str
    proposals: int
    verified: bool
    grade: str | None


@dataclass(frozen=True)
class ExperimentReport:
    cases: tuple[ExperimentCaseResult, ...]

    @property
    def all_verified(self) -> bool:
        return all(case.verified for case in self.cases)

    @property
    def graded_cases(self) -> int:
        return sum(case.grade is not None for case in self.cases)

    @property
    def merge_as_is_rate(self) -> float | None:
        if self.graded_cases != len(self.cases):
            return None
        return sum(case.grade == "merge_as_is" for case in self.cases) / len(self.cases)

    def to_json(self) -> str:
        payload = asdict(self)
        payload["all_verified"] = self.all_verified
        payload["graded_cases"] = self.graded_cases
        payload["merge_as_is_rate"] = self.merge_as_is_rate
        return json.dumps(payload, indent=2) + "\n"


def run_experiment(
    cases_path: Path | None = None, *, grades_path: Path | None = None
) -> ExperimentReport:
    cases_path = cases_path or _DEFAULT_CASES
    cases = json.loads(cases_path.read_text())
    grades = _load_grades(grades_path) if grades_path else {}
    results: list[ExperimentCaseResult] = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="avert-experiment3-") as temp_dir:
            root = Path(temp_dir)
            file_path = Path(case["file_path"])
            target = root / file_path
            target.parent.mkdir(parents=True)
            target.write_text(case["source"])
            event = _event_for(case)
            proposals = [
                proposal
                for call_site in run_index(root, repo=f"experiment3/{case['id']}")
                if (proposal := generate_model_replacement(root, event, call_site)) is not None
            ]
            evidence = [verify_proposal(root, event, proposal) for proposal in proposals]
            results.append(
                ExperimentCaseResult(
                    case_id=case["id"], source_url=str(event.provenance.source_url), proposals=len(proposals),
                    verified=len(proposals) == 1 and all(item.passed for item in evidence),
                    grade=grades.get(case["id"]),
                )
            )
    return ExperimentReport(cases=tuple(results))


def format_report(report: ExperimentReport) -> str:
    verified = sum(case.verified for case in report.cases)
    rate = "pending" if report.merge_as_is_rate is None else f"{report.merge_as_is_rate:.0%}"
    return (
        f"{verified}/{len(report.cases)} cases mechanically verified\n"
        f"{report.graded_cases}/{len(report.cases)} cases manually graded\n"
        f"merge-as-is rate: {rate}"
    )


def _event_for(case: dict):
    matches = [
        event for event in load_events()
        if event.surface.provider == case["provider"] and event.surface.value == case["model"]
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one registry event for experiment case {case['id']}")
    return matches[0]


def _load_grades(path: Path) -> dict[str, str]:
    grades = json.loads(path.read_text())
    if not isinstance(grades, dict) or not all(grade in _VALID_GRADES for grade in grades.values()):
        raise ValueError("grades must map case IDs to merge_as_is, merge_with_edits, or wrong")
    return grades

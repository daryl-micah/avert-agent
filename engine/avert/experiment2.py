"""Experiment 2 (SPEC §15): the extractor against real repositories.

The fixture harness in tests/harness/ measures the static funnel on synthetic
files. This runs the same funnel over a pinned corpus of public repositories
so the recall number the decision rule needs (<85% kills the inventory
product) comes from real code. Predictions and a label template are written
per repository; a repository is scored only once a reviewer has committed
its labels.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from avert.index import run_index
from avert.models.call_site_schema import CallSite
from avert.score import ScoreBucket, label_template, load_labels, score

_DEFAULT_CORPUS = Path(__file__).parents[1] / "tests" / "fixtures" / "experiment2" / "corpus.json"


@dataclass(frozen=True)
class CorpusEntry:
    repo: str
    url: str
    commit: str


@dataclass(frozen=True)
class RepositoryResult:
    repo: str
    commit: str
    call_sites: int
    by_value_binding: dict[str, int]
    labelled: bool
    precision: float | None
    recall: float | None
    error: str | None = None


@dataclass(frozen=True)
class CorpusReport:
    repositories: tuple[RepositoryResult, ...]
    overall: ScoreBucket

    def to_json(self) -> str:
        payload = {
            "repositories": [asdict(r) for r in self.repositories],
            "labelled_repositories": sum(r.labelled for r in self.repositories),
            "precision": self.overall.precision,
            "recall": self.overall.recall,
        }
        return json.dumps(payload, indent=2) + "\n"


def load_corpus(path: Path | None = None) -> list[CorpusEntry]:
    entries = json.loads((path or _DEFAULT_CORPUS).read_text())
    return [CorpusEntry(**entry) for entry in entries]


def fetch_pinned(entry: CorpusEntry, dest: Path) -> None:
    """Fetches exactly one commit: no history, no other refs."""
    dest.mkdir(parents=True)
    for argv in (
        ["git", "init", "-q"],
        ["git", "remote", "add", "origin", entry.url],
        ["git", "fetch", "-q", "--depth", "1", "origin", entry.commit],
        ["git", "checkout", "-q", "FETCH_HEAD"],
    ):
        subprocess.run(argv, cwd=dest, check=True, capture_output=True, text=True)


def run_corpus(
    entries: list[CorpusEntry], *, out_dir: Path, labels_dir: Path | None = None
) -> CorpusReport:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[RepositoryResult] = []
    overall = ScoreBucket()
    for entry in entries:
        stem = entry.repo.replace("/", "__")
        try:
            call_sites = _index_pinned(entry)
        except subprocess.CalledProcessError as exc:
            results.append(_failed(entry, f"git failed: {exc.stderr.strip()}"))
            continue
        except (OSError, RuntimeError, ValueError) as exc:
            results.append(_failed(entry, str(exc)))
            continue

        (out_dir / f"{stem}.predictions.jsonl").write_text(
            "".join(cs.model_dump_json() + "\n" for cs in call_sites)
        )
        labels_path = (labels_dir or out_dir) / f"{stem}.labels.jsonl"
        precision = recall = None
        labelled = labels_path.exists()
        if labelled:
            report = score(load_labels(labels_path), call_sites)
            precision, recall = report.overall.precision, report.overall.recall
            overall.true_positives += report.overall.true_positives
            overall.false_positives += report.overall.false_positives
            overall.false_negatives += report.overall.false_negatives
        else:
            (out_dir / f"{stem}.labels.jsonl").write_text(
                "".join(label_template(cs) + "\n" for cs in call_sites)
            )

        bindings: dict[str, int] = {}
        for cs in call_sites:
            bindings[cs.value_binding] = bindings.get(cs.value_binding, 0) + 1
        results.append(
            RepositoryResult(
                repo=entry.repo, commit=entry.commit, call_sites=len(call_sites),
                by_value_binding=dict(sorted(bindings.items())), labelled=labelled,
                precision=precision, recall=recall,
            )
        )
    return CorpusReport(repositories=tuple(results), overall=overall)


def format_report(report: CorpusReport) -> str:
    def pct(x: float | None) -> str:
        return f"{x:.0%}" if x is not None else "n/a"

    lines = [f"{'repository':<32} {'sites':>5}  literal/dynamic/absent  labelled  P/R"]
    for r in report.repositories:
        if r.error:
            lines.append(f"{r.repo:<32} error: {r.error}")
            continue
        b = r.by_value_binding
        counts = f"{b.get('literal', 0)}/{b.get('dynamic', 0)}/{b.get('absent', 0)}"
        lines.append(
            f"{r.repo:<32} {r.call_sites:>5}  {counts:<22}  {'yes' if r.labelled else 'no':<8}  "
            f"{pct(r.precision)}/{pct(r.recall)}"
        )
    labelled = sum(r.labelled for r in report.repositories)
    lines.append("")
    lines.append(
        f"{labelled}/{len(report.repositories)} repositories labelled; "
        f"precision={pct(report.overall.precision)} recall={pct(report.overall.recall)}"
    )
    return "\n".join(lines)


def _index_pinned(entry: CorpusEntry) -> list[CallSite]:
    with tempfile.TemporaryDirectory(prefix="avert-experiment2-") as temp_dir:
        checkout = Path(temp_dir) / "repo"
        fetch_pinned(entry, checkout)
        return run_index(checkout, repo=entry.repo, commit=entry.commit)


def _failed(entry: CorpusEntry, error: str) -> RepositoryResult:
    return RepositoryResult(
        repo=entry.repo, commit=entry.commit, call_sites=0, by_value_binding={},
        labelled=False, precision=None, recall=None, error=error,
    )

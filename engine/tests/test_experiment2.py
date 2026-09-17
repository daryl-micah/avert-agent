import json
import subprocess
from pathlib import Path

from avert.experiment2 import CorpusEntry, load_corpus, run_corpus

FIXTURE = Path(__file__).parent / "fixtures" / "typed_sdk"
GROUND_TRUTH = Path(__file__).parent / "ground_truth" / "typed_sdk.jsonl"


def _local_remote(tmp_path: Path) -> CorpusEntry:
    """A file:// git repository standing in for GitHub, pinned to its only commit."""
    remote = tmp_path / "remote"
    remote.mkdir()
    (remote / "src").mkdir()
    for source in (FIXTURE / "src").iterdir():
        (remote / "src" / source.name).write_bytes(source.read_bytes())
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for argv in (["git", "init", "-q"], ["git", "add", "."], ["git", "commit", "-q", "-m", "init"]):
        subprocess.run(argv, cwd=remote, check=True, env={**env, "PATH": "/usr/bin:/bin"})
    subprocess.run(
        ["git", "config", "uploadpack.allowAnySHA1InWant", "true"], cwd=remote, check=True
    )
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=remote, check=True, capture_output=True, text=True
    ).stdout.strip()
    return CorpusEntry(repo="acme/typed-sdk", url=str(remote), commit=sha)


def test_committed_corpus_is_pinned_to_full_shas():
    entries = load_corpus()
    assert len(entries) == 20
    assert all(len(entry.commit) == 40 for entry in entries)
    assert len({entry.repo for entry in entries}) == 20


def test_unlabelled_repository_gets_a_label_template(tmp_path):
    entry = _local_remote(tmp_path)
    out = tmp_path / "out"

    report = run_corpus([entry], out_dir=out)

    (result,) = report.repositories
    assert result.error is None
    assert result.commit == entry.commit
    assert result.call_sites == 6
    assert result.labelled is False
    template = (out / "acme__typed-sdk.labels.jsonl").read_text().splitlines()
    assert len(template) == 6
    assert json.loads(template[0])["expect_detected"] is True
    assert (out / "acme__typed-sdk.predictions.jsonl").exists()
    assert report.overall.recall is None


def test_labelled_repository_is_scored(tmp_path):
    entry = _local_remote(tmp_path)
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "acme__typed-sdk.labels.jsonl").write_bytes(GROUND_TRUTH.read_bytes())

    report = run_corpus([entry], out_dir=tmp_path / "out", labels_dir=labels)

    (result,) = report.repositories
    assert result.labelled is True
    assert result.recall == 1.0
    assert result.precision == 1.0
    assert report.overall.recall == 1.0
    assert not (tmp_path / "out" / "acme__typed-sdk.labels.jsonl").exists()


def test_unreachable_repository_is_reported_not_raised(tmp_path):
    entry = CorpusEntry(repo="acme/missing", url=str(tmp_path / "nope"), commit="0" * 40)

    report = run_corpus([entry], out_dir=tmp_path / "out")

    (result,) = report.repositories
    assert result.error is not None
    assert result.call_sites == 0

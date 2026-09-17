from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

import psycopg

from avert import db
from avert.alerts import deliver_alerts
from avert.detect.events import fingerprint
from avert.detect.registry import load_events
from avert.detect.sdk_diff.acquire import downloaded_pair
from avert.detect.sdk_diff.diff import diff_artifacts
from avert.experiment2 import format_report as format_experiment2_report
from avert.experiment2 import load_corpus, run_corpus
from avert.experiment3 import format_report as format_experiment3_report
from avert.experiment3 import run_experiment
from avert.impacts import build_impact_report
from avert.index import run_index
from avert.index.incremental import incremental_index
from avert.inventory import build_inventory
from avert.models.call_site_schema import CallSite
from avert.models.change_event_schema import ChangeEvent
from avert.patch import generate_model_replacement
from avert.score import format_report, label_template, load_labels, load_predictions, score
from avert.verify import verify_proposal


def cmd_index(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 1

    repo = args.repo or root.name
    if args.database:
        with _connect(args.database) as conn:
            stats = incremental_index(
                conn, root, repo=repo, commit=args.commit, github_installation_id=args.installation,
            )
        print(
            f"{repo}: {stats.parsed} files parsed, {stats.skipped} unchanged, "
            f"{stats.deleted} removed, {stats.call_sites_written} call sites written"
        )
        return 0

    call_sites = run_index(root, repo=repo, commit=args.commit)
    out_path = Path(args.out)
    with out_path.open("w") as f:
        for cs in call_sites:
            f.write(cs.model_dump_json() + "\n")

    print(f"{len(call_sites)} call sites -> {out_path}")
    return 0


def _connect(dsn: str) -> psycopg.Connection:
    conn = psycopg.connect(dsn)
    db.apply_migrations(conn)
    return conn


def cmd_score(args: argparse.Namespace) -> int:
    predictions = load_predictions(Path(args.predictions))
    labels = load_labels(Path(args.labels))
    report = score(labels, predictions)
    print(format_report(report))
    return 0


def cmd_label(args: argparse.Namespace) -> int:
    predictions = []
    with Path(args.predictions).open() as f:
        for line in f:
            if line.strip():
                predictions.append(CallSite.model_validate_json(line))

    out_path = Path(args.out)
    with out_path.open("w") as f:
        for cs in predictions:
            f.write(label_template(cs) + "\n")

    print(f"{len(predictions)} candidate labels -> {out_path}")
    print("Review each line: set expect_detected to false for anything that isn't a real API call,")
    print("and hand-add any missed call sites the extractor didn't find.")
    return 0


def _write_events(events, out_path: Path) -> None:
    with out_path.open("w") as f:
        for event in events:
            f.write(event.model_dump_json() + "\n")


def cmd_registry(args: argparse.Namespace) -> int:
    events = load_events()
    if args.database:
        with _connect(args.database) as conn:
            for event in events:
                db.upsert_change_event(conn, event, fingerprint=fingerprint(event))
            conn.commit()
        print(f"{len(events)} lifecycle events -> {args.database}")
        return 0
    out_path = Path(args.out)
    _write_events(events, out_path)
    print(f"{len(events)} lifecycle events -> {out_path}")
    return 0


def cmd_inventory(args: argparse.Namespace) -> int:
    with _connect(args.database) as conn:
        inventory = build_inventory(conn, github_installation_id=args.installation)
    payload = inventory.model_dump_json(indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(payload)
        print(f"{inventory.call_site_count} call sites -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(payload)
    return 0


def cmd_sdk_diff(args: argparse.Namespace) -> int:
    source_url = args.source_url or f"https://{args.ecosystem}.org/project/{args.package}/"
    if args.from_path and args.to_path:
        from_path, to_path = Path(args.from_path), Path(args.to_path)
        events = diff_artifacts(
            ecosystem=args.ecosystem, package=args.package, from_path=from_path, to_path=to_path,
            from_version=args.from_version, to_version=args.to_version, source_url=source_url,
        )
    else:
        tempdir, (from_path, to_path) = downloaded_pair(
            ecosystem=args.ecosystem, package=args.package, from_version=args.from_version, to_version=args.to_version,
        )
        try:
            events = diff_artifacts(
                ecosystem=args.ecosystem, package=args.package, from_path=from_path, to_path=to_path,
                from_version=args.from_version, to_version=args.to_version, source_url=source_url,
            )
        finally:
            tempdir.cleanup()
    out_path = Path(args.out)
    _write_events(events, out_path)
    print(f"{len(events)} SDK changes -> {out_path}")
    return 0


def cmd_remediate(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a repository directory", file=sys.stderr)
        return 1
    try:
        event = ChangeEvent.model_validate_json(Path(args.event).read_text())
    except (OSError, ValueError) as exc:
        print(f"error: could not load event: {exc}", file=sys.stderr)
        return 1

    commands = [tuple(shlex.split(command)) for command in args.check]
    proposals = [
        proposal
        for call_site in run_index(root, repo=args.repo or root.name, commit=args.commit)
        if (proposal := generate_model_replacement(root, event, call_site)) is not None
    ]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    verified = 0
    for proposal in proposals:
        evidence = verify_proposal(root, event, proposal, commands=commands, timeout_seconds=args.timeout)
        stem = proposal.file_path.replace("/", "__").replace("\\", "__")
        base = out_dir / f"{stem}.L{proposal.line_start}"
        Path(f"{base}.diff").write_text(proposal.diff)
        Path(f"{base}.evidence.json").write_text(evidence.to_json())
        verified += evidence.passed

    print(f"{len(proposals)} patch proposals, {verified} verified -> {out_dir}")
    return 0 if verified == len(proposals) else 2


def cmd_impacts(args: argparse.Namespace) -> int:
    with _connect(args.database) as conn:
        report = build_impact_report(conn, github_installation_id=args.installation)
    payload = report.model_dump_json(indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(payload)
        print(f"{len(report.impacts)} change events -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(payload)
    return 0


def cmd_alerts(args: argparse.Namespace) -> int:
    with _connect(args.database) as conn:
        stats = deliver_alerts(conn, webhook_url=args.webhook_url)
    print(f"{stats.delivered} alerts delivered, {stats.skipped} already delivered")
    return 0


def cmd_experiment2(args: argparse.Namespace) -> int:
    entries = load_corpus(Path(args.corpus) if args.corpus else None)
    if args.only:
        entries = [entry for entry in entries if entry.repo in set(args.only)]
    report = run_corpus(
        entries,
        out_dir=Path(args.out),
        labels_dir=Path(args.labels) if args.labels else None,
    )
    (Path(args.out) / "report.json").write_text(report.to_json())
    print(format_experiment2_report(report))
    return 0 if all(r.error is None for r in report.repositories) else 1


def cmd_experiment3(args: argparse.Namespace) -> int:
    report = run_experiment(
        Path(args.cases) if args.cases else None,
        grades_path=Path(args.grades) if args.grades else None,
    )
    Path(args.out).write_text(report.to_json())
    print(format_experiment3_report(report))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="avert")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Extract call sites from a repository")
    index_parser.add_argument("path", help="Repository root to index")
    index_target = index_parser.add_mutually_exclusive_group(required=True)
    index_target.add_argument("--out", help="Output JSONL path")
    index_target.add_argument("--database", help="Postgres DSN; persists incrementally (SPEC §8.2)")
    index_parser.add_argument("--repo", default=None, help="Repo identifier (defaults to dir name)")
    index_parser.add_argument("--commit", default=None, help="Commit SHA being indexed")
    index_parser.add_argument(
        "--installation", type=int, default=None, help="GitHub App installation id (with --database)"
    )
    index_parser.set_defaults(func=cmd_index)

    score_parser = subparsers.add_parser("score", help="Score predictions against ground-truth labels")
    score_parser.add_argument("predictions", help="Predictions JSONL (from `avert index`)")
    score_parser.add_argument("--labels", required=True, help="Ground-truth labels JSONL")
    score_parser.set_defaults(func=cmd_score)

    label_parser = subparsers.add_parser(
        "label", help="Turn extraction output into an editable labels file for hand review"
    )
    label_parser.add_argument("predictions", help="Predictions JSONL (from `avert index`)")
    label_parser.add_argument("--out", required=True, help="Output labels JSONL path")
    label_parser.set_defaults(func=cmd_label)

    registry_parser = subparsers.add_parser("registry", help="Export model lifecycle events")
    registry_target = registry_parser.add_mutually_exclusive_group(required=True)
    registry_target.add_argument("--out", help="Output JSONL path")
    registry_target.add_argument("--database", help="Postgres DSN; upserts events by fingerprint")
    registry_parser.set_defaults(func=cmd_registry)

    inventory_parser = subparsers.add_parser(
        "inventory", help="Build the Layer 1 inventory from Postgres"
    )
    inventory_parser.add_argument("--database", required=True, help="Postgres DSN")
    inventory_parser.add_argument("--installation", type=int, default=None, help="Scope to one installation")
    inventory_parser.add_argument("--out", default=None, help="Output JSON path (defaults to stdout)")
    inventory_parser.set_defaults(func=cmd_inventory)

    diff_parser = subparsers.add_parser("sdk-diff", help="Diff two published SDK versions")
    diff_parser.add_argument("--ecosystem", choices=["pypi", "npm"], required=True)
    diff_parser.add_argument("--package", required=True)
    diff_parser.add_argument("--from-version", required=True)
    diff_parser.add_argument("--to-version", required=True)
    diff_parser.add_argument("--out", required=True)
    diff_parser.add_argument("--source-url", default=None)
    diff_parser.add_argument("--from-path", default=None, help="Local unpacked artifact (tests/offline use)")
    diff_parser.add_argument("--to-path", default=None, help="Local unpacked artifact (tests/offline use)")
    diff_parser.set_defaults(func=cmd_sdk_diff)

    remediate_parser = subparsers.add_parser(
        "remediate", help="Generate and verify literal model replacement proposals"
    )
    remediate_parser.add_argument("path", help="Repository root")
    remediate_parser.add_argument("--event", required=True, help="One ChangeEvent JSON file")
    remediate_parser.add_argument("--out", required=True, help="Directory for diffs and evidence JSON")
    remediate_parser.add_argument("--check", action="append", default=[], help="Verification command (repeatable)")
    remediate_parser.add_argument("--timeout", type=int, default=60, help="Per-check timeout in seconds")
    remediate_parser.add_argument("--repo", default=None, help="Repo identifier (defaults to directory name)")
    remediate_parser.add_argument("--commit", default=None, help="Commit SHA being remediated")
    remediate_parser.set_defaults(func=cmd_remediate)

    impacts_parser = subparsers.add_parser(
        "impacts", help="Change events joined to affected call sites (Layer 2 feed)"
    )
    impacts_parser.add_argument("--database", required=True, help="Postgres DSN")
    impacts_parser.add_argument("--installation", type=int, default=None, help="Scope to one installation")
    impacts_parser.add_argument("--out", default=None, help="Output JSON path (defaults to stdout)")
    impacts_parser.set_defaults(func=cmd_impacts)

    alerts_parser = subparsers.add_parser(
        "alerts", help="Deliver one webhook alert per affected (change event, repository)"
    )
    alerts_parser.add_argument("--database", required=True, help="Postgres DSN")
    alerts_parser.add_argument("--webhook-url", required=True, help="Receives a JSON POST per alert")
    alerts_parser.set_defaults(func=cmd_alerts)

    corpus_parser = subparsers.add_parser(
        "experiment2", help="Run the extractor over the pinned public-repository corpus"
    )
    corpus_parser.add_argument("--out", required=True, help="Directory for predictions, label templates, report")
    corpus_parser.add_argument("--corpus", default=None, help="Corpus JSON (defaults to the committed manifest)")
    corpus_parser.add_argument("--labels", default=None, help="Directory of reviewed <owner>__<repo>.labels.jsonl")
    corpus_parser.add_argument("--only", action="append", default=[], help="Restrict to a repository (repeatable)")
    corpus_parser.set_defaults(func=cmd_experiment2)

    experiment_parser = subparsers.add_parser(
        "experiment3", help="Run the historical model-deprecation remediation corpus"
    )
    experiment_parser.add_argument("--cases", default=None, help="Cases JSON (defaults to the committed corpus)")
    experiment_parser.add_argument("--grades", default=None, help="Manual grades JSON")
    experiment_parser.add_argument("--out", required=True, help="Experiment report JSON")
    experiment_parser.set_defaults(func=cmd_experiment3)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

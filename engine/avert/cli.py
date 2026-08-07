from __future__ import annotations

import argparse
import sys
from pathlib import Path

from avert.index import run_index
from avert.models.call_site_schema import CallSite
from avert.score import format_report, label_template, load_labels, load_predictions, score


def cmd_index(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 1

    repo = args.repo or root.name
    call_sites = run_index(root, repo=repo, commit=args.commit)

    out_path = Path(args.out)
    with out_path.open("w") as f:
        for cs in call_sites:
            f.write(cs.model_dump_json() + "\n")

    print(f"{len(call_sites)} call sites -> {out_path}")
    return 0


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="avert")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Extract call sites from a repository")
    index_parser.add_argument("path", help="Repository root to index")
    index_parser.add_argument("--out", required=True, help="Output JSONL path")
    index_parser.add_argument("--repo", default=None, help="Repo identifier (defaults to dir name)")
    index_parser.add_argument("--commit", default=None, help="Commit SHA being indexed")
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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

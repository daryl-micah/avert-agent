# Avert

Detects breaking changes in external APIs and maps them to the exact call sites they affect.

See [docs/SPEC.md](docs/SPEC.md) for the product spec and [docs/STRUCTURE.md](docs/STRUCTURE.md) for the repository layout.

## Status

Phase 1 complete (SPEC §15). Static inventory persisted incrementally in Postgres, SDK/lifecycle
change detection, an impact join that drives both the dashboard's lifecycle status and the change
feed, one-shot webhook alerts per affected repository, guarded model-replacement proposals, and a
read-only GitHub App with push-triggered re-indexing. Experiment records live in `docs/experiments/`.

## Development

```bash
docker compose up -d              # Postgres
cd engine && uv sync
uv run pytest
uv run avert index <path> --database $AVERT_DATABASE_URL   # incremental, persisted
uv run avert registry --database $AVERT_DATABASE_URL        # load lifecycle events
uv run avert inventory --database $AVERT_DATABASE_URL       # Layer 1 inventory JSON
uv run avert impacts --database $AVERT_DATABASE_URL         # Layer 2 change feed with blast radius
uv run avert alerts --database $AVERT_DATABASE_URL --webhook-url https://hooks.example/...
uv run avert index <path> --out calls.jsonl                 # one-off JSONL, no database
uv run avert experiment2 --out experiment2/     # pinned 20-repo corpus; writes label templates
uv run avert experiment3 --out experiment3-report.json                 # synthetic corpus (offline)
uv run avert experiment3 --cases engine/tests/fixtures/experiment3/corpus.json --out report.json  # pinned real repositories

cd ../app
cp .env.example .env.local       # GitHub App credentials + AVERT_DATABASE_URL
npm ci && npm run dev            # inventory dashboard at http://localhost:3000
```

`AVERT_DATABASE_URL` is `postgresql://avert:avert@localhost:5432/avert` for the compose service.
Migrations apply automatically on connect. The inventory's lifecycle status is the impact join
(`engine/avert/join.py`) evaluated per call site; its shape is `shared/schemas/inventory.schema.json`.
`impacts` is the same join per change event with a blast-radius statement
(`shared/schemas/impact.schema.json`); `alerts` posts one JSON payload per affected (event,
repository) and records it in `alert_delivery`, so re-running it never repeats a delivery.

`experiment2` runs the extractor over the pinned public-repository corpus in
`engine/tests/fixtures/experiment2/corpus.json`. Each unlabelled repository gets a
`<owner>__<repo>.labels.jsonl` template; review it (flip `expect_detected`, hand-add misses), commit
it under a labels directory, and re-run with `--labels <dir>` to get precision and recall. The
decision rule (SPEC §15) is <85% recall.

`experiment3` mechanically verifies a model-deprecation corpus: the committed synthetic ten cases by
default, or ten pinned public repositories with `--cases .../corpus.json` (first run recorded in
`docs/experiments/experiment3-2026-09-18.md`: 7/10). Its merge-readiness rate remains pending until an
experienced engineer supplies manual grades (`merge_as_is`, `merge_with_edits`, or `wrong`).

See [app/README.md](app/README.md) for the Week 4 local demo flow and its current boundaries.

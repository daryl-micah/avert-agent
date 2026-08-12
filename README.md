# Avert

Detects breaking changes in external APIs and maps them to the exact call sites they affect.

See [docs/SPEC.md](docs/SPEC.md) for the product spec and [docs/STRUCTURE.md](docs/STRUCTURE.md) for the repository layout.

## Status

Phase 1, week 3 (SPEC §15). Static inventory, SDK/lifecycle change detection, impact joins, and guarded model-replacement proposals for Python and TypeScript.

## Development

```bash
docker compose up -d              # Postgres
cd engine && uv sync
uv run pytest
uv run avert index <path> --out calls.jsonl
uv run avert experiment3 --out experiment3-report.json
```

`experiment3` mechanically verifies the committed ten-case historical model-deprecation corpus. Its merge-readiness rate remains pending until an experienced engineer supplies manual grades (`merge_as_is`, `merge_with_edits`, or `wrong`).

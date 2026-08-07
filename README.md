# Avert

Detects breaking changes in external APIs and maps them to the exact call sites they affect.

See [docs/SPEC.md](docs/SPEC.md) for the product spec and [docs/STRUCTURE.md](docs/STRUCTURE.md) for the repository layout.

## Status

Pre-build, week 1 (SPEC §15 Phase 1). Static extraction pipeline for Python and TypeScript, targeting OpenAI and Anthropic SDK call sites.

## Development

```bash
docker compose up -d              # Postgres
cd engine && uv sync
uv run pytest
uv run avert index <path> --out calls.jsonl
```

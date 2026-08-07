# 0001 — Controlled vocabulary lives in `shared/`

**Status:** Accepted
**Context:** STRUCTURE.md §4 lifecycle registry

## Decision

The controlled vocabulary for `provider`, `resource`, and `operation` (SPEC §6.1) lives at
`shared/vocabulary/providers.json`, alongside the JSON Schemas it constrains.

## Why

SPEC §6.1 requires these three fields come from a controlled vocabulary rather than free text —
"`openai` and `open-ai` resolving to different identities would silently halve every count in the
system." That is a contract both the Python engine and the TypeScript app must agree on, which is
exactly what `shared/` exists for (STRUCTURE §2: "so the two pipelines cannot disagree about a
field name").

STRUCTURE §4 leaves this placement open, noting `detect/registry/` is a candidate because it is
the vocabulary's only reader today. But the vocabulary is a validation input to `SurfaceID`
construction on both sides of the join, not detection-specific output — `index/` needs it as much
as `detect/` will. Placing it under `engine/avert/detect/registry/` would make `index/` depend on
`detect/`, which STRUCTURE §2 forbids outright ("`detect/` and `index/` never import each other").

`detect/registry/` (SPEC §15, opened in Phase 2) remains a separate concern: it is the model
*lifecycle* registry (deprecation dates, migration targets), not the identity vocabulary. The two
may eventually share a public-repository extraction path (STRUCTURE §4's open question), but
nothing here forecloses that.

## Consequence

Week 1 ships `shared/vocabulary/providers.json` scoped to `openai` and `anthropic` only, per
SPEC §15's "hardcode OpenAI and Anthropic" instruction. Expanding to new providers is an addition
to this file, not a structural change.

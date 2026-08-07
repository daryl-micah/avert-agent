# Avert — Repository Structure

**Status:** Pre-build. Nothing in this tree exists yet.
**Companion to:** [SPEC.md](SPEC.md) — §6.3 is the source this expands.
**Last updated:** August 2026

---

## 1. Shape

A single repository, two runtime languages, one schema source of truth.

```
avert-app/
├── AGENTS.md
├── README.md
├── docker-compose.yml          Postgres for local dev
├── docs/
│   ├── SPEC.md
│   ├── STRUCTURE.md
│   └── decisions/              ADRs, numbered, one per irreversible choice
│
├── shared/                     Contract between the two languages
│   ├── schemas/
│   │   ├── surface_id.schema.json
│   │   ├── change_event.schema.json
│   │   └── call_site.schema.json
│   └── generate.sh             → engine/avert/models/, app/src/types/
│
├── engine/                     Python — detection, indexing, patching, verification
│   ├── pyproject.toml
│   ├── avert/
│   │   ├── models/             GENERATED Pydantic — do not hand-edit
│   │   ├── db/
│   │   │   ├── migrations/     NNNN_name.sql, sequential
│   │   │   ├── schema.py       query helpers
│   │   │   └── queue.py        SKIP LOCKED claim/ack
│   │   ├── detect/
│   │   │   ├── sdk_diff/       §7.1 — the first source built
│   │   │   │   ├── python_surface.py
│   │   │   │   └── ts_surface.py      shells out to tools/dts-surface
│   │   │   ├── registry/       static model lifecycle data (see §4)
│   │   │   ├── spec_diff.py    §7.2 — shells out to oasdiff
│   │   │   ├── email.py        §7.4
│   │   │   └── changelog.py    §7.5
│   │   ├── index/
│   │   │   ├── candidates.py   §8.1 step 1 — ripgrep
│   │   │   ├── parse/          §8.1 step 2 — tree-sitter
│   │   │   │   └── queries/    *.scm, one per language
│   │   │   ├── classify.py     §8.1 steps 3–5 — embeddings, small, frontier
│   │   │   └── incremental.py  §8.2 — content-hash keying
│   │   ├── join.py             §6 impact join — a SQL query, not a model call
│   │   ├── patch/
│   │   ├── verify/             §9 evidence bundle
│   │   │   └── sandbox/        Dockerfiles for ephemeral test runs
│   │   └── workers/            queue consumers; entry points live here
│   ├── tools/
│   │   └── dts-surface/        TypeScript — .d.ts public-surface extractor
│   └── tests/                  mirrors avert/
│
├── app/                        TypeScript — GitHub App + dashboard
│   ├── package.json
│   ├── src/
│   │   ├── types/              GENERATED — do not hand-edit
│   │   ├── github/             Octokit, webhook handlers, PR authoring
│   │   └── dashboard/          Next.js
│   └── tests/
│
└── collectors/                 §7.3 — libraries, not infrastructure
    ├── python/
    └── node/
```

---

## 2. Why these boundaries

**`shared/` exists so the two pipelines cannot disagree about a field name.** JSON Schema is authored by hand; Pydantic models and TS types are generated from it. Generated output is **committed**, and CI fails if regeneration produces a diff — so consumers never run codegen, but drift is impossible.

**`engine/tools/dts-surface/` is TypeScript inside the Python tree on purpose.** SPEC §6.3 has no home for it. Its only consumer is `detect/sdk_diff/`, and the engine already shells out to `oasdiff` and `ripgrep`; this is the same pattern with a locally-built binary. Colocating it with its caller beats a fourth top-level directory.

**`detect/` and `index/` never import each other.** That is the decoupling in SPEC §6 made structural — the only shared surface is `models/` and the database. If a file in one imports from the other, the architecture has been violated and the two-branch shipping story is gone.

**`join.py` is one file and should stay small.** SPEC §6.1 claims the join is a database query rather than an AI problem. If this file grows a model call, that claim has quietly stopped being true.

**Migrations are plain SQL, no ORM, no Alembic.** Same reasoning as SPEC §6.2's Postgres-over-Celery choice: the schema is small and the queue is already raw SQL. Revisit if migration count passes ~30.

---

## 3. What is deliberately absent

Adding any of these without a corresponding spec change means something drifted:

- **No `providers/` abstraction layer.** SPEC §15 is explicit — hardcode OpenAI and Anthropic through the full pipeline first. The seams are not known yet, and a plugin interface designed now will encode the wrong definition of "a change."
- **No Go, no proxy, no sidecar.** SPEC §6.2. Collectors are imports.
- **No vector store, no Redis, no Celery.** Postgres does all three jobs.
- **No `services/` or per-deployable split.** One engine process type, differentiated by which worker runs.
- **No MCP server or provider-side product.** Phase 3 (SPEC §5.4, §15). When it lands it is a consumer of the change feed, so it goes under `app/` or as a fourth top-level — decide then, not now.

---

## 4. Open placement questions

- **`detect/registry/`** holds the model lifecycle registry that Phase 2 open-sources (SPEC §15). It is under `engine/` for now because that is its only reader, but a public registry probably wants its own repository with its own release cadence. Decide before the free tier ships, not after.
- **`shared/schemas/` now carries a resolved but unexercised design.** SPEC §6.1 was amended to add `value` to the identity tuple, put API version on the `ChangeEvent`/`CallSite` edges, and add `value_binding` to call sites. It is still the hardest thing to change later, and nothing has tested it against a real provider yet — week 1's extractor run is the first evidence it holds up. Treat a second provider disagreeing with the tuple as a spec bug, not a mapping problem.
- **`detect/` needs a controlled vocabulary owner.** SPEC §6.1 requires `provider`/`resource`/`operation` come from a controlled vocabulary rather than free text. Where that vocabulary lives is unplaced — likely alongside `detect/registry/`, and likely with the same open question about being extracted.

---

## 5. Week 1 subset

Phase 1 week 1 (SPEC §15) needs only:

```
shared/schemas/surface_id.schema.json + call_site.schema.json
shared/generate.sh
engine/avert/models/
engine/avert/db/migrations/0001_init.sql
engine/avert/index/{candidates,parse,incremental}.py
engine/tests/
docker-compose.yml
```

Everything else stays unwritten. Week 1 output is the extractor run against 20 repositories — which is experiment 2, so it needs a labelled-ground-truth harness under `engine/tests/` measuring **both recall and precision** (SPEC §15 specifies recall only; see the audit).

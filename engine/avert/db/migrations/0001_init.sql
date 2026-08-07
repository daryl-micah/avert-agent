-- Week 1 schema (SPEC §6.1, §6.2, §8.2; STRUCTURE §2 — plain SQL, no ORM).
-- pgvector extension is available in the image but not enabled here:
-- nothing in week 1 needs embeddings (index/classify.py doesn't exist yet).

CREATE TABLE repository (
    id   BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE  -- e.g. "acme/widgets"
);

CREATE TABLE indexed_file (
    id             BIGSERIAL PRIMARY KEY,
    repository_id  BIGINT NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
    path           TEXT NOT NULL,
    language       TEXT NOT NULL,
    content_hash   TEXT NOT NULL,  -- sha256 of file bytes; SPEC §8.2 incremental re-index key
    commit_sha     TEXT,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, path)
);

-- SurfaceID (SPEC §6.1). NULLS NOT DISTINCT because three of the five
-- columns are nullable and Postgres treats NULL as distinct by default —
-- without this, duplicate identities could silently accumulate.
CREATE TABLE surface (
    id         BIGSERIAL PRIMARY KEY,
    provider   TEXT NOT NULL,
    resource   TEXT NOT NULL,
    operation  TEXT,
    field_path TEXT,
    value      TEXT,
    UNIQUE NULLS NOT DISTINCT (provider, resource, operation, field_path, value)
);

-- One row per call expression (decision 5 in the plan): no separate
-- coarser-granularity row per call. No snippet column — SPEC §10 "no code
-- retention" beyond file path and line numbers.
CREATE TABLE call_site (
    id              BIGSERIAL PRIMARY KEY,
    indexed_file_id BIGINT NOT NULL REFERENCES indexed_file(id) ON DELETE CASCADE,
    surface_id      BIGINT NOT NULL REFERENCES surface(id),
    line_start      INTEGER NOT NULL,
    line_end        INTEGER NOT NULL,
    api_version     TEXT,
    value_binding   TEXT NOT NULL CHECK (value_binding IN ('literal', 'dynamic', 'absent')),
    confidence      REAL NOT NULL,
    extractor       TEXT NOT NULL
);

CREATE INDEX call_site_indexed_file_id_idx ON call_site (indexed_file_id);
CREATE INDEX call_site_surface_id_idx ON call_site (surface_id);

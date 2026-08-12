CREATE TABLE change_event (
    id                     BIGSERIAL PRIMARY KEY,
    surface_id             BIGINT NOT NULL REFERENCES surface(id),
    replacement_surface_id BIGINT REFERENCES surface(id),
    change_type            TEXT NOT NULL,
    severity               TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'breaking')),
    source                 TEXT NOT NULL CHECK (source IN ('sdk_diff', 'model_registry')),
    confidence             REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    summary                TEXT,
    announced_at           DATE,
    effective_at           DATE,
    applies_from           TEXT,
    applies_to             TEXT,
    detected_at            TIMESTAMPTZ NOT NULL,
    provenance             JSONB NOT NULL,
    fingerprint            TEXT NOT NULL UNIQUE
);

CREATE INDEX change_event_surface_id_idx ON change_event (surface_id);

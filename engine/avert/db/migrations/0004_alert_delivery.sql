-- One row per alert actually delivered, keyed on what it was about, so a
-- re-run of `avert alerts` never repeats a delivery (SPEC §5.2: alert fatigue
-- is the cardinal product failure after missed changes).
CREATE TABLE alert_delivery (
    id              BIGSERIAL PRIMARY KEY,
    change_event_id BIGINT NOT NULL REFERENCES change_event(id) ON DELETE CASCADE,
    repository_id   BIGINT NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL,
    delivered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (change_event_id, repository_id, channel)
);

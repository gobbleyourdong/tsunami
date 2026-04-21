-- Runs once on fresh volume. Idempotent — don't put migrations here;
-- use a real migration tool (dbmate, sqlx, alembic, flyway).

CREATE TABLE IF NOT EXISTS _scaffold_ping (
    id SERIAL PRIMARY KEY,
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO _scaffold_ping DEFAULT VALUES;

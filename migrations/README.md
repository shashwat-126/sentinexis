# Database Migrations (Alembic)

The platform's services still call `Base.metadata.create_all()` on startup
for local/dev convenience -- `docker compose up -d --build` works out of the
box with no extra steps. This directory is the **production migration
path**: a single, versioned schema history for the shared Postgres
database, independent of any one service's ORM models.

## Usage

```bash
# Point at your target database
export DATABASE_URL=postgresql://user:password@localhost:5432/aiops

# Apply all migrations (idempotent -- safe to re-run)
alembic upgrade head

# Create a new revision after changing a model
alembic revision -m "add priority column to incidents"

# Roll back the most recent revision
alembic downgrade -1
```

## Baseline

`versions/0001_baseline.py` mirrors the exact schema `create_all()`
produces today: `incidents`, `incident_events`, `actions`,
`metric_snapshots`, `audit_logs`, `notifications`, plus the two original
tables (`inference_results`, `incident_logs`). Running it against a fresh
database gets you to the same starting point as a fresh `docker compose up`.

## Going forward in production

Once a database has been migrated with Alembic, disable the
`Base.metadata.create_all()` calls in each service's startup (they're
idempotent and harmless against an existing schema, but the source of
truth should be migrations from that point on) and add a new revision for
every schema change instead.

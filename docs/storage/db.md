# storage/db.py — SQLite Database Layer

## Purpose

All persistence for `Job` objects goes through this class. Uses Python's standard library `sqlite3` module — no ORM dependency. Jobs are stored as a mix of typed columns (for fast querying and sorting) and JSON blobs (for flexible nested data like scores and salary).

## Design Decisions

### No ORM
`sqlite3` is used directly rather than SQLAlchemy or another ORM. This keeps the dependency list small and makes the SQL readable. The trade-off is slightly more verbose serialisation code in `_to_row()` and `_from_row()`.

### JSON Blobs for Nested Data
`salary_json` and `scores_json` store the entire `SalaryRange` and `TrackScores` objects as JSON strings. This avoids extra tables for a one-to-one relationship and keeps `INSERT` and `UPDATE` statements simple.

Additionally, individual score values (`score_ic`, `score_architect`, `score_management`, `score_best`) are stored as separate INTEGER columns. This allows:
- Fast `ORDER BY score_best DESC` without parsing JSON in SQLite
- The Streamlit dashboard to query scores directly via `pd.read_sql_query`

### Schema Migrations
New columns are added via `ALTER TABLE` without recreating the table. The `_MIGRATIONS` list tracks every column added after the initial schema. On startup, `_run_migrations()` checks which columns already exist and only adds the missing ones. Safe to run every time — idempotent.

### WAL Mode
```python
self._conn.execute("PRAGMA journal_mode=WAL")
```
Write-Ahead Logging allows concurrent reads while a write is in progress. The Streamlit dashboard can read while `main.py` is scoring, without locking errors.

## Public Interface

### `Database(db_path: str)`
Opens or creates the database file. Creates the jobs table if it doesn't exist. Runs migrations.

### Write Operations

| Method | Purpose |
|---|---|
| `insert_job(job) → Job` | Inserts a job. Silently ignores duplicate URLs (`INSERT OR IGNORE`). Sets `job.id` from the database. |
| `update_job(job)` | Updates all fields of an existing job. Requires `job.id` to be set. |
| `upsert_job(job) → Job` | Inserts if new (by URL), updates if exists. Convenience wrapper. |

### Read Operations

| Method | Returns | Notes |
|---|---|---|
| `get_by_id(job_id)` | `Job?` | Primary key lookup |
| `get_by_url(url)` | `Job?` | Used for deduplication on insert |
| `get_by_title_company(title, company)` | `Job?` | Catches same job posted with different URLs |
| `get_by_status(status)` | `list[Job]` | Key for pipeline: `get_by_status(NEW)` = jobs to score |
| `get_all()` | `list[Job]` | All jobs, newest first |
| `count()` | `int` | Total job count |

### `close()`
Closes the database connection. Always called in `main.py`'s `finally` block.

## Schema

```sql
CREATE TABLE jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    url              TEXT    NOT NULL UNIQUE,   -- deduplication key
    source           TEXT    NOT NULL,
    title            TEXT    NOT NULL,
    company          TEXT    NOT NULL,
    location         TEXT,
    work_mode        TEXT,
    description      TEXT,
    salary_json      TEXT,                      -- SalaryRange as JSON
    scores_json      TEXT,                      -- TrackScores as JSON
    status           TEXT    NOT NULL DEFAULT 'new',
    posted_at        TEXT,                      -- ISO 8601
    expires_at       TEXT,
    found_at         TEXT    NOT NULL,
    applied_at       TEXT,
    score_ic         INTEGER,                   -- denormalised for fast queries
    score_architect  INTEGER,
    score_management INTEGER,
    score_best       INTEGER                    -- max(ic, architect, management)
)
```

## Serialisation

`_to_row(job)` converts a `Job` to a flat tuple for the INSERT statement. Handles:
- Enum values: `job.source.value` → `"linkedin"`
- Optional datetimes: `.isoformat()` or `None`
- Pydantic models: `.model_dump_json()` or `None`

`_from_row(row)` reverses this. Handles:
- JSON blobs: `TrackScores.model_validate_json(row["scores_json"])`
- Enum reconstruction: `JobSource(row["source"])`
- Optional datetime parsing: `datetime.fromisoformat(row["posted_at"])`

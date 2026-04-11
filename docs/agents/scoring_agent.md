# agents/scoring_agent.py — Job Scoring Agent

## Purpose

Scores job postings against the candidate's profile across all active career tracks (IC, Architect, Management). Sends up to **10 jobs per Claude call** and fires all batches **concurrently** using `ThreadPoolExecutor` to minimise latency.

## Agentic Patterns

### 1. Parallel Batched Fan-Out

Jobs are chunked into batches of `BATCH_SIZE = 10` and submitted to Claude concurrently — up to `MAX_PARALLEL_BATCHES = 3` at a time. All batches are independent: they share the same cached system prompt but carry different job sets in the user message.

```
50 jobs  →  5 batches of 10  →  submitted concurrently (3 + 2)
                                 ├─ batch 1 ─┐
                                 ├─ batch 2 ─┤ → fire together (~15s wall time)
                                 └─ batch 3 ─┘
                                 ├─ batch 4 ─┐
                                 └─ batch 5 ─┘ → fire together (~15s wall time)
                                                Total: ~30s vs ~75s sequential
```

**Thread safety:**
- `ClaudeClient._usage` is protected by `threading.Lock` — concurrent `+=` on shared counters would lose increments without it.
- `db.update_job()` calls are serialised with a per-`score_batch()` `threading.Lock` — SQLite WAL mode allows concurrent reads but still serialises commits.

**Cache correctness:** `num_jobs` is intentionally absent from the system prompt. Including it caused a cache miss on the last batch (e.g. "Score these 7 jobs" ≠ "Score these 10 jobs" → different cache key → full input charge on every last batch). The count is passed in the user message only, keeping the system prompt byte-identical across all concurrent batches so all share the same Anthropic prompt cache key.

**Fault isolation:** Each future is caught independently via `as_completed()`. One batch failing after all retries does not cancel other in-flight batches. Jobs in a failed batch stay `NEW` and are retried on the next run.

### 2. Pre-Filter Gate (Cheap Before Expensive)

Four filter stages run before any Claude call, eliminating irrelevant jobs:

```
Stage 1 — is_stale?         skip jobs posted > 30 days ago
Stage 2 — no description?   skip — Claude cannot score without content
Stage 3 — excluded title?   skip sales, civil eng, property managers, etc.
Stage 4 — tech description? at least one tech keyword must appear
                             catches hotel maintenance, plumbing, etc.
```

### 3. Multi-Track Scoring

A single Claude call returns scores for all three tracks simultaneously. The prompt lists active tracks; Claude returns `null` for disabled tracks. This avoids 3x the API calls that a per-track approach would require.

### 4. Crash-Safe Persistence

After each batch resolves, `db.update_job()` is called immediately for every scored job — not once at the end. If the run is interrupted, already-scored jobs are preserved and will not be sent to Claude again on the next run.

## Public Interface

### `ScoringAgent(client, loader, parser, tracks_config, salary_config)`

### `score_batch(jobs, profile, db=None, on_progress=None) → list[Job]`

| Parameter | Type | Purpose |
|---|---|---|
| `jobs` | `list[Job]` | Jobs to score — must already be in the database |
| `profile` | `Profile` | The candidate's parsed profile |
| `db` | `Database` (optional) | If provided, each job is saved immediately after scoring |
| `on_progress` | `Callable` (optional) | Called before each batch fires with `(batch_num, total_batches, batch_jobs)` |

Returns the same list with `scores` and `status` populated on eligible jobs.

### `last_run_stats: dict`

Populated after each `score_batch()` call. Read by `main.py` to persist timing data to the `runs` table.

| Key | Type | Description |
|---|---|---|
| `elapsed_score_s` | `float` | Wall-clock seconds for the entire scoring phase |
| `avg_batch_latency_s` | `float` | Mean seconds per Claude API call across all batches |
| `jobs_per_second` | `float` | Scoring throughput: `jobs_scored / elapsed_score_s` |

## Constants

| Constant | Value | Purpose |
|---|---|---|
| `BATCH_SIZE` | `10` | Max jobs per Claude call. At 10, one call is ~6,500 input + ~3,000 output tokens. |
| `MAX_PARALLEL_BATCHES` | `3` | Concurrent Claude calls. Safe for free-tier RPM. Raise to 5 on paid tiers. |

## Filter Keywords

Both filter lists live in **`models/filters.py`** — the single source of truth imported by both `ScoringAgent` and `AdzunaScraper`. Editing `models/filters.py` updates both gatekeeping layers simultaneously.

### Excluded Titles (`EXCLUDED_TITLE_KEYWORDS`)
Titles containing these strings are skipped regardless of source:
- Sales: `presales`, `sales manager`, `sales engineer`, `account manager`, `business development`
- Non-tech management: `property manager`, `community manager`, `leasing`, `project manager`, `program manager`, `office manager`, `operations manager`
- Non-software engineering: `electrical engineer`, `civil engineer`, `structural engineer`, `landscape architect`, `hvac`, `medical`
- Junior/unrelated: `intern`, `internship`, `associate engineer`, `hotel`
- Language-specific: `java developer`, `java engineer`

### Required Description Keywords (`TECH_DESCRIPTION_KEYWORDS`)
At least one of these must appear in the description:
- Languages: `software`, `python`, `javascript`, `typescript`, `.net`, `golang`, `rust`
- Cloud/infra: `cloud`, `aws`, `azure`, `gcp`, `kubernetes`, `docker`, `terraform`, `ci/cd`, `devops`
- Architecture: `api`, `microservice`, `distributed system`, `backend`, `frontend`, `saas`
- Data/AI: `data engineering`, `machine learning`, `artificial intelligence`, `llm`, `database`
- IoT/edge: `iot`, `mqtt`, `edge computing`, `embedded`, `firmware`

## Claude Call Details

| Setting | Value |
|---|---|
| Prompt template | `prompts/score_job.md` |
| Operation | `job_scoring` |
| Max tokens | 3,500 (covers 10 jobs — ~300 tokens per score object) |
| Temperature | 0.1 (consistent scoring across runs) |

## Data Flow

```
[list[Job]] + [Profile]
      │
      ▼
Pre-filter gate (stale / no desc / excluded title / non-tech)
      │
      ▼
Chunk into batches of BATCH_SIZE
      │
      ▼
ThreadPoolExecutor (MAX_PARALLEL_BATCHES workers)
  ├─ _run_batch(1, chunk_1) ──────────────────────────────────┐
  ├─ _run_batch(2, chunk_2) ─────────────────────────────┐    │
  └─ _run_batch(3, chunk_3) ────────────────────────┐    │    │
                                                    │    │    │
  Each worker:                                      ▼    ▼    ▼
    _score_chunk(chunk, profile)             results collected
      ├─ build jobs_block (XML index tags)   via as_completed()
      ├─ PromptLoader.load("score_job", ...)
      ├─ ClaudeClient.call(system, user, "job_scoring")
      └─ ResponseParser.parse_list(raw, BatchJobScore)
            │
            ▼ (under db_lock)
      job.scores = TrackScores(ic, architect, management)
      job.status = SCORED
      db.update_job(job)
```

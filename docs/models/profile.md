# models/profile.py — Candidate Profile Model

## Purpose

Defines the `Profile` Pydantic model — a structured representation of your professional background extracted from your resume PDF. The profile is the "candidate side" of every Claude scoring and tailoring call.

## Role in the System

```
resume.pdf
    │
    ▼
ProfileAgent (Claude extracts text → JSON)
    │
    ▼
Profile object (validated by Pydantic)
    │
    ├─── injected into score_job prompt   → Claude compares profile vs job
    └─── injected into tailor_resume prompt → Claude rewrites resume for job
```

## Sub-Models

### `Experience`
One role in your work history.

| Field | Type | Notes |
|---|---|---|
| `company` | `str` | Company name |
| `title` | `str` | Your job title at this company |
| `start_year` | `int` | Year started |
| `end_year` | `int?` | Year left — `None` if current role |
| `description` | `str?` | Summary of responsibilities and achievements |
| `technologies` | `list[str]` | Technologies used in this role |

**Computed property `years`:** returns number of years in the role. Uses current year for ongoing roles. Used by Claude to assess seniority.

### `Education`
| Field | Type | Notes |
|---|---|---|
| `institution` | `str` | University name |
| `degree` | `str` | e.g. "B.S. Computer Science" |
| `year` | `int?` | Graduation year |

### `Certification`
| Field | Type | Notes |
|---|---|---|
| `name` | `str` | e.g. "AWS Solutions Architect" |
| `issuer` | `str?` | e.g. "Amazon Web Services" |
| `year` | `int?` | Year obtained |

Certifications are high-signal for certain roles (cloud architect, DevOps engineer). Claude uses them to boost scores on roles that list specific certs as requirements.

## Main Model: `Profile`

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Full name |
| `headline` | `str?` | One-line summary, e.g. "Staff Engineer with 12 years in cloud" |
| `email` | `str?` | Contact email |
| `location` | `str?` | e.g. "Atlanta, GA" |
| `experience` | `list[Experience]` | Work history, most recent first |
| `skills` | `list[str]` | Flat list of technologies and tools |
| `education` | `list[Education]` | Degrees |
| `certifications` | `list[Certification]` | Professional certifications |
| `summary` | `str?` | Free-text professional summary paragraph |

### Computed Properties

**`total_years_experience`** — sum of years across all experience entries. Useful for seniority checks.

**`current_title`** — title of the most recent role (`end_year is None`). Falls back to first entry if none is marked current.

## How It's Serialised

When injected into prompts, the profile is serialised with:
```python
json.dumps(profile.model_dump(), indent=2, default=str)
```

This produces a pretty-printed JSON block inside the `<profile>` XML tag in the prompt. Claude reads this JSON to understand your background.

## Cache

The profile is cached as `data/profile.json` between runs. See [agents/profile_agent.md](../agents/profile_agent.md) for cache invalidation details.

# agents/profile_agent.py — Resume Parser Agent

## Purpose

Extracts a structured `Profile` object from your resume PDF using Claude. Once parsed, the profile is **cached to disk** so Claude is not called again on the next run unless the resume file changes.

## Agentic Pattern: Cache-Aside

This is a textbook **Cache-Aside** pattern applied to an LLM call:

```
ProfileAgent.load(resume.pdf)
  │
  ├─ cache exists AND is newer than resume.pdf?
  │   └─ YES → load data/profile.json, return Profile  (no Claude call)
  │
  └─ NO (cache missing or stale)
      ├─ pdfplumber extracts text from resume.pdf
      ├─ PromptLoader renders parse_resume.md with the text
      ├─ ClaudeClient.call(system, user, "resume_parsing")
      ├─ ResponseParser.parse(raw, Profile)  → validated Profile
      └─ save to data/profile.json          → warm the cache
```

The cache is invalidated by comparing file modification timestamps. If you update your resume, delete `data/profile.json` or simply save the PDF — the stale check will trigger a fresh parse automatically.

## Public Interface

### `ProfileAgent(client, loader, parser)`

| Parameter | Type | Purpose |
|---|---|---|
| `client` | `ClaudeClient` | Makes the Claude API call |
| `loader` | `PromptLoader` | Loads `prompts/parse_resume.md` |
| `parser` | `ResponseParser` | Validates Claude's JSON response |

### `load(resume_path: str) → Profile`

Returns the candidate's `Profile`. Uses the cache if it is fresh; re-parses with Claude otherwise.

- Raises `FileNotFoundError` if the PDF does not exist.
- Raises `ResponseParseError` if Claude returns invalid JSON.

## Claude Call Details

| Setting | Value |
|---|---|
| Prompt template | `prompts/parse_resume.md` |
| Operation | `resume_parsing` |
| Max tokens | 1,000 (set in config.yaml) |
| Temperature | 0.1 (deterministic extraction) |

## Cache File

Location: `data/profile.json`

The profile is serialised with `Profile.model_dump_json(indent=2)` — a plain JSON file you can inspect or edit by hand. The `data/` directory is created automatically.

## Output: Profile Object

The parsed profile contains:
- `name`, `headline`, `email`, `location`
- `experience` — list of `Experience` (company, title, years, technologies)
- `skills` — flat list of technology strings
- `education` — list of `Education`
- `certifications` — list of `Certification`
- `summary` — free-text professional summary

The full schema is documented in [models/profile.md](../models/profile.md).

## Why this matters for scoring

Every job scoring call injects the full Profile as JSON into the scoring prompt. Without caching, scoring 50 jobs would trigger 51 Claude calls (1 resume parse + 10 scoring batches). With caching, it triggers 10.

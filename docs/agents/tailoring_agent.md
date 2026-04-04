# agents/tailoring_agent.py — Resume Tailoring Agent

## Purpose

Rewrites your resume sections to match a specific job posting and career track. Called only when you decide to apply — not during the initial scoring run. Saves the tailored content as a human-readable `.txt` file you can use as a guide when updating your actual resume.

## When It Runs

Only invoked via `python main.py --tailor <job_id>`. You choose:
1. Which job (by database ID)
2. Which career track: IC, Architect, or Management

This distinction matters because the same job posting might be applied for differently depending on which angle you're taking (e.g., applying as an architect vs. a manager requires a different emphasis).

## Agentic Pattern: Structured Creative Output

Tailoring is the one place in this system where Claude produces **creative, freeform text** rather than pure data extraction. The trick is still wrapping the output in a JSON schema so it can be parsed and saved consistently:

```
Profile (JSON) + Job (text) + Track (string)
      │
      ▼
PromptLoader.load("tailor_resume", ...)
      │
      ▼
ClaudeClient.call("resume_tailoring")  ← temperature=0.3 (more natural language)
      │
      ▼
ResponseParser._strip_code_fences()
ResponseParser._extract_json()
json.loads() → dict
      │
      ▼
TailoredResume(
  tailored_summary,        ← rewritten professional summary
  highlighted_experience,  ← per-role bullet points, most relevant to this job
  keywords,                ← ATS keywords from the posting that match your background
  gaps,                    ← requirements you don't clearly meet
  output_path              ← where the file was saved
)
```

## Public Interface

### `TailoringAgent(client, loader, parser, output_dir)`

| Parameter | Default | Purpose |
|---|---|---|
| `client` | — | `ClaudeClient` for API calls |
| `loader` | — | `PromptLoader` for the tailor_resume template |
| `parser` | — | `ResponseParser` for JSON extraction |
| `output_dir` | `output/resumes` | Where tailored resume files are saved |

### `tailor(job, profile, track) → TailoredResume`

Returns a `TailoredResume` dataclass:

| Field | Type | Content |
|---|---|---|
| `tailored_summary` | `str` | Rewritten professional summary paragraph |
| `highlighted_experience` | `list[dict]` | Per-role bullets most relevant to the job |
| `keywords` | `list[str]` | ATS keywords from the job that match your background |
| `gaps` | `list[str]` | Requirements in the job you don't clearly meet |
| `output_path` | `Path` | File path where the .txt was saved |

## Output File Format

Files are saved to `output/resumes/<Company>_<Title>_<track>.txt`:

```
TAILORED RESUME — Senior Software Engineer at Acme Corp
Track: ARCHITECT
URL: https://...
======================================================================

PROFESSIONAL SUMMARY
----------------------------------------
<rewritten summary paragraph>

HIGHLIGHTED EXPERIENCE
----------------------------------------

Staff Engineer @ Previous Company
  • Bullet point most relevant to this job
  • Another relevant achievement

ATS KEYWORDS
----------------------------------------
kubernetes, platform engineering, AWS, distributed systems, ...

GAPS TO ADDRESS
----------------------------------------
  • 5+ years of Terraform experience (you have 2)
  • Public cloud certification (AWS SAA)
```

## Claude Call Details

| Setting | Value |
|---|---|
| Prompt template | `prompts/tailor_resume.md` |
| Operation | `resume_tailoring` |
| Max tokens | 2,000 |
| Temperature | 0.3 (slightly higher for natural language) |

## After Tailoring

`main.py` shows the keywords and gaps in the terminal, then asks if you want to mark the job as APPLIED. If confirmed, `job.status = APPLIED` and `job.applied_at` is set in the database.

# Job Search Agent — Claude Notes

## Project overview
Python tool that scores jobs against your profile across three career tracks:
- `ic` — Senior / Staff / Principal Engineer
- `architect` — Solutions Architect / Principal Architect
- `management` — Senior Manager / Director / Head of Engineering / VP

## Key design decisions
- Direct Anthropic SDK only — no LangChain
- All Claude responses are JSON validated by Pydantic
- Prompts live in `prompts/*.md` as XML-tagged templates
- LinkedIn handled manually via `inbox/linkedin.txt`
- Model: `claude-sonnet-4-6`

## Running the agent
```bash
python main.py                  # scrape + score all new jobs
python main.py --list           # show all scored jobs
python main.py --tailor 42      # tailor resume for job ID 42
python main.py --dashboard      # scrape + score, then launch dashboard
python main.py --dashboard-only # launch dashboard immediately (no scraping)
```

## File structure
- `models/`      — Pydantic data models
- `claude/`      — Anthropic SDK client, prompt loader, response parser
- `prompts/`     — Claude prompt templates
- `scrapers/`    — Job scrapers (LinkedIn, Adzuna, Ladders)
- `agents/`      — Profile parsing, scoring, tailoring
- `storage/`     — SQLite database layer
- `dashboard.py` — Streamlit UI (job list + resume tailoring)

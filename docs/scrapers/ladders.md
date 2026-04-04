# scrapers/ladders.py — Ladders.com Scraper

## Purpose

Scrapes job listings from [Ladders.com](https://www.theladders.com) — a job board focused on $100k+ roles. Because Ladders focuses on senior and executive compensation, it has a naturally high signal-to-noise ratio for the seniority levels this agent targets.

## Important Caveats

**Ladders uses HTML scraping** — unlike Adzuna (REST API) or LinkedIn (predictable structure), Ladders' HTML is scraped from their search results page. This means:

1. **It may break** if Ladders changes their front-end markup
2. **Multiple CSS selectors are tried** for each field as a fallback strategy
3. **If no job cards are found**, a warning is logged suggesting you check the selectors

This scraper is the most fragile in the system. If it returns 0 results, check `scrapers/ladders.py` and inspect Ladders' current HTML structure.

## Search URL

```
https://www.theladders.com/jobs/searchjobs?keywords=<keyword>&sort=date
```

One HTTP call per keyword in `config.scrapers.ladders.keywords`. Results are sorted by date (most recent first).

## HTML Selectors (Best-Effort)

The scraper tries multiple selectors for each field:

| Field | Selectors tried |
|---|---|
| Job card container | `li.job-card`, `div[data-testid='job-card']`, `article.job` |
| Title | `a.job-title`, `h2.title`, `[data-testid='job-title']` |
| Company | `span.company`, `[data-testid='company-name']` |
| Location | `span.location`, `[data-testid='job-location']` |
| URL | `a[href]` on the card |

If none match, `None` is returned for that field. Jobs missing both title and URL are dropped.

## Limitations

- **No description at scrape time** — Ladders search cards show only the job title, company, and location. The description field is `None` until a future fetch. Since `ScoringAgent` skips jobs with no description, Ladders jobs currently pass the scrape step but are filtered out during scoring.
- **Requires free account for full details** — The public search page shows limited info. Full descriptions may require authentication.

## Retry Logic

`_fetch_listings()` retries up to 3 times with exponential backoff (2s, 4s, 8s). Per-keyword failures are caught and logged without stopping the other keywords.

## Deduplication

URL-based deduplication runs within the scraper (same as Adzuna) to handle cases where the same job appears under multiple search keywords.

## When to Disable

If Ladders consistently returns 0 scored jobs (because descriptions are empty), set `enabled: false` in `config.yaml` to skip it:

```yaml
scrapers:
  ladders:
    enabled: false
```

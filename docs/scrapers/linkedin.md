# scrapers/linkedin.py — LinkedIn Manual Intake Scraper

## Purpose

Reads LinkedIn job URLs that you paste manually into `inbox/linkedin.txt`, fetches each posting with `httpx`, parses the HTML with BeautifulSoup, and returns `Job` objects for scoring.

## Why Manual Instead of Automated?

LinkedIn aggressively blocks automated scraping and requires authentication to view most job details. Rather than fight their bot detection:

- You browse LinkedIn normally and paste interesting job URLs into `inbox/linkedin.txt`
- The scraper fetches each URL, parses the HTML structure, and clears the inbox after processing
- This gives you full control over which LinkedIn jobs enter the pipeline

## Workflow

```
inbox/linkedin.txt (you paste URLs here)
      │
      ▼
_read_inbox()     → reads non-blank, non-comment lines
      │
      ▼
for each URL:
  _fetch_job(url) → httpx GET with browser-like headers
                  → BeautifulSoup parses title, company, location, description
                  → returns Job object
      │
      ▼
_clear_inbox()    → overwrites file with just the header comment
                    so URLs are not processed again next run
```

## Inbox File Format

```
# Paste LinkedIn job URLs here, one per line
https://www.linkedin.com/jobs/view/123456789
https://www.linkedin.com/jobs/view/987654321
```

Lines starting with `#` are ignored. The file is auto-created if it doesn't exist.

## HTML Selectors

LinkedIn's markup structure (may need updating if LinkedIn changes their front-end):

| Field | CSS Selector |
|---|---|
| `title` | `h1.top-card-layout__title` |
| `company` | `a.topcard__org-name-link` or `span.topcard__flavor` |
| `location` | `span.topcard__flavor--bullet` |
| `description` | `div.show-more-less-html__markup` |

If title or company can't be parsed, the URL is skipped with a warning.

## Anti-Bot Headers

The scraper uses browser-like headers to reduce blocking probability:
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...
Accept-Language: en-US,en;q=0.9
```

LinkedIn still may return minimal content for non-logged-in requests. If descriptions come back empty, the job will be skipped during scoring (`ScoringAgent` requires a non-empty description).

## Retry Logic

`_fetch_job()` retries up to 3 times with exponential backoff (2s, 4s, 8s). One failed URL does not stop the others — the loop continues and logs a warning.

## After Processing

The inbox file is cleared immediately after all URLs are fetched (success or failure). This prevents duplicate processing on the next run. If a URL failed to fetch, it is lost — you would need to re-paste it.

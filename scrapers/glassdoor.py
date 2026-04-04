# scrapers/glassdoor.py
# ─────────────────────────────────────────────────────────────────────────────
# Glassdoor scraper — parses the Glassdoor RSS feed for each keyword.
# Similar approach to the Indeed scraper — RSS entries give us basic metadata
# and a short snippet. Full descriptions require a separate fetch.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
from urllib.parse import urlencode

import feedparser

from models.job import Job, JobSource
from models.config_schema import GlassdoorConfig
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Glassdoor RSS feed base URL
GLASSDOOR_RSS_BASE = "https://www.glassdoor.com/feed/jobs/jobs.rss"


class GlassdoorScraper(BaseScraper):
    """
    Fetches jobs from Glassdoor using their public RSS feed.

    Glassdoor's RSS feed is less structured than Indeed's — company and location
    are often embedded in the title or description HTML. We do a best-effort
    parse and let the extraction agent clean up via Claude if needed.
    """

    def __init__(self, config: GlassdoorConfig) -> None:
        """
        Args:
            config: GlassdoorConfig from config.yaml — keywords.
        """
        super().__init__("glassdoor")
        self.config = config

    def scrape(self) -> list[Job]:
        """
        Fetches jobs for all configured keywords and returns deduplicated results.

        Returns:
            List of Job objects, deduplicated by URL.
        """
        if not self.config.enabled:
            logger.info("Glassdoor scraper is disabled in config")
            return []

        seen_urls: set[str] = set()
        jobs: list[Job] = []

        for keyword in self.config.keywords:
            try:
                new_jobs = self._fetch_feed(keyword)
                for job in new_jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        jobs.append(job)
            except Exception as e:
                logger.warning("Glassdoor feed failed for keyword '%s': %s", keyword, e)

        self.log_result(jobs)
        return jobs

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _feed_url(self, keyword: str) -> str:
        """
        Builds the Glassdoor RSS feed URL for a given keyword.

        Args:
            keyword: Search term, e.g. "solutions architect"

        Returns:
            Full RSS feed URL string.
        """
        params = {
            "sc.keyword": keyword,
            "locT":       "N",    # national search
            "jobType":    "all",
        }
        return f"{GLASSDOOR_RSS_BASE}?{urlencode(params)}"

    def _fetch_feed(self, keyword: str) -> list[Job]:
        """
        Fetches and parses the Glassdoor RSS feed for one keyword.

        Args:
            keyword: Search term to pass to the feed URL.

        Returns:
            List of Job objects parsed from the feed entries.
        """
        url = self._feed_url(keyword)
        logger.debug("Fetching Glassdoor RSS feed: %s", url)

        feed = feedparser.parse(url)

        if feed.bozo:
            logger.warning("Glassdoor RSS feed may be malformed for keyword '%s'", keyword)

        jobs: list[Job] = []
        for entry in feed.entries:
            try:
                job = self._parse_entry(entry)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning("Failed to parse Glassdoor entry: %s", e)

        logger.debug("Glassdoor RSS returned %d entries for keyword '%s'", len(jobs), keyword)
        return jobs

    def _parse_entry(self, entry: feedparser.FeedParserDict) -> Job | None:
        """
        Converts a single feedparser entry into a Job object.

        Args:
            entry: A feedparser entry dict from the Glassdoor RSS feed.

        Returns:
            A Job object, or None if required fields are missing.
        """
        url     = getattr(entry, "link", None)
        title   = getattr(entry, "title", None)
        summary = getattr(entry, "summary", None)

        if not url or not title:
            return None

        # Glassdoor titles are often "Job Title – Company Name"
        # Split on em dash or regular dash as a best-effort
        company = None
        clean_title = title
        for sep in [" \u2013 ", " - "]:
            if sep in title:
                parts = title.split(sep, 1)
                clean_title = parts[0].strip()
                company = parts[1].strip() if len(parts) > 1 else None
                break

        return Job(
            url=url,
            source=JobSource.GLASSDOOR,
            title=clean_title,
            company=company or "Unknown",
            description=summary,
        )

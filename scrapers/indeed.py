# scrapers/indeed.py
# ─────────────────────────────────────────────────────────────────────────────
# Indeed scraper — parses the Indeed RSS feed for each keyword.
# No browser needed — RSS feeds are plain XML and freely accessible.
# Each feed entry becomes a Job object with basic metadata.
# Full descriptions are fetched separately if needed.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
from urllib.parse import urlencode

import feedparser

from models.job import Job, JobSource
from models.config_schema import IndeedConfig
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Indeed RSS feed base URL — query params are appended per search
INDEED_RSS_BASE = "https://www.indeed.com/rss"


class IndeedScraper(BaseScraper):
    """
    Fetches jobs from Indeed using their public RSS feed.

    For each keyword in config, builds a feed URL and parses the entries.
    RSS entries include title, company, location, and a short description snippet.
    The snippet is not the full description — use the extraction agent for that.

    Indeed RSS feeds are rate-limited but generally reliable for a few
    searches per run. We do not need authentication or a browser.
    """

    def __init__(self, config: IndeedConfig) -> None:
        """
        Args:
            config: IndeedConfig from config.yaml — keywords, location, radius.
        """
        super().__init__("indeed")
        self.config = config

    def scrape(self) -> list[Job]:
        """
        Fetches jobs for all configured keywords and returns deduplicated results.

        Returns:
            List of Job objects, deduplicated by URL.
        """
        if not self.config.enabled:
            logger.info("Indeed scraper is disabled in config")
            return []

        seen_urls: set[str] = set()
        jobs: list[Job] = []

        for keyword in self.config.keywords:
            try:
                new_jobs = self._fetch_feed(keyword)
                for job in new_jobs:
                    # Deduplicate by URL across keywords
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        jobs.append(job)
            except Exception as e:
                logger.warning("Indeed feed failed for keyword '%s': %s", keyword, e)

        self.log_result(jobs)
        return jobs

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _feed_url(self, keyword: str) -> str:
        """
        Builds the Indeed RSS feed URL for a given keyword, location, and radius.

        Args:
            keyword: Search term, e.g. "software engineer"

        Returns:
            Full RSS feed URL string.
        """
        params = {
            "q":      keyword,
            "l":      self.config.location,
            "radius": self.config.radius_miles,
            "sort":   "date",   # most recent first
        }
        return f"{INDEED_RSS_BASE}?{urlencode(params)}"

    def _fetch_feed(self, keyword: str) -> list[Job]:
        """
        Fetches and parses the Indeed RSS feed for one keyword.

        Args:
            keyword: Search term to pass to the feed URL.

        Returns:
            List of Job objects parsed from the feed entries.
        """
        url = self._feed_url(keyword)
        logger.debug("Fetching Indeed RSS feed: %s", url)

        feed = feedparser.parse(url)

        if feed.bozo:
            # feedparser sets bozo=True when the feed is malformed
            logger.warning("Indeed RSS feed may be malformed for keyword '%s'", keyword)

        jobs: list[Job] = []
        for entry in feed.entries:
            try:
                job = self._parse_entry(entry)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning("Failed to parse Indeed entry: %s", e)

        logger.debug("Indeed RSS returned %d entries for keyword '%s'", len(jobs), keyword)
        return jobs

    def _parse_entry(self, entry: feedparser.FeedParserDict) -> Job | None:
        """
        Converts a single feedparser entry into a Job object.

        Args:
            entry: A feedparser entry dict from the Indeed RSS feed.

        Returns:
            A Job object, or None if required fields are missing.
        """
        url     = getattr(entry, "link", None)
        title   = getattr(entry, "title", None)
        summary = getattr(entry, "summary", None)

        if not url or not title:
            return None

        # Indeed RSS encodes "Job Title - Company Name - Location" in the title
        # We do a best-effort parse — full extraction is done by Claude if needed
        company, location = self._parse_title_meta(title)

        return Job(
            url=url,
            source=JobSource.INDEED,
            title=title.split(" - ")[0].strip() if " - " in title else title,
            company=company or "Unknown",
            location=location,
            description=summary,   # RSS summary is a snippet, not the full description
        )

    @staticmethod
    def _parse_title_meta(raw_title: str) -> tuple[str | None, str | None]:
        """
        Attempts to extract company and location from an Indeed RSS title string.
        Indeed formats titles as: "Job Title - Company - Location"

        Args:
            raw_title: The raw title string from the RSS entry.

        Returns:
            Tuple of (company, location), either may be None if not parseable.
        """
        parts = [p.strip() for p in raw_title.split(" - ")]
        company  = parts[1] if len(parts) > 1 else None
        location = parts[2] if len(parts) > 2 else None
        return company, location

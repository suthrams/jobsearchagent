# scrapers/base.py
# ─────────────────────────────────────────────────────────────────────────────
# Abstract base class for all scrapers.
# Every scraper (LinkedIn, Indeed, Glassdoor, Ladders) inherits from this
# and implements the scrape() method, which returns a list of Job objects.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from models.job import Job

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for all job scrapers.

    All scrapers must implement scrape(), which returns a list of Job objects.
    The base class provides shared logging and a helper for deduplication.

    Subclasses:
      - LinkedInScraper  : reads URLs from inbox/linkedin.txt
      - IndeedScraper    : parses Indeed RSS feed
      - GlassdoorScraper : parses Glassdoor RSS feed
      - LaddersScraper   : scrapes Ladders job listings
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: Human-readable name for this scraper, used in log messages.
        """
        self.name = name
        self.logger = logging.getLogger(f"scrapers.{name}")

    @abstractmethod
    def scrape(self) -> list[Job]:
        """
        Fetches job postings from the source and returns them as Job objects.
        Each Job should have at minimum: url, source, title, company.
        description is populated here if easily available, otherwise left for
        the extraction agent to fill in via Claude.

        Returns:
            List of Job objects. May be empty if no new jobs are found.
        """
        ...

    def log_result(self, jobs: list[Job]) -> None:
        """
        Logs a summary of the scrape result. Called by subclasses after scrape().

        Args:
            jobs: The list of Job objects returned by scrape().
        """
        self.logger.info("%s scraper found %d jobs", self.name, len(jobs))

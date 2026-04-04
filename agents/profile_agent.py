# agents/profile_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Parses your resume PDF into a Profile object using Claude.
# Runs once when your resume changes — the result is cached as JSON
# so Claude is not called again on every run.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
from pathlib import Path

import pdfplumber

from claude.client import ClaudeClient
from claude.prompt_loader import PromptLoader
from claude.response_parser import ResponseParser
from models.profile import Profile

logger = logging.getLogger(__name__)

# Where the parsed profile is cached between runs
PROFILE_CACHE_PATH = Path("data/profile.json")


class ProfileAgent:
    """
    Extracts a structured Profile from your resume PDF using Claude.

    Workflow:
      1. Check if a cached profile.json exists and is newer than the resume
      2. If cache is fresh, load and return it — no Claude call needed
      3. If cache is stale or missing, extract text from the PDF with pdfplumber
      4. Call Claude with the parse_resume prompt
      5. Validate the response into a Profile object
      6. Save the profile to data/profile.json for future runs
    """

    def __init__(
        self,
        client: ClaudeClient,
        loader: PromptLoader,
        parser: ResponseParser,
    ) -> None:
        """
        Args:
            client : ClaudeClient for making API calls
            loader : PromptLoader for loading the parse_resume prompt
            parser : ResponseParser for validating Claude's JSON response
        """
        self.client = client
        self.loader = loader
        self.parser = parser

    def load(self, resume_path: str) -> Profile:
        """
        Returns the parsed Profile for the given resume PDF.
        Uses the cache if available and up-to-date.

        Args:
            resume_path: Path to your resume PDF file.

        Returns:
            A validated Profile object.
        """
        resume = Path(resume_path)
        if not resume.exists():
            raise FileNotFoundError(
                f"Resume PDF not found at {resume_path}. "
                "Update resume_path in your config or main.py."
            )

        # Use the cache if it exists and is newer than the resume file
        if self._cache_is_fresh(resume):
            logger.info("Loading profile from cache: %s", PROFILE_CACHE_PATH)
            return self._load_cache()

        # Cache is missing or stale — re-parse the resume
        logger.info("Parsing resume with Claude: %s", resume_path)
        profile = self._parse_resume(resume)

        # Save to cache for next run
        self._save_cache(profile)
        logger.info("Profile cached at %s", PROFILE_CACHE_PATH)

        return profile

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _cache_is_fresh(self, resume: Path) -> bool:
        """
        Returns True if the cached profile exists and is newer than the resume PDF.
        A stale cache means the resume has been updated and needs re-parsing.
        """
        if not PROFILE_CACHE_PATH.exists():
            return False
        cache_mtime = PROFILE_CACHE_PATH.stat().st_mtime
        resume_mtime = resume.stat().st_mtime
        return cache_mtime > resume_mtime

    def _load_cache(self) -> Profile:
        """
        Loads and validates the cached profile JSON.
        """
        data = json.loads(PROFILE_CACHE_PATH.read_text(encoding="utf-8"))
        return Profile.model_validate(data)

    def _save_cache(self, profile: Profile) -> None:
        """
        Serialises the profile to JSON and writes it to the cache file.
        Creates the data/ directory if it does not exist.
        """
        PROFILE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROFILE_CACHE_PATH.write_text(
            profile.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _parse_resume(self, resume: Path) -> Profile:
        """
        Extracts text from the PDF and sends it to Claude for parsing.

        Args:
            resume: Path to the resume PDF.

        Returns:
            A validated Profile object.
        """
        # Extract raw text from the PDF using pdfplumber
        resume_text = self._extract_pdf_text(resume)

        # Load and render the prompt template
        prompt = self.loader.load("parse_resume", resume_text=resume_text)

        # Call Claude — parse_resume operation settings apply
        raw_response = self.client.call(
            system=prompt,
            user="Please parse the resume above and return the JSON object.",
            operation="resume_parsing",
        )

        # Validate the response into a Profile object
        return self.parser.parse(raw_response, Profile)

    @staticmethod
    def _extract_pdf_text(resume: Path) -> str:
        """
        Extracts all text from a PDF file using pdfplumber.
        Joins pages with double newlines to preserve section breaks.

        Args:
            resume: Path to the PDF file.

        Returns:
            The full extracted text as a single string.
        """
        pages: list[str] = []
        with pdfplumber.open(resume) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)

        if not pages:
            raise ValueError(
                f"Could not extract any text from {resume}. "
                "Make sure it is a text-based PDF, not a scanned image."
            )

        return "\n\n".join(pages)

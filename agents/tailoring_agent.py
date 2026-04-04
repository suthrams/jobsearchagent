# agents/tailoring_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Rewrites your resume sections to match a specific job posting.
# Called only when you decide to apply — not on every scored job.
# Saves the tailored output as a text file in output/resumes/.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from claude.client import ClaudeClient
from claude.prompt_loader import PromptLoader
from claude.response_parser import ResponseParser, ResponseParseError
from models.job import Job, CareerTrack
from models.profile import Profile

logger = logging.getLogger(__name__)


@dataclass
class TailoredResume:
    """
    The output of a resume tailoring run.
    Contains rewritten content ready to paste into your resume template.

    Fields:
        tailored_summary       : Rewritten professional summary for this job
        highlighted_experience : Per-role bullet points most relevant to this job
        keywords               : ATS keywords from the posting that match your background
        gaps                   : Requirements in the job that you do not clearly meet
        output_path            : Where the text file was saved
    """
    tailored_summary:        str
    highlighted_experience:  list[dict]
    keywords:                list[str]
    gaps:                    list[str]
    output_path:             Path


class TailoringAgent:
    """
    Rewrites resume sections for a specific job and career track.

    Workflow:
      1. Render the tailor_resume prompt with profile + job + track
      2. Call Claude and validate the response
      3. Format the output as a readable text file
      4. Save to output/resumes/<company>_<title>_<track>.txt
      5. Return a TailoredResume dataclass with all fields populated
    """

    def __init__(
        self,
        client: ClaudeClient,
        loader: PromptLoader,
        parser: ResponseParser,
        output_dir: str = "output/resumes",
    ) -> None:
        """
        Args:
            client     : ClaudeClient for API calls
            loader     : PromptLoader for the tailor_resume prompt
            parser     : ResponseParser for validating Claude's JSON
            output_dir : Directory where tailored resume files are saved
        """
        self.client     = client
        self.loader     = loader
        self.parser     = parser
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tailor(self, job: Job, profile: Profile, track: CareerTrack) -> TailoredResume:
        """
        Generates a tailored resume for the given job and career track.

        Args:
            job     : The Job object to tailor for. Must have a description.
            profile : The candidate's parsed Profile.
            track   : Which career track to optimise the resume for.

        Returns:
            A TailoredResume object with rewritten content and the output file path.

        Raises:
            ValueError          : If the job has no description.
            ResponseParseError  : If Claude returns invalid JSON.
        """
        if not job.description:
            raise ValueError(
                f"Job '{job.title}' at '{job.company}' has no description — "
                "cannot tailor resume without job content."
            )

        logger.info(
            "Tailoring resume for: %s at %s (track=%s)",
            job.title, job.company, track.value,
        )

        # Render the tailoring prompt
        prompt = self.loader.load(
            "tailor_resume",
            profile=json.dumps(profile.model_dump(), indent=2, default=str),
            job=self._job_text(job),
            track=track.value,
        )

        # Call Claude
        raw_response = self.client.call(
            system=prompt,
            user="Please tailor the resume for this job and return the JSON object.",
            operation="resume_tailoring",
        )

        # Parse the response into a plain dict first — no dedicated Pydantic model
        # for tailoring output since it's freeform text, not a domain object
        import json as _json
        from claude.response_parser import ResponseParser as _RP
        rp = _RP()
        # We parse manually here since TailoredResume is a dataclass not a BaseModel
        cleaned = rp._strip_code_fences(raw_response)
        json_str = rp._extract_json(cleaned)
        data = _json.loads(json_str)

        # Build the output text file
        output_path = self._save_output(job, track, data)

        result = TailoredResume(
            tailored_summary=data.get("tailored_summary", ""),
            highlighted_experience=data.get("highlighted_experience", []),
            keywords=data.get("keywords", []),
            gaps=data.get("gaps", []),
            output_path=output_path,
        )

        logger.info("Tailored resume saved to: %s", output_path)
        return result

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _job_text(self, job: Job) -> str:
        """
        Formats the job as plain text for injection into the tailoring prompt.
        """
        parts = [
            f"Title: {job.title}",
            f"Company: {job.company}",
            f"Location: {job.location or 'Not specified'}",
            f"\nDescription:\n{job.description}",
        ]
        return "\n".join(parts)

    def _save_output(self, job: Job, track: CareerTrack, data: dict) -> Path:
        """
        Formats the tailoring output as a human-readable text file and saves it.

        File name format: <company>_<title>_<track>.txt
        Special characters are replaced with underscores.

        Args:
            job   : The job being applied to
            track : The career track
            data  : The parsed dict from Claude's JSON response

        Returns:
            The Path where the file was saved.
        """
        # Build a safe filename
        def safe(s: str) -> str:
            return "".join(c if c.isalnum() else "_" for c in s).strip("_")

        filename = f"{safe(job.company)}_{safe(job.title)}_{track.value}.txt"
        path = self.output_dir / filename

        # Format the content
        lines = [
            f"TAILORED RESUME — {job.title} at {job.company}",
            f"Track: {track.value.upper()}",
            f"URL: {job.url}",
            "=" * 70,
            "",
            "PROFESSIONAL SUMMARY",
            "-" * 40,
            data.get("tailored_summary", ""),
            "",
            "HIGHLIGHTED EXPERIENCE",
            "-" * 40,
        ]

        for role in data.get("highlighted_experience", []):
            lines.append(f"\n{role.get('title', '')} @ {role.get('company', '')}")
            for bullet in role.get("bullets", []):
                lines.append(f"  • {bullet}")

        lines += [
            "",
            "ATS KEYWORDS",
            "-" * 40,
            ", ".join(data.get("keywords", [])),
            "",
            "GAPS TO ADDRESS",
            "-" * 40,
        ]
        for gap in data.get("gaps", []):
            lines.append(f"  • {gap}")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

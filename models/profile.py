# models/profile.py
# ─────────────────────────────────────────────────────────────────────────────
# Pydantic model representing your professional profile.
# Parsed once from your resume PDF by Claude, then reused for every
# job scoring and resume tailoring call — avoids re-parsing on every run.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ─── Sub-models ───────────────────────────────────────────────────────────────

class Experience(BaseModel):
    """
    A single role in your work history.
    Parsed from your resume PDF by Claude during profile extraction.
    Used by the scoring prompt to evaluate seniority and relevance.
    """
    company:      str            = Field(..., description="Company name")
    title:        str            = Field(..., description="Your job title at this company")
    start_year:   int            = Field(..., description="Year you started this role")
    end_year:     Optional[int]  = Field(None, description="Year you left — None if current role")
    description:  Optional[str]  = Field(None, description="Brief summary of responsibilities and achievements")
    technologies: list[str]      = Field(default_factory=list, description="Technologies used in this role")

    @property
    def years(self) -> float:
        """
        Returns the number of years spent in this role.
        Uses the current year for roles still in progress.
        """
        from datetime import datetime
        end = self.end_year or datetime.utcnow().year
        return max(0, end - self.start_year)


class Education(BaseModel):
    """
    A single education entry from your resume.
    Degree and institution are the minimum required fields.
    """
    institution: str           = Field(..., description="University or institution name")
    degree:      str           = Field(..., description="Degree type, e.g. B.S. Computer Science")
    year:        Optional[int] = Field(None, description="Graduation year")


class Certification(BaseModel):
    """
    A professional certification — AWS, GCP, Azure, PMP, etc.
    Used by Claude to boost scores for roles requiring specific certifications.
    """
    name:   str            = Field(..., description="Certification name, e.g. AWS Solutions Architect")
    issuer: Optional[str]  = Field(None, description="Issuing organization, e.g. Amazon Web Services")
    year:   Optional[int]  = Field(None, description="Year obtained")


# ─── Main model ───────────────────────────────────────────────────────────────

class Profile(BaseModel):
    """
    Your professional profile, extracted from your resume PDF by Claude.
    Stored as a JSON file alongside the database so it does not need
    to be re-parsed on every run — only re-parse when your resume changes.

    Used in two ways:
      1. Injected into the job scoring prompt so Claude can compare
         your background against the job requirements
      2. Injected into the resume tailoring prompt so Claude can
         rewrite your resume to match a specific job
    """

    # --- Personal ---
    # Name and headline are used in tailored resume output headers
    name:      str           = Field(..., description="Your full name")
    headline:  Optional[str] = Field(None, description="One-line professional summary, e.g. 'Staff Engineer with 12 years in cloud infrastructure'")
    email:     Optional[str] = Field(None, description="Contact email")
    location:  Optional[str] = Field(None, description="Your location, e.g. Atlanta, GA")

    # --- Experience ---
    # Ordered most recent first — Claude reads them in this order
    experience: list[Experience] = Field(default_factory=list, description="Work history, most recent first")

    # --- Skills ---
    # Flat list of technologies and tools — e.g. ["Python", "GCP", "Kubernetes"]
    # Claude uses this to match against job requirements quickly
    skills: list[str] = Field(default_factory=list, description="Technologies, tools, and platforms you know")

    # --- Education ---
    education: list[Education] = Field(default_factory=list, description="Degrees and institutions")

    # --- Certifications ---
    certifications: list[Certification] = Field(default_factory=list, description="Professional certifications")

    # --- Summary ---
    # Optional free-text summary from your resume — used as context for tailoring
    summary: Optional[str] = Field(None, description="Professional summary paragraph from your resume")

    @property
    def total_years_experience(self) -> float:
        """
        Returns the sum of years across all experience entries.
        Useful for quick seniority checks in the scoring prompt.
        """
        return sum(e.years for e in self.experience)

    @property
    def current_title(self) -> Optional[str]:
        """
        Returns the title of your most recent role (end_year is None).
        Falls back to the first entry in the list if none is marked current.
        """
        for e in self.experience:
            if e.end_year is None:
                return e.title
        return self.experience[0].title if self.experience else None

    class Config:
        """
        Pydantic model configuration.
        - populate_by_name : allows fields to be set by their Python name
        """
        populate_by_name = True

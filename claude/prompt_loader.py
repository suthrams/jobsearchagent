# claude/prompt_loader.py
# ─────────────────────────────────────────────────────────────────────────────
# Loads prompt templates from the prompts/ directory and fills in variables.
# Prompts are stored as .md files with XML-tagged placeholders like <profile/>.
# This keeps prompt text out of Python code and makes them easy to iterate on.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default location of prompt files relative to the project root
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PromptLoader:
    """
    Reads prompt templates from prompts/*.md and substitutes variables.

    Template variables use double-brace syntax: {{variable_name}}
    They map directly to keyword arguments passed to load().

    Example template (prompts/score_job.md):
        You are a career coach. Here is the candidate profile:
        <profile>
        {{profile}}
        </profile>
        Here is the job posting:
        <job>
        {{job}}
        </job>

    Example usage:
        loader = PromptLoader()
        prompt = loader.load("score_job", profile=profile_text, job=job_text)
    """

    def __init__(self, prompts_dir: Path = PROMPTS_DIR) -> None:
        """
        Args:
            prompts_dir: Path to the directory containing .md prompt files.
                         Defaults to the prompts/ folder in the project root.
        """
        self.prompts_dir = prompts_dir

        if not self.prompts_dir.exists():
            raise FileNotFoundError(
                f"Prompts directory not found: {self.prompts_dir}. "
                "Make sure prompts/ exists in the project root."
            )

        logger.debug("PromptLoader initialised | prompts_dir=%s", self.prompts_dir)

    def load(self, template_name: str, **variables: str) -> str:
        """
        Loads a prompt template and substitutes all {{variable}} placeholders.

        Args:
            template_name : Filename without extension, e.g. 'score_job'
                            maps to prompts/score_job.md
            **variables   : Key-value pairs to substitute into the template.
                            Keys must match the {{placeholders}} in the file.

        Returns:
            The fully rendered prompt string ready to send to Claude.

        Raises:
            FileNotFoundError : If the .md file does not exist.
            KeyError          : If a placeholder in the template has no matching variable.
        """
        path = self.prompts_dir / f"{template_name}.md"

        if not path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {path}. "
                f"Expected a file at prompts/{template_name}.md"
            )

        # Read the raw template text
        template = path.read_text(encoding="utf-8")

        # Substitute each {{placeholder}} with its value
        # We do this manually rather than using str.format() to avoid
        # conflicts with curly braces that appear in JSON examples in prompts
        rendered = template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"   # produces {{key}}
            if placeholder not in rendered:
                logger.warning(
                    "Variable '%s' was passed to prompt '%s' but no {{%s}} placeholder was found",
                    key, template_name, key,
                )
            rendered = rendered.replace(placeholder, str(value))

        # Check for any unfilled placeholders remaining in the template
        import re
        unfilled = re.findall(r"\{\{(\w+)\}\}", rendered)
        if unfilled:
            raise KeyError(
                f"Prompt '{template_name}' has unfilled placeholders: {unfilled}. "
                "Pass them as keyword arguments to load()."
            )

        logger.debug("Prompt loaded | template=%s | variables=%s", template_name, list(variables.keys()))

        return rendered

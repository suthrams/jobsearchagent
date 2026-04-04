# claude/client.py
# ─────────────────────────────────────────────────────────────────────────────
# Thin wrapper around the Anthropic SDK.
# All Claude API calls in this project go through this client — nowhere else.
# Handles authentication, retry logic, and consistent error reporting.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models.config_schema import ClaudeConfig

logger = logging.getLogger(__name__)


class ClaudeClient:
    """
    Wraps the Anthropic SDK client.
    Instantiated once at startup and injected into agents that need it.

    Responsibilities:
    - Loads the API key from the environment
    - Provides a single call() method used by all agents
    - Applies retry logic with exponential backoff on rate limit / server errors
    - Logs every request at DEBUG level for cost tracking
    """

    def __init__(self, config: ClaudeConfig) -> None:
        """
        Initialises the Anthropic client.
        Reads ANTHROPIC_API_KEY from the environment — must be set in .env.

        Args:
            config: ClaudeConfig section from config.yaml, contains model name,
                    max_tokens, and temperature settings per operation.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file and make sure python-dotenv is loaded."
            )

        # The Anthropic SDK client — used for all API calls
        self._client = anthropic.Anthropic(api_key=api_key)

        # Holds model name, max_tokens, and temperature per operation type
        self.config = config

        logger.debug("ClaudeClient initialised with model=%s", config.model)

    @retry(
        # Retry up to 3 times on rate limit or server errors
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError)),
        # Wait 2s, then 4s, then 8s between attempts
        wait=wait_exponential(multiplier=1, min=2, max=8),
        stop=stop_after_attempt(3),
        # Log a warning before each retry attempt
        before_sleep=lambda retry_state: logger.warning(
            "Claude API error — retrying (attempt %d/3)", retry_state.attempt_number
        ),
    )
    def call(
        self,
        *,
        system: str,
        user: str,
        operation: str,
    ) -> str:
        """
        Makes a single Claude API call and returns the response text.

        Args:
            system    : System prompt — sets Claude's role and output format.
            user      : User message — the actual content to process.
            operation : One of 'resume_parsing', 'job_scoring', 'resume_tailoring'.
                        Used to look up max_tokens and temperature from config.

        Returns:
            The text content of Claude's response as a plain string.
            Callers are responsible for parsing JSON from this string.

        Raises:
            ValueError          : If operation is not a recognised key.
            anthropic.APIError  : If all retry attempts are exhausted.
        """
        # Look up per-operation settings from config
        max_tokens  = getattr(self.config.max_tokens,  operation, None)
        temperature = getattr(self.config.temperature, operation, None)

        if max_tokens is None or temperature is None:
            raise ValueError(
                f"Unknown operation '{operation}'. "
                "Must be one of: resume_parsing, job_scoring, resume_tailoring."
            )

        logger.debug(
            "Claude call | operation=%s | model=%s | max_tokens=%d | temperature=%.1f",
            operation, self.config.model, max_tokens, temperature,
        )

        # Make the API call using the messages endpoint
        message = self._client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        # Extract text from the first content block
        # Claude always returns at least one text block for our use case
        response_text = message.content[0].text

        logger.debug(
            "Claude response | operation=%s | input_tokens=%d | output_tokens=%d",
            operation,
            message.usage.input_tokens,
            message.usage.output_tokens,
        )

        return response_text

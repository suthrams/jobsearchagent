# claude/response_parser.py
# ─────────────────────────────────────────────────────────────────────────────
# Parses and validates Claude's JSON responses into Pydantic models.
# Claude is prompted to return JSON — this module extracts it safely
# and raises clear errors if the response is malformed or missing fields.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
import re
from typing import TypeVar, Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# Generic type variable so parse() can return the correct Pydantic model type
T = TypeVar("T", bound=BaseModel)


class ResponseParseError(Exception):
    """
    Raised when Claude's response cannot be parsed into the expected model.
    Includes the raw response text to aid debugging.
    """
    def __init__(self, message: str, raw_response: str) -> None:
        super().__init__(message)
        self.raw_response = raw_response


class ResponseParser:
    """
    Extracts JSON from Claude's response text and validates it against
    a Pydantic model. Handles the common case where Claude wraps its
    JSON in markdown code fences (```json ... ```) despite being told not to.

    Usage:
        parser = ResponseParser()
        score = parser.parse(raw_text, TrackScores)
    """

    def parse_list(self, raw_response: str, model: Type[T]) -> list[T]:
        """
        Parses a Claude response that contains a JSON array and validates
        each element against a Pydantic model.

        Args:
            raw_response : The raw text returned by Claude.
            model        : The Pydantic model class to validate each item against.

        Returns:
            A list of validated model instances.

        Raises:
            ResponseParseError : If the response is not a JSON array or validation fails.
        """
        cleaned = self._strip_code_fences(raw_response)
        json_str = self._extract_json(cleaned)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error("JSON decode error | %s | raw=%s", e, raw_response[:200])
            raise ResponseParseError(
                f"Claude returned invalid JSON: {e}",
                raw_response=raw_response,
            ) from e

        if not isinstance(data, list):
            raise ResponseParseError(
                "Expected a JSON array but got an object.",
                raw_response=raw_response,
            )

        try:
            return [model.model_validate(item) for item in data]
        except ValidationError as e:
            logger.error("Pydantic validation error | model=%s | %s", model.__name__, e)
            raise ResponseParseError(
                f"Claude's JSON did not match expected schema for {model.__name__}: {e}",
                raw_response=raw_response,
            ) from e

    def parse(self, raw_response: str, model: Type[T]) -> T:
        """
        Parses a Claude response string into a validated Pydantic model instance.

        Steps:
          1. Strip markdown code fences if present
          2. Extract the first JSON object or array from the text
          3. Parse the JSON string into a dict
          4. Validate the dict against the Pydantic model

        Args:
            raw_response : The raw text returned by Claude.
            model        : The Pydantic model class to validate against.

        Returns:
            A validated instance of the given Pydantic model.

        Raises:
            ResponseParseError : If JSON cannot be extracted or validation fails.
        """
        # Step 1 — strip markdown code fences
        cleaned = self._strip_code_fences(raw_response)

        # Step 2 — extract JSON substring
        json_str = self._extract_json(cleaned)

        # Step 3 — parse JSON string to dict
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error("JSON decode error | %s | raw=%s", e, raw_response[:200])
            raise ResponseParseError(
                f"Claude returned invalid JSON: {e}",
                raw_response=raw_response,
            ) from e

        # Step 4 — validate against the Pydantic model
        try:
            instance = model.model_validate(data)
        except ValidationError as e:
            logger.error("Pydantic validation error | model=%s | %s", model.__name__, e)
            raise ResponseParseError(
                f"Claude's JSON did not match expected schema for {model.__name__}: {e}",
                raw_response=raw_response,
            ) from e

        logger.debug("Response parsed successfully | model=%s", model.__name__)
        return instance

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _strip_code_fences(self, text: str) -> str:
        """
        Removes markdown code fences from around JSON.
        Claude sometimes wraps its output in ```json ... ``` despite instructions.

        Handles:
          ```json\n{...}\n```
          ```\n{...}\n```
        """
        # Match opening fence with optional language tag and closing fence
        pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _extract_json(self, text: str) -> str:
        """
        Finds the first complete JSON object ({...}) or array ([...]) in the text.
        Handles cases where Claude adds a preamble sentence before the JSON.

        Returns the JSON substring, or raises ResponseParseError if none found.
        """
        # Find the first { or [ — start of JSON object or array
        start = -1
        open_char = ""
        close_char = ""

        for i, ch in enumerate(text):
            if ch == "{":
                start = i
                open_char = "{"
                close_char = "}"
                break
            if ch == "[":
                start = i
                open_char = "["
                close_char = "]"
                break

        if start == -1:
            raise ResponseParseError(
                "No JSON object or array found in Claude's response.",
                raw_response=text,
            )

        # Walk forward tracking brace depth to find the matching close
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        raise ResponseParseError(
            "JSON in Claude's response is not properly closed.",
            raw_response=text,
        )

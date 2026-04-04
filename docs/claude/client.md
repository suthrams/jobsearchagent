# claude/client.py — Anthropic SDK Wrapper

## Purpose

A thin wrapper around the Anthropic Python SDK. **Every Claude API call in the project goes through this single class.** No other file imports `anthropic` directly. This centralises authentication, retry logic, logging, and per-operation settings.

## Design Principle: Single Seam

Having one class own all Claude calls means:
- API key management is in one place
- Retry behaviour is consistent across all agents
- Token usage is always logged for cost tracking
- Swapping models or adding streaming in the future requires changes in exactly one file

## Agentic Pattern: Retry with Exponential Backoff

Uses `tenacity` to retry on `RateLimitError` and `APIStatusError`:

```
Attempt 1 → fails (rate limit)
Wait 2s
Attempt 2 → fails (server error)
Wait 4s
Attempt 3 → succeeds (or raises)
```

Configured with:
- `stop_after_attempt(3)` — maximum 3 tries
- `wait_exponential(multiplier=1, min=2, max=8)` — 2s, 4s, 8s
- Logs a WARNING before each retry so you can see it in the terminal

## Public Interface

### `ClaudeClient(config: ClaudeConfig)`

Reads `ANTHROPIC_API_KEY` from the environment (loaded from `.env` by `main.py`). Raises `EnvironmentError` if missing.

### `call(*, system, user, operation) → str`

Makes a single Claude API call using the Messages endpoint.

| Parameter | Type | Purpose |
|---|---|---|
| `system` | `str` | System prompt — sets Claude's role and output format |
| `user` | `str` | User message — the actual content to process |
| `operation` | `str` | One of: `resume_parsing`, `job_scoring`, `resume_tailoring` |

Returns the raw response text as a string. Callers are responsible for parsing JSON from this string (via `ResponseParser`).

`operation` maps to per-operation settings in `config.yaml`:

| Operation | max_tokens | temperature |
|---|---|---|
| `resume_parsing` | 1,000 | 0.1 |
| `job_scoring` | 2,000 | 0.1 |
| `resume_tailoring` | 2,000 | 0.3 |

## Logging

Every call logs at DEBUG level:
- Before: `operation`, `model`, `max_tokens`, `temperature`
- After: `input_tokens`, `output_tokens`

This lets you audit the `output/logs/run.log` to see exact token usage and estimate costs after a run.

## What It Does NOT Do

- It does not parse JSON — that is `ResponseParser`'s job.
- It does not build prompts — that is `PromptLoader`'s job.
- It does not handle streaming — all calls use the standard blocking Messages API.
- It does not cache responses — caching happens at the agent level (ProfileAgent).

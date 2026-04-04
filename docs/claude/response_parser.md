# claude/response_parser.py — Claude Response Parser

## Purpose

Extracts JSON from Claude's response text and validates it against a Pydantic model. This is the **trust boundary** of the system — Claude's output is untrusted text until this class validates it into a typed Python object.

## Why This Exists

Claude is instructed to return JSON, but it sometimes:
1. Wraps the JSON in markdown code fences (` ```json ... ``` `)
2. Adds a preamble sentence before the JSON
3. Returns JSON that doesn't match the expected schema

`ResponseParser` handles all three cases defensively, so agents never receive malformed data.

## Agentic Pattern: Structured Output Validation

This class is the implementation of the **Structured Output** pattern:

```
Claude raw text (untrusted)
      │
      ▼
_strip_code_fences()    → removes ```json ... ``` wrapping
      │
      ▼
_extract_json()         → finds the first { or [ and walks to matching close
      │
      ▼
json.loads()            → parses to Python dict/list
      │
      ▼
Model.model_validate()  → Pydantic validates shape, types, constraints
      │
      ▼
Typed Python object (trusted)
```

If any step fails, `ResponseParseError` is raised with the raw response included for debugging.

## Public Interface

### `parse(raw_response, model) → T`

Parses a Claude response into a single Pydantic model instance.

```python
profile = parser.parse(raw_text, Profile)
```

### `parse_list(raw_response, model) → list[T]`

Parses a Claude response into a list of Pydantic model instances. Used when Claude returns a JSON array (e.g., batch scoring returns one score per job).

```python
scores = parser.parse_list(raw_text, BatchJobScore)
```

Both methods raise `ResponseParseError` on failure. The error includes `raw_response` so you can inspect exactly what Claude returned.

## Error Class

### `ResponseParseError(message, raw_response)`

- Extends `Exception`
- `.raw_response` — the original Claude text that failed to parse
- Logged at ERROR level before raising, so `output/logs/run.log` always has the failing response

## Private Helpers

### `_strip_code_fences(text) → str`

Removes ` ```json ... ``` ` or ` ``` ... ``` ` wrapping using a regex. Returns the inner content, or the original text unchanged if no fences are found.

### `_extract_json(text) → str`

Finds the first `{` or `[` in the text and walks forward tracking brace depth to find the matching `}` or `]`. Returns the balanced JSON substring.

This handles:
- Preamble text before the JSON: `"Here is the result: { ... }"`
- Trailing explanation after the JSON: `"{ ... } I hope this helps!"`

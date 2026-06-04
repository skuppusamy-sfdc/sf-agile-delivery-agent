"""Validate LLM outputs against JSON schemas.

Uses Python's jsonschema module if available, otherwise falls back to basic structural checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def load_schema(index_name: str) -> dict | None:
    """Load the JSON schema for a given index type."""
    schema_file = SCHEMAS_DIR / f"{index_name.replace('_', '-')}.schema.json"
    if not schema_file.exists():
        # Try alternate naming
        schema_file = SCHEMAS_DIR / f"{index_name}.schema.json"
    if not schema_file.exists():
        return None
    return json.loads(schema_file.read_text())


def validate_output(output: dict, index_name: str) -> tuple[bool, list[str]]:
    """Validate an LLM output against its schema.

    Returns (is_valid, list_of_errors).
    """
    schema = load_schema(index_name)
    if not schema:
        return True, []

    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(output))
        if errors:
            return False, [f"{e.path}: {e.message}" for e in errors[:5]]
        return True, []
    except ImportError:
        return _basic_validate(output, schema, index_name)


def _basic_validate(output: dict, schema: dict, index_name: str) -> tuple[bool, list[str]]:
    """Fallback validation without jsonschema library."""
    errors = []

    if not isinstance(output, dict):
        return False, ["Output is not a JSON object"]

    required = schema.get("required", [])
    for field in required:
        if field not in output:
            errors.append(f"Missing required field: {field}")

    props = schema.get("properties", {})
    for field, field_schema in props.items():
        if field not in output:
            continue
        value = output[field]
        expected_type = field_schema.get("type")
        if expected_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{field}' should be array, got {type(value).__name__}")
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(f"Field '{field}' should be object, got {type(value).__name__}")
        elif expected_type == "string" and not isinstance(value, str):
            errors.append(f"Field '{field}' should be string, got {type(value).__name__}")

    return len(errors) == 0, errors


def validate_batch_responses(responses: list, index_name: str) -> dict[str, Any]:
    """Validate all responses in a batch. Returns summary statistics."""
    valid_count = 0
    invalid_count = 0
    all_errors = []

    for resp in responses:
        if resp.status != "success" or not resp.output:
            invalid_count += 1
            continue
        is_valid, errors = validate_output(resp.output, index_name)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            all_errors.extend([(resp.custom_id, e) for e in errors])

    return {
        "total": len(responses),
        "valid": valid_count,
        "invalid": invalid_count,
        "errors": all_errors[:20],
    }

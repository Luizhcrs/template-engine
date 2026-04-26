"""Unit tests for engine.llm._utils + engine.llm._schema."""

from types import SimpleNamespace

from engine.llm._schema import normalize_for_strict
from engine.llm._utils import retry_after_from_error


def _err_with_headers(headers: dict) -> Exception:
    e = Exception("rate limited")
    e.response = SimpleNamespace(headers=headers)  # type: ignore[attr-defined]
    return e


def _err_with_attr(retry_after: object) -> Exception:
    e = Exception("rate limited")
    e.retry_after = retry_after  # type: ignore[attr-defined]
    return e


def test_retry_after_from_header_lowercase():
    assert retry_after_from_error(_err_with_headers({"retry-after": "30"})) == 30


def test_retry_after_from_header_titlecase():
    assert retry_after_from_error(_err_with_headers({"Retry-After": "45"})) == 45


def test_retry_after_from_x_ratelimit_reset():
    assert retry_after_from_error(_err_with_headers({"x-ratelimit-reset": "120"})) == 120


def test_retry_after_from_attr():
    assert retry_after_from_error(_err_with_attr(15)) == 15


def test_retry_after_falls_back_to_default():
    assert retry_after_from_error(Exception("no headers"), default=99) == 99


def test_retry_after_invalid_value_falls_back():
    assert retry_after_from_error(_err_with_headers({"retry-after": "garbage"}), default=42) == 42


def test_retry_after_float_string_truncated():
    assert retry_after_from_error(_err_with_headers({"retry-after": "12.7"})) == 12


# ===== _schema.normalize_for_strict =====


def test_normalize_adds_additional_properties_false():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    out = normalize_for_strict(schema)
    assert out["additionalProperties"] is False


def test_normalize_populates_required_with_all_properties():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
    }
    out = normalize_for_strict(schema)
    assert set(out["required"]) == {"a", "b"}


def test_normalize_overwrites_partial_required():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
        "required": ["a"],
    }
    out = normalize_for_strict(schema)
    assert set(out["required"]) == {"a", "b"}


def test_normalize_recurses_into_nested_objects():
    schema = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {"inner": {"type": "string"}},
            }
        },
    }
    out = normalize_for_strict(schema)
    assert out["additionalProperties"] is False
    assert out["properties"]["outer"]["additionalProperties"] is False
    assert out["properties"]["outer"]["required"] == ["inner"]


def test_normalize_recurses_into_array_items():
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"k": {"type": "string"}},
                },
            }
        },
    }
    out = normalize_for_strict(schema)
    item_schema = out["properties"]["items"]["items"]
    assert item_schema["additionalProperties"] is False
    assert item_schema["required"] == ["k"]


def test_normalize_does_not_mutate_input():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    normalize_for_strict(schema)
    assert "additionalProperties" not in schema
    assert "required" not in schema

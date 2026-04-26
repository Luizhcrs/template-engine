"""JSON Schema utilities — normalize for OpenAI strict mode."""

from __future__ import annotations

from typing import Any


def normalize_for_strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively normalize a JSON Schema for OpenAI strict mode compatibility.

    Strict mode requires:
    - Every ``object`` has ``additionalProperties: false``
    - Every ``object`` lists ALL keys from ``properties`` in ``required``

    This walker mutates a deep copy of the input. Original schema unchanged.

    Limitations:
    - Doesn't follow ``$ref``
    - Doesn't recurse into ``oneOf`` / ``anyOf`` / ``allOf`` siblings
    - Best-effort: complex schemas may still need manual tuning
    """
    import copy

    normalized = copy.deepcopy(schema)
    _walk(normalized)
    return normalized


def _walk(node: Any) -> None:
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "object":
            node.setdefault("additionalProperties", False)
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties.keys())
                for value in properties.values():
                    _walk(value)
        elif node_type == "array":
            items = node.get("items")
            if isinstance(items, dict):
                _walk(items)
        # nested object/array under any key
        for key, value in node.items():
            if key in ("properties", "items", "required", "type", "additionalProperties"):
                continue
            _walk(value)
    elif isinstance(node, list):
        for item in node:
            _walk(item)

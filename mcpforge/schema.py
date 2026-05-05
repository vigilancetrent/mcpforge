"""Convert Python type hints into JSON Schema fragments."""
from __future__ import annotations

import dataclasses
import enum
import inspect
import types
import typing
from typing import Any, get_args, get_origin

try:
    from pydantic import BaseModel
    _HAS_PYDANTIC = True
except ImportError:
    BaseModel = None  # type: ignore[assignment, misc]
    _HAS_PYDANTIC = False


_PRIMITIVE_MAP: dict[Any, dict[str, Any]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    bytes: {"type": "string", "contentEncoding": "base64"},
    type(None): {"type": "null"},
}


def python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python type annotation to a JSON Schema fragment."""
    if annotation is Any or annotation is inspect.Parameter.empty:
        return {}

    if _HAS_PYDANTIC and isinstance(annotation, type) and issubclass(annotation, BaseModel):
        schema = annotation.model_json_schema()
        schema.pop("title", None)
        return schema

    if dataclasses.is_dataclass(annotation) and isinstance(annotation, type):
        return _dataclass_to_schema(annotation)

    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        values = [m.value for m in annotation]
        base = _PRIMITIVE_MAP.get(type(values[0]), {"type": "string"}) if values else {"type": "string"}
        return {**base, "enum": values}

    if annotation in _PRIMITIVE_MAP:
        return dict(_PRIMITIVE_MAP[annotation])

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is typing.Union or origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        has_none = len(non_none) != len(args)
        if len(non_none) == 1:
            inner = python_type_to_json_schema(non_none[0])
            if has_none:
                if "type" in inner and isinstance(inner["type"], str):
                    return {**inner, "type": [inner["type"], "null"]}
                return {"anyOf": [inner, {"type": "null"}]}
            return inner
        members = [python_type_to_json_schema(a) for a in non_none]
        if has_none:
            members.append({"type": "null"})
        return {"anyOf": members}

    if origin is typing.Literal:
        values = list(args)
        types_seen = {type(v) for v in values}
        if len(types_seen) == 1 and next(iter(types_seen)) in _PRIMITIVE_MAP:
            base = _PRIMITIVE_MAP[next(iter(types_seen))]
            return {**base, "enum": values}
        return {"enum": values}

    if origin in (list, typing.List):
        item_schema = python_type_to_json_schema(args[0]) if args else {}
        return {"type": "array", "items": item_schema}

    if origin in (set, frozenset, typing.Set, typing.FrozenSet):
        item_schema = python_type_to_json_schema(args[0]) if args else {}
        return {"type": "array", "items": item_schema, "uniqueItems": True}

    if origin in (tuple, typing.Tuple):
        if len(args) == 2 and args[1] is Ellipsis:
            return {"type": "array", "items": python_type_to_json_schema(args[0])}
        return {
            "type": "array",
            "prefixItems": [python_type_to_json_schema(a) for a in args],
            "minItems": len(args),
            "maxItems": len(args),
        }

    if origin in (dict, typing.Dict):
        if len(args) == 2:
            return {"type": "object", "additionalProperties": python_type_to_json_schema(args[1])}
        return {"type": "object"}

    if annotation is list:
        return {"type": "array"}
    if annotation is dict:
        return {"type": "object"}
    if annotation is tuple:
        return {"type": "array"}
    if annotation is set or annotation is frozenset:
        return {"type": "array", "uniqueItems": True}

    return {}


def _dataclass_to_schema(cls: type) -> dict[str, Any]:
    """Recursively build an object schema for a dataclass."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for f in dataclasses.fields(cls):
        properties[f.name] = python_type_to_json_schema(f.type if not isinstance(f.type, str) else _resolve_str_annotation(f.type, cls))
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            required.append(f.name)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def _resolve_str_annotation(ann: str, cls: type) -> Any:
    """Resolve a stringified annotation against a class's module globals."""
    try:
        hints = typing.get_type_hints(cls)
        if ann in hints:
            return hints[ann]
    except Exception:
        pass
    return Any


def function_to_input_schema(func: typing.Callable[..., Any]) -> dict[str, Any]:
    """Build a JSON Schema "object" describing a function's parameters."""
    sig = inspect.signature(func)
    try:
        hints = typing.get_type_hints(func)
    except Exception:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        annotation = hints.get(name, param.annotation)
        prop_schema = python_type_to_json_schema(annotation)
        if param.default is not inspect.Parameter.empty:
            try:
                import json as _json
                _json.dumps(param.default)
                prop_schema = {**prop_schema, "default": param.default}
            except (TypeError, ValueError):
                pass
        else:
            required.append(name)
        properties[name] = prop_schema

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema

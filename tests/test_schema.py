"""Schema-conversion tests."""
from __future__ import annotations

import dataclasses
from typing import Literal, Optional

import pytest

from mcpforge.schema import function_to_input_schema, python_type_to_json_schema


def test_primitives() -> None:
    assert python_type_to_json_schema(str) == {"type": "string"}
    assert python_type_to_json_schema(int) == {"type": "integer"}
    assert python_type_to_json_schema(float) == {"type": "number"}
    assert python_type_to_json_schema(bool) == {"type": "boolean"}
    assert python_type_to_json_schema(type(None)) == {"type": "null"}


def test_list_and_dict() -> None:
    assert python_type_to_json_schema(list[str]) == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert python_type_to_json_schema(dict[str, int]) == {
        "type": "object",
        "additionalProperties": {"type": "integer"},
    }


def test_optional() -> None:
    schema = python_type_to_json_schema(Optional[int])
    assert schema == {"type": ["integer", "null"]}


def test_pep604_union_with_none() -> None:
    schema = python_type_to_json_schema(int | None)
    assert schema == {"type": ["integer", "null"]}


def test_literal() -> None:
    schema = python_type_to_json_schema(Literal["a", "b", "c"])
    assert schema["enum"] == ["a", "b", "c"]
    assert schema["type"] == "string"


def test_dataclass() -> None:
    @dataclasses.dataclass
    class Point:
        x: int
        y: int
        label: str = "p"

    schema = python_type_to_json_schema(Point)
    assert schema["type"] == "object"
    assert schema["properties"]["x"] == {"type": "integer"}
    assert schema["properties"]["y"] == {"type": "integer"}
    assert schema["properties"]["label"] == {"type": "string"}
    assert set(schema["required"]) == {"x", "y"}


def test_pydantic_model() -> None:
    pydantic = pytest.importorskip("pydantic")

    class User(pydantic.BaseModel):
        name: str
        age: int = 0

    schema = python_type_to_json_schema(User)
    assert schema["type"] == "object"
    assert "name" in schema["properties"]
    assert "age" in schema["properties"]


def test_function_to_input_schema_basic() -> None:
    def f(self, symbol: str, limit: int = 10) -> list[dict]: ...

    schema = function_to_input_schema(f)
    assert schema["type"] == "object"
    assert schema["properties"]["symbol"] == {"type": "string"}
    assert schema["properties"]["limit"] == {"type": "integer", "default": 10}
    assert schema["required"] == ["symbol"]
    assert schema["additionalProperties"] is False


def test_function_to_input_schema_skips_self() -> None:
    def f(self) -> int: ...
    schema = function_to_input_schema(f)
    assert schema["properties"] == {}
    assert "required" not in schema


def test_function_to_input_schema_optional_param() -> None:
    def f(self, name: Optional[str] = None) -> str: ...
    schema = function_to_input_schema(f)
    assert schema["properties"]["name"]["type"] == ["string", "null"]
    assert "required" not in schema or "name" not in schema["required"]

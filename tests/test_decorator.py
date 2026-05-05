"""Tests for @serve / @tool / @resource decorators."""
from __future__ import annotations

from mcpforge import resource, serve, tool
from mcpforge.types import META_ATTR


def test_serve_attaches_meta() -> None:
    @serve(name="t", version="9.9.9", description="testy")
    class T:
        @tool
        def ping(self) -> str:
            return "pong"

    info = getattr(T, META_ATTR)
    assert info.name == "t"
    assert info.version == "9.9.9"
    assert "ping" in info.tools


def test_tool_bare_and_with_kwargs() -> None:
    @serve(name="t", version="1")
    class T:
        @tool
        def a(self, x: int) -> int:
            """First line of a's doc."""
            return x

        @tool(description="custom desc")
        def b(self, y: int) -> int:
            return y

    info = getattr(T, META_ATTR)
    assert info.tools["a"].description == "First line of a's doc."
    assert info.tools["b"].description == "custom desc"


def test_tool_preserves_callable() -> None:
    @serve(name="t", version="1")
    class T:
        @tool
        def double(self, x: int) -> int:
            return x * 2

    inst = T()
    assert inst.double(21) == 42


def test_input_schema_generated_from_signature() -> None:
    @serve(name="t", version="1")
    class T:
        @tool
        def search(self, query: str, limit: int = 10) -> list[dict]:
            return []

    info = getattr(T, META_ATTR)
    schema = info.tools["search"].input_schema
    assert schema["properties"]["query"] == {"type": "string"}
    assert schema["properties"]["limit"]["default"] == 10
    assert schema["required"] == ["query"]


def test_resource_registration() -> None:
    @serve(name="t", version="1")
    class T:
        @resource(uri="x://snapshot", description="A snapshot")
        def snap(self) -> dict:
            return {"ok": True}

    info = getattr(T, META_ATTR)
    assert "x://snapshot" in info.resources
    assert info.resources["x://snapshot"].description == "A snapshot"


def test_duplicate_tool_names_raise() -> None:
    import pytest

    with pytest.raises(ValueError, match="duplicate tool"):
        @serve(name="t", version="1")
        class _T:
            @tool(name="dup")
            def a(self) -> int: return 1
            @tool(name="dup")
            def b(self) -> int: return 2

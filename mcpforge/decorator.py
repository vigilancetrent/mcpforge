"""The three public decorators: @serve, @tool, @resource."""
from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar, overload

from .schema import function_to_input_schema
from .types import (
    META_ATTR,
    RESOURCE_ATTR,
    TOOL_ATTR,
    Capability,
    Resource,
    ServerInfo,
    Tool,
)

F = TypeVar("F", bound=Callable[..., Any])
C = TypeVar("C", bound=type)


def _first_doc_line(func: Callable[..., Any]) -> str:
    """Return the first non-empty line of a function's docstring, or ''."""
    doc = inspect.getdoc(func) or ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


@overload
def tool(func: F) -> F: ...
@overload
def tool(*, name: str | None = ..., description: str | None = ...) -> Callable[[F], F]: ...


def tool(func: Any = None, *, name: str | None = None, description: str | None = None) -> Any:
    """Mark a method as an MCP tool."""
    def _wrap(f: F) -> F:
        meta = {
            "name": name or f.__name__,
            "description": description or _first_doc_line(f) or f.__name__,
        }
        setattr(f, TOOL_ATTR, meta)
        return f

    if callable(func) and name is None and description is None:
        return _wrap(func)
    return _wrap


def resource(
    *,
    uri: str,
    name: str | None = None,
    description: str | None = None,
    mime_type: str = "application/json",
) -> Callable[[F], F]:
    """Mark a method as an MCP resource."""
    def _wrap(f: F) -> F:
        meta = {
            "uri": uri,
            "name": name or f.__name__,
            "description": description or _first_doc_line(f) or f.__name__,
            "mime_type": mime_type,
        }
        setattr(f, RESOURCE_ATTR, meta)
        return f

    return _wrap


def serve(
    *,
    name: str,
    version: str = "0.1.0",
    description: str = "",
    capabilities: Capability | None = None,
) -> Callable[[C], C]:
    """Decorate a class to declare it as an MCP server."""
    def _wrap(cls: C) -> C:
        info = ServerInfo(
            name=name,
            version=version,
            description=description or (inspect.getdoc(cls) or "").strip().split("\n")[0],
            capabilities=capabilities or Capability(),
        )

        for attr_name, member in inspect.getmembers(cls):
            if not callable(member):
                continue
            if hasattr(member, TOOL_ATTR):
                meta = getattr(member, TOOL_ATTR)
                input_schema = function_to_input_schema(member)
                info.add_tool(
                    Tool(
                        name=meta["name"],
                        description=meta["description"],
                        input_schema=input_schema,
                        func=member,
                        method_name=attr_name,
                    )
                )
            if hasattr(member, RESOURCE_ATTR):
                meta = getattr(member, RESOURCE_ATTR)
                info.add_resource(
                    Resource(
                        uri=meta["uri"],
                        name=meta["name"],
                        description=meta["description"],
                        mime_type=meta["mime_type"],
                        func=member,
                    )
                )

        setattr(cls, META_ATTR, info)
        return cls

    return _wrap

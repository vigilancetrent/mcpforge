"""mcpforge — ship an MCP server in 5 lines of Python.

Public surface:
    serve         — class decorator that marks a class as an MCP server
    tool          — method decorator registering a tool
    resource      — method decorator registering a resource
    serve_stdio   — run the stdio JSON-RPC loop for an instance
    run           — convenience: instantiate then serve_stdio
"""
from __future__ import annotations

from .decorator import resource, serve, tool
from .server import serve_stdio
from .types import (
    Capability,
    Resource,
    ServerInfo,
    Tool,
)

__version__ = "0.1.0"

__all__ = [
    "serve",
    "tool",
    "resource",
    "serve_stdio",
    "run",
    "Tool",
    "Resource",
    "Capability",
    "ServerInfo",
    "__version__",
]


def run(cls_or_instance, *args, **kwargs) -> None:
    """Instantiate `cls_or_instance` (if a class) and run the stdio MCP server."""
    import inspect as _inspect

    if _inspect.isclass(cls_or_instance):
        instance = cls_or_instance(*args, **kwargs)
    else:
        instance = cls_or_instance
    serve_stdio(instance)

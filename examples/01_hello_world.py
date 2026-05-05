"""Minimal mcpforge example: a single tool.

Run:
    python -m mcpforge run examples.01_hello_world:Hello
"""
from __future__ import annotations

from mcpforge import serve, tool


@serve(name="hello", version="0.1.0")
class Hello:
    """Friendly greetings."""

    @tool
    def greet(self, name: str = "world") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"


if __name__ == "__main__":
    from mcpforge import run
    run(Hello)

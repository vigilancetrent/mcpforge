# mcpforge

> Ship an MCP server in 5 lines of Python.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io)

```
Before                              After
──────                              ─────
~200 lines of                       @serve
JSON-RPC stdio                      class MarketTools:
boilerplate, schema                     @tool
generation, error                       def latest_price(self, symbol: str) -> float: ...
handling, lifecycle                     @tool
management.                             def search(self, query: str) -> list[dict]: ...

                                    $ python -m mcpforge run market:MarketTools
                                    ✓ MCP server running on stdio
```

---

## Why mcpforge

The Model Context Protocol (MCP) is the open standard Claude, Cursor, and an
exploding ecosystem of AI tools use to call external functions. It's powerful —
and writing a server is currently miserable.

You write the same JSON-RPC framing, schema generation, dispatch loop, and
error handling on every project. **mcpforge erases all of it.** Annotate your
class. Type-hint your methods. You're done.

```python
from mcpforge import serve, tool

@serve(name="market_tools", version="0.1.0")
class MarketTools:
    """Market data tools for AI agents."""

    @tool(description="Get the latest price for a symbol")
    def latest_price(self, symbol: str) -> float:
        return fetch_price(symbol)

    @tool
    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search ticker symbols matching `query`."""
        return run_search(query, limit)
```

That's a complete, spec-compliant MCP server. Type hints become JSON Schema.
Docstrings become tool descriptions. Returns are auto-serialized.

## 60-second quickstart

```bash
pip install mcpforge
```

```python
# hello.py
from mcpforge import serve, tool

@serve(name="hello", version="0.1.0")
class HelloTools:
    @tool
    def greet(self, name: str = "world") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"
```

```bash
python -m mcpforge run hello:HelloTools
```

You now have a working MCP server speaking JSON-RPC 2.0 over stdio.

## How it works

1. `@serve` tags a class as an MCP server (name, version, capabilities).
2. `@tool` registers methods as MCP tools.
3. `@resource(uri=...)` registers methods as MCP resources.
4. mcpforge introspects each method's signature and produces a JSON Schema —
   primitives, `list[T]`, `dict[str, T]`, `Literal[...]`, `Optional[T]`,
   dataclasses, and Pydantic models all just work.
5. `python -m mcpforge run mod:Class` boots the stdio loop, handles
   `initialize` / `tools/list` / `tools/call` / `resources/list` / `resources/read`,
   and reports JSON-RPC errors with proper codes.

No external MCP SDK. Just stdlib `json` + `pydantic` for schema niceties.

## Built-in servers

Two batteries-included servers you can drop in today:

```bash
# Filesystem tools (sandboxed to a root directory)
python -m mcpforge run mcpforge.builtin.filesystem:FilesystemTools

# HTTP fetch tools
python -m mcpforge run mcpforge.builtin.http:HttpTools
```

`FilesystemTools` exposes `list_dir`, `read_file`, `search` — sandboxed with
path traversal checks. `HttpTools` exposes `fetch_url` with size limits.

## Plug into Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "market": {
      "command": "python",
      "args": ["-m", "mcpforge", "run", "market:MarketTools"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

Restart Claude Desktop. Your tools appear in the conversation.

## Plug into Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "market": {
      "command": "python",
      "args": ["-m", "mcpforge", "run", "market:MarketTools"]
    }
  }
}
```

## Comparison

| Feature                       | mcpforge | `mcp` SDK | FastMCP | Hand-rolled |
| ----------------------------- | :------: | :-------: | :-----: | :---------: |
| Single decorator              |    Yes   |     No    |   Yes   |      No     |
| Auto JSON Schema from types   |    Yes   |     No    |   Yes   |      No     |
| Pydantic v2 support           |    Yes   |     Yes   |   Yes   |      No     |
| Zero required deps beyond pyd |    Yes   |     No    |    No   |     N/A     |
| Built-in fs / http servers    |    Yes   |     No    |    No   |      No     |
| Lines for hello world         |    ~5    |    ~40    |   ~10   |    ~200     |

## Inspect the wire format

```bash
python -m mcpforge inspect market:MarketTools
```

Prints the exact `tools/list` payload your clients will see.

## Roadmap

- [x] Tools (call, list)
- [x] Resources (read, list)
- [x] Type-hint -> JSON Schema (Pydantic v2, dataclasses, Literal, Optional)
- [x] Built-in filesystem and http servers
- [ ] Resource subscriptions
- [ ] Prompts capability
- [ ] Sampling capability
- [ ] WebSocket / HTTP-SSE transport (optional `[http]` extra)
- [ ] Async tools (`async def`)
- [ ] OTel tracing hooks

## License

MIT — see [LICENSE](LICENSE).

Author: [thechifura](https://github.com/vigilancetrent). Sibling to
[quantflow](https://github.com/vigilancetrent/quantflow) and
[strategos](https://github.com/vigilancetrent/strategos).

"""End-to-end tests for the stdio JSON-RPC server."""
from __future__ import annotations

import io
import json

import pytest

from mcpforge import resource, serve, tool
from mcpforge.server import _Server, handle_message, serve_stdio


@serve(name="demo", version="1.2.3", description="demo server")
class Demo:
    """A demo server."""

    @tool
    def add(self, a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    @tool
    def echo(self, msg: str = "hi") -> str:
        return msg

    @tool
    def boom(self) -> int:
        raise RuntimeError("kaboom")

    @resource(uri="demo://snapshot", description="demo state")
    def snap(self) -> dict:
        return {"ok": True}


def _server() -> _Server:
    return _Server(Demo())


def _send(server: _Server, payload: dict) -> dict | None:
    raw = json.dumps(payload)
    out = handle_message(server, raw)
    return json.loads(out) if out is not None else None


def test_initialize() -> None:
    s = _server()
    resp = _send(s, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "demo"
    assert resp["result"]["serverInfo"]["version"] == "1.2.3"
    assert "tools" in resp["result"]["capabilities"]


def test_tools_list() -> None:
    s = _server()
    resp = _send(s, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {"add", "echo", "boom"}
    add_tool = next(t for t in resp["result"]["tools"] if t["name"] == "add")
    assert add_tool["description"] == "Add two integers."
    assert add_tool["inputSchema"]["properties"]["a"] == {"type": "integer"}


def test_tools_call_success() -> None:
    s = _server()
    resp = _send(s, {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "add", "arguments": {"a": 2, "b": 3}},
    })
    assert resp["result"]["isError"] is False
    text = resp["result"]["content"][0]["text"]
    assert json.loads(text) == 5


def test_tools_call_default_argument() -> None:
    s = _server()
    resp = _send(s, {
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "echo", "arguments": {}},
    })
    assert resp["result"]["isError"] is False
    assert json.loads(resp["result"]["content"][0]["text"]) == "hi"


def test_tools_call_unknown_tool() -> None:
    s = _server()
    resp = _send(s, {
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "no_such", "arguments": {}},
    })
    assert resp["error"]["code"] == -32602


def test_tools_call_bad_arguments() -> None:
    s = _server()
    resp = _send(s, {
        "jsonrpc": "2.0", "id": 6, "method": "tools/call",
        "params": {"name": "add", "arguments": {"a": 1}},
    })
    assert resp["error"]["code"] == -32602


def test_tools_call_runtime_error_returns_iserror() -> None:
    s = _server()
    resp = _send(s, {
        "jsonrpc": "2.0", "id": 7, "method": "tools/call",
        "params": {"name": "boom", "arguments": {}},
    })
    assert resp["result"]["isError"] is True
    assert "kaboom" in resp["result"]["content"][0]["text"]


def test_unknown_method() -> None:
    s = _server()
    resp = _send(s, {"jsonrpc": "2.0", "id": 8, "method": "no/such/method"})
    assert resp["error"]["code"] == -32601


def test_resources_list_and_read() -> None:
    s = _server()
    list_resp = _send(s, {"jsonrpc": "2.0", "id": 9, "method": "resources/list"})
    uris = [r["uri"] for r in list_resp["result"]["resources"]]
    assert "demo://snapshot" in uris

    read_resp = _send(s, {
        "jsonrpc": "2.0", "id": 10, "method": "resources/read",
        "params": {"uri": "demo://snapshot"},
    })
    assert read_resp["result"]["contents"][0]["uri"] == "demo://snapshot"
    assert json.loads(read_resp["result"]["contents"][0]["text"]) == {"ok": True}


def test_parse_error() -> None:
    s = _server()
    out = handle_message(s, "{not valid json")
    assert out is not None
    resp = json.loads(out)
    assert resp["error"]["code"] == -32700


def test_notification_returns_none() -> None:
    s = _server()
    out = handle_message(s, json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
    assert out is None


def test_serve_stdio_loop() -> None:
    """Pipe a couple of requests through serve_stdio and check stdout."""
    requests = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n"
    )
    stdin = io.StringIO(requests)
    stdout = io.StringIO()
    serve_stdio(Demo(), stdin=stdin, stdout=stdout)
    lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["id"] == 1
    assert "tools" in lines[0]["result"]
    assert lines[1]["id"] == 2
    assert lines[1]["result"] == {}


def test_filesystem_path_traversal_rejected(tmp_path) -> None:
    from mcpforge.builtin.filesystem import FilesystemTools

    fs = FilesystemTools(root=str(tmp_path))
    (tmp_path / "ok.txt").write_text("hello")
    assert "ok.txt" in fs.list_dir(".")
    with pytest.raises(ValueError, match="escapes sandbox"):
        fs.read_file("../../../../etc/passwd")


def test_cli_inspect_outputs_valid_json(capsys) -> None:
    from mcpforge.cli import main

    rc = main(["inspect", "mcpforge.builtin.filesystem:FilesystemTools"])
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["serverInfo"]["name"] == "filesystem"
    assert isinstance(payload["tools"], list)
    tool_names = {t["name"] for t in payload["tools"]}
    assert {"list_dir", "read_file", "search"}.issubset(tool_names)

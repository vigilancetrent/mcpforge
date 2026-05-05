"""Stdio JSON-RPC 2.0 MCP server — no external SDK."""
from __future__ import annotations

import dataclasses
import inspect
import json
import sys
import traceback
from typing import Any, TextIO

from .types import META_ATTR, Resource, ServerInfo, Tool

ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603


def _log(msg: str, stream: TextIO | None = None) -> None:
    """Log to stderr (stdout is reserved for JSON-RPC framing)."""
    out = stream if stream is not None else sys.stderr
    try:
        out.write(f"[mcpforge] {msg}\n")
        out.flush()
    except Exception:
        pass


def _json_default(o: Any) -> Any:
    """Best-effort JSON encoder for return values."""
    if hasattr(o, "model_dump"):
        try:
            return o.model_dump()
        except Exception:
            pass
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return dataclasses.asdict(o)
    if hasattr(o, "__fspath__"):
        return str(o)
    if isinstance(o, (bytes, bytearray)):
        try:
            return o.decode("utf-8")
        except UnicodeDecodeError:
            import base64
            return base64.b64encode(bytes(o)).decode("ascii")
    if isinstance(o, (set, frozenset)):
        return list(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _serialize_result(value: Any) -> str:
    """Serialise a tool/resource return value to a JSON string."""
    return json.dumps(value, default=_json_default, ensure_ascii=False)


class _Server:
    """Internal server holding an instance and its ServerInfo."""

    def __init__(self, instance: Any) -> None:
        info = getattr(type(instance), META_ATTR, None)
        if info is None:
            raise TypeError(
                f"{type(instance).__name__} is not decorated with @serve. "
                "Did you forget the decorator?"
            )
        self.instance: Any = instance
        self.info: ServerInfo = info
        self.initialized: bool = False

    def _tool_descriptor(self, t: Tool) -> dict[str, Any]:
        return {
            "name": t.name,
            "description": t.description,
            "inputSchema": t.input_schema,
        }

    def _resource_descriptor(self, r: Resource) -> dict[str, Any]:
        return {
            "uri": r.uri,
            "name": r.name,
            "description": r.description,
            "mimeType": r.mime_type,
        }

    def handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        self.initialized = True
        return {
            "protocolVersion": self.info.protocol_version,
            "capabilities": self.info.capabilities.to_dict(),
            "serverInfo": {
                "name": self.info.name,
                "version": self.info.version,
            },
        }

    def handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": [self._tool_descriptor(t) for t in self.info.tools.values()]}

    def handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(params, dict):
            raise _RpcError(ERR_INVALID_PARAMS, "params must be an object")
        name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        if not isinstance(name, str):
            raise _RpcError(ERR_INVALID_PARAMS, "missing or invalid 'name'")
        if not isinstance(arguments, dict):
            raise _RpcError(ERR_INVALID_PARAMS, "'arguments' must be an object")
        tool = self.info.tools.get(name)
        if tool is None:
            raise _RpcError(ERR_INVALID_PARAMS, f"unknown tool: {name}")

        bound = tool.func.__get__(self.instance, type(self.instance))
        try:
            sig = inspect.signature(bound)
            sig.bind(**arguments)
        except TypeError as e:
            raise _RpcError(ERR_INVALID_PARAMS, f"invalid arguments for {name}: {e}")

        try:
            result = bound(**arguments)
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}],
                "isError": True,
            }

        text = _serialize_result(result)
        return {
            "content": [{"type": "text", "text": text}],
            "isError": False,
        }

    def handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "resources": [self._resource_descriptor(r) for r in self.info.resources.values()]
        }

    def handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(params, dict):
            raise _RpcError(ERR_INVALID_PARAMS, "params must be an object")
        uri = params.get("uri")
        if not isinstance(uri, str):
            raise _RpcError(ERR_INVALID_PARAMS, "missing or invalid 'uri'")
        res = self.info.resources.get(uri)
        if res is None:
            raise _RpcError(ERR_INVALID_PARAMS, f"unknown resource: {uri}")
        bound = res.func.__get__(self.instance, type(self.instance))
        try:
            value = bound()
        except Exception as e:
            raise _RpcError(ERR_INTERNAL, f"resource read failed: {e}")
        text = _serialize_result(value)
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": res.mime_type,
                    "text": text,
                }
            ]
        }

    def handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    def handle_shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    def dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Any] = {
            "initialize": self.handle_initialize,
            "ping": self.handle_ping,
            "tools/list": self.handle_tools_list,
            "tools/call": self.handle_tools_call,
            "resources/list": self.handle_resources_list,
            "resources/read": self.handle_resources_read,
            "shutdown": self.handle_shutdown,
        }
        if method not in handlers:
            raise _RpcError(ERR_METHOD_NOT_FOUND, f"method not found: {method}")
        return handlers[method](params or {})


class _RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _build_response(req_id: Any, result: dict[str, Any] | None = None,
                    error: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result if result is not None else {}
    return out


def _is_notification(msg: dict[str, Any]) -> bool:
    return "id" not in msg or msg.get("id") is None


def handle_message(server: _Server, raw: str) -> str | None:
    """Process one JSON-RPC message string. Returns the response string,
    or None if the message was a notification (no response required)."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        resp = _build_response(None, error={"code": ERR_PARSE, "message": f"parse error: {e}"})
        return json.dumps(resp)

    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        resp = _build_response(msg.get("id") if isinstance(msg, dict) else None,
                               error={"code": ERR_INVALID_REQUEST, "message": "invalid request"})
        return json.dumps(resp)

    method = msg.get("method")
    params = msg.get("params") or {}
    req_id = msg.get("id")
    is_notification = _is_notification(msg)

    if not isinstance(method, str):
        if is_notification:
            return None
        resp = _build_response(req_id, error={"code": ERR_INVALID_REQUEST, "message": "missing method"})
        return json.dumps(resp)

    if method in ("initialized", "notifications/initialized", "notifications/cancelled"):
        return None

    try:
        result = server.dispatch(method, params)
    except _RpcError as e:
        if is_notification:
            return None
        resp = _build_response(req_id, error={"code": e.code, "message": e.message, "data": e.data})
        return json.dumps(resp)
    except Exception as e:
        _log(f"internal error in {method}: {e}\n{traceback.format_exc()}")
        if is_notification:
            return None
        resp = _build_response(req_id, error={"code": ERR_INTERNAL, "message": f"internal error: {e}"})
        return json.dumps(resp)

    if is_notification:
        return None
    return json.dumps(_build_response(req_id, result=result))


def serve_stdio(instance: Any, stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
    """Run the MCP stdio server loop until EOF."""
    server = _Server(instance)
    rin = stdin if stdin is not None else sys.stdin
    rout = stdout if stdout is not None else sys.stdout

    _log(f"serving '{server.info.name}' v{server.info.version} "
         f"({len(server.info.tools)} tools, {len(server.info.resources)} resources) on stdio")

    try:
        for raw_line in rin:
            line = raw_line.strip()
            if not line:
                continue
            response = handle_message(server, line)
            if response is not None:
                rout.write(response + "\n")
                rout.flush()
    except KeyboardInterrupt:
        _log("interrupted")
    except BrokenPipeError:
        _log("client disconnected")
    finally:
        _log("shutting down")

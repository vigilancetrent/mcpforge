"""Internal dataclasses representing the MCP server registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    """A registered MCP tool: a callable plus its advertised schema."""

    name: str
    description: str
    input_schema: dict[str, Any]
    func: Callable[..., Any]
    method_name: str = ""


@dataclass
class Resource:
    """A registered MCP resource: a static URI plus a reader callable."""

    uri: str
    name: str
    description: str
    mime_type: str
    func: Callable[..., Any]


@dataclass
class Capability:
    """Set of capabilities the server advertises during initialize."""

    tools: bool = True
    resources: bool = True
    prompts: bool = False
    logging: bool = False

    def to_dict(self) -> dict[str, Any]:
        cap: dict[str, Any] = {}
        if self.tools:
            cap["tools"] = {"listChanged": False}
        if self.resources:
            cap["resources"] = {"subscribe": False, "listChanged": False}
        if self.prompts:
            cap["prompts"] = {"listChanged": False}
        if self.logging:
            cap["logging"] = {}
        return cap


@dataclass
class ServerInfo:
    """The full MCP server descriptor produced by `@serve`."""

    name: str
    version: str
    description: str = ""
    tools: dict[str, Tool] = field(default_factory=dict)
    resources: dict[str, Resource] = field(default_factory=dict)
    capabilities: Capability = field(default_factory=Capability)
    protocol_version: str = "2024-11-05"

    def add_tool(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self.tools[tool.name] = tool

    def add_resource(self, resource: Resource) -> None:
        if resource.uri in self.resources:
            raise ValueError(f"duplicate resource uri: {resource.uri}")
        self.resources[resource.uri] = resource


META_ATTR = "__mcp_meta__"
TOOL_ATTR = "__mcp_tool__"
RESOURCE_ATTR = "__mcp_resource__"

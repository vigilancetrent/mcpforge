"""Command-line entry point."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from typing import Any

from . import __version__
from .server import _Server, serve_stdio
from .types import META_ATTR


def _resolve_target(target: str) -> Any:
    """Resolve a 'pkg.module:Attr' string to the attribute."""
    if ":" not in target:
        raise SystemExit(
            f"target must be in the form 'module:ClassName', got: {target!r}"
        )
    module_path, attr = target.split(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise SystemExit(f"could not import {module_path!r}: {e}")
    try:
        obj = getattr(module, attr)
    except AttributeError:
        raise SystemExit(f"{attr!r} not found in {module_path!r}")
    return obj


def _instantiate(obj: Any) -> Any:
    """If obj is a class, call it with no args; otherwise return as-is."""
    import inspect as _inspect
    if _inspect.isclass(obj):
        try:
            return obj()
        except TypeError as e:
            raise SystemExit(
                f"could not instantiate {obj.__name__} with no arguments: {e}\n"
                f"Tip: provide a wrapper that constructs it for you."
            )
    return obj


def _cmd_run(args: argparse.Namespace) -> int:
    obj = _resolve_target(args.target)
    instance = _instantiate(obj)
    if not hasattr(type(instance), META_ATTR):
        raise SystemExit(
            f"{type(instance).__name__} is not decorated with @serve."
        )
    serve_stdio(instance)
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    obj = _resolve_target(args.target)
    instance = _instantiate(obj)
    server = _Server(instance)
    payload = {
        "serverInfo": {
            "name": server.info.name,
            "version": server.info.version,
        },
        "capabilities": server.info.capabilities.to_dict(),
        "tools": server.handle_tools_list({})["tools"],
        "resources": server.handle_resources_list({})["resources"],
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mcpforge",
        description="Ship an MCP server in 5 lines of Python.",
    )
    p.add_argument("--version", action="version", version=f"mcpforge {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run an MCP server over stdio")
    run.add_argument("target", help="module:ClassName to serve")
    run.set_defaults(func=_cmd_run)

    inspect_cmd = sub.add_parser(
        "inspect", help="Print the tools/list payload as JSON for debugging"
    )
    inspect_cmd.add_argument("target", help="module:ClassName to inspect")
    inspect_cmd.set_defaults(func=_cmd_inspect)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

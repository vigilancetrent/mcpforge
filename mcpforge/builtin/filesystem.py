"""Sandboxed filesystem tools."""
from __future__ import annotations

import os
from pathlib import Path

from ..decorator import serve, tool


@serve(
    name="filesystem",
    version="0.1.0",
    description="Sandboxed filesystem read/list/search tools",
)
class FilesystemTools:
    """Read-only filesystem tools, sandboxed to a single root directory."""

    def __init__(self, root: str = ".") -> None:
        self.root: Path = Path(root).expanduser().resolve()

    def _safe_join(self, path: str) -> Path:
        """Resolve `path` under self.root and verify it stays inside."""
        candidate = (self.root / path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise ValueError(
                f"path escapes sandbox root: {path!r} resolves outside {self.root}"
            )
        return candidate

    @tool
    def list_dir(self, path: str = ".") -> list[str]:
        """List entries in `path` (relative to the sandbox root)."""
        target = self._safe_join(path)
        if not target.exists():
            raise FileNotFoundError(f"no such path: {path}")
        if not target.is_dir():
            raise NotADirectoryError(f"not a directory: {path}")
        entries = []
        for entry in sorted(target.iterdir()):
            suffix = "/" if entry.is_dir() else ""
            entries.append(entry.name + suffix)
        return entries

    @tool
    def read_file(self, path: str, max_bytes: int = 100_000) -> str:
        """Read up to `max_bytes` bytes of the file at `path` as UTF-8 text."""
        target = self._safe_join(path)
        if not target.exists():
            raise FileNotFoundError(f"no such file: {path}")
        if not target.is_file():
            raise IsADirectoryError(f"not a file: {path}")
        with target.open("rb") as f:
            data = f.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        body = data[:max_bytes].decode("utf-8", errors="replace")
        if truncated:
            body += f"\n\n[truncated at {max_bytes} bytes]"
        return body

    @tool
    def search(self, pattern: str, path: str = ".", max_results: int = 100) -> list[dict]:
        """Recursively search for `pattern` in files under `path`."""
        if not pattern:
            raise ValueError("pattern must be non-empty")
        root = self._safe_join(path)
        if not root.exists():
            raise FileNotFoundError(f"no such path: {path}")
        if not root.is_dir():
            raise NotADirectoryError(f"not a directory: {path}")

        results: list[dict] = []
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                fpath = Path(dirpath) / fname
                try:
                    with fpath.open("r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, start=1):
                            if pattern in line:
                                results.append({
                                    "file": str(fpath.relative_to(self.root)),
                                    "line": lineno,
                                    "text": line.rstrip("\n"),
                                })
                                if len(results) >= max_results:
                                    return results
                except (OSError, UnicodeDecodeError):
                    continue
        return results

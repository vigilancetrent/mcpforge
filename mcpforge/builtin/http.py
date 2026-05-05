"""HTTP fetch tools using stdlib only — no `requests` dependency."""
from __future__ import annotations

import urllib.error
import urllib.request
from typing import Literal

from ..decorator import serve, tool


@serve(
    name="http_tools",
    version="0.1.0",
    description="Stdlib HTTP fetch tools",
)
class HttpTools:
    """Fetch URLs with size and method limits."""

    def __init__(self, user_agent: str = "mcpforge/0.1.0", timeout: float = 30.0) -> None:
        self.user_agent = user_agent
        self.timeout = timeout

    @tool
    def fetch_url(
        self,
        url: str,
        method: Literal["GET", "HEAD"] = "GET",
        max_bytes: int = 1_000_000,
    ) -> dict:
        """Fetch `url` via GET or HEAD. Returns status, headers, and body."""
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("only http(s) URLs are supported")
        req = urllib.request.Request(
            url,
            method=method,
            headers={"User-Agent": self.user_agent},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read(max_bytes + 1) if method != "HEAD" else b""
                truncated = len(raw) > max_bytes
                body = raw[:max_bytes].decode("utf-8", errors="replace")
                if truncated:
                    body += f"\n\n[truncated at {max_bytes} bytes]"
                return {
                    "status": resp.status,
                    "headers": dict(resp.headers.items()),
                    "body": body,
                    "truncated": truncated,
                }
        except urllib.error.HTTPError as e:
            return {
                "status": e.code,
                "headers": dict(e.headers.items()) if e.headers else {},
                "body": "",
                "error": str(e),
            }
        except urllib.error.URLError as e:
            raise ConnectionError(f"could not fetch {url}: {e.reason}")

    @tool
    def parse_html(self, html: str, max_len: int = 50_000) -> str:
        """Strip tags from `html` and return the visible text (best-effort)."""
        from html.parser import HTMLParser

        class _Stripper(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []
                self._skip_depth = 0

            def handle_starttag(self, tag: str, attrs: list) -> None:
                if tag in ("script", "style"):
                    self._skip_depth += 1

            def handle_endtag(self, tag: str) -> None:
                if tag in ("script", "style") and self._skip_depth:
                    self._skip_depth -= 1

            def handle_data(self, data: str) -> None:
                if self._skip_depth == 0:
                    self.parts.append(data)

        s = _Stripper()
        s.feed(html)
        text = " ".join(p.strip() for p in s.parts if p.strip())
        if len(text) > max_len:
            text = text[:max_len] + f"\n\n[truncated at {max_len} chars]"
        return text

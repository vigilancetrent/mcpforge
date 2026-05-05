"""Realistic example: market data tools with multiple types and a resource.

Run:
    python -m mcpforge run examples.02_market_tools:MarketTools
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from mcpforge import resource, serve, tool


class Quote(BaseModel):
    symbol: str = Field(..., description="Ticker symbol, e.g. AAPL")
    price: float
    currency: Literal["USD", "EUR", "GBP", "JPY"] = "USD"
    timestamp: int = Field(..., description="Unix epoch seconds")


@serve(
    name="market_tools",
    version="0.1.0",
    description="Demo market data tools backed by canned responses",
)
class MarketTools:
    """Provides market data tools to MCP clients."""

    def __init__(self) -> None:
        self._fake_prices: dict[str, float] = {
            "AAPL": 192.34,
            "MSFT": 412.55,
            "GOOG": 175.10,
            "NVDA": 1145.33,
        }

    @tool(description="Get the latest quote for a symbol")
    def latest_quote(self, symbol: str) -> Quote:
        """Return the most recent quote for `symbol`."""
        symbol = symbol.upper()
        price = self._fake_prices.get(symbol, 0.0)
        return Quote(symbol=symbol, price=price, currency="USD", timestamp=1717000000)

    @tool
    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search ticker symbols matching `query`."""
        q = query.upper()
        hits = [
            {"symbol": s, "price": p}
            for s, p in self._fake_prices.items()
            if q in s
        ]
        return hits[:limit]

    @tool
    def list_supported(self) -> list[str]:
        """Return the list of supported symbols."""
        return sorted(self._fake_prices.keys())

    @resource(uri="market://snapshot", description="Snapshot of all known prices")
    def snapshot(self) -> dict:
        """Read-only snapshot of current market state."""
        return {
            "timestamp": 1717000000,
            "prices": dict(self._fake_prices),
        }


if __name__ == "__main__":
    from mcpforge import run
    run(MarketTools)

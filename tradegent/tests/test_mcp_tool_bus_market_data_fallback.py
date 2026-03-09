"""Tests for MCPToolBus market-data fallback extraction."""

from __future__ import annotations

from adk_runtime.mcp_tool_bus import MCPToolBus


class _FakeQuote:
    def __init__(self, *, last=None, close=None) -> None:
        self.last = last
        self.close = close


class _FakeIBClient:
    def __init__(self, *, stock_price: dict | None, batch: dict | None, historical: dict | None) -> None:
        self._stock_price = stock_price
        self._batch = batch
        self._historical = historical

    def get_stock_price(self, _symbol: str):
        return self._stock_price

    def get_quotes_batch(self, _symbols: list[str]):
        return self._batch

    def get_historical_data(self, _symbol: str, duration: str = "2 D", bar_size: str = "1 day", what_to_show: str = "TRADES"):
        _ = (duration, bar_size, what_to_show)
        return self._historical


def test_market_data_fallback_uses_historical_close(monkeypatch) -> None:
    fake = _FakeIBClient(
        stock_price={"last": None, "close": None},
        batch={"MSFT": _FakeQuote(last=None, close=None)},
        historical={"bars": [{"close": 412.5}]},
    )

    monkeypatch.setattr("ib_client.get_ib_client", lambda: fake)

    bus = MCPToolBus()
    snapshot = bus._fetch_live_market_data("MSFT")

    assert isinstance(snapshot, dict)
    assert snapshot.get("price_data_source") == "ib_mcp"
    assert snapshot.get("prior_close") == 412.5
    assert snapshot.get("current_price") == 412.5
    assert snapshot.get("price_data_verified") is True


def test_market_data_snapshot_unverified_when_no_prices(monkeypatch) -> None:
    fake = _FakeIBClient(
        stock_price={"last": None, "close": None},
        batch={"MSFT": _FakeQuote(last=None, close=None)},
        historical={"bars": []},
    )

    monkeypatch.setattr("ib_client.get_ib_client", lambda: fake)

    bus = MCPToolBus()
    snapshot = bus._fetch_live_market_data("MSFT")

    assert isinstance(snapshot, dict)
    assert snapshot.get("price_data_source") == "ib_mcp"
    assert snapshot.get("price_data_verified") is False
    assert "quote_timestamp" in snapshot

"""Unit tests for trades service layer."""

from fastapi import HTTPException

from tradegent_ui.server.services import trades_service


def test_list_trades_maps_response(monkeypatch) -> None:
    class DummyDate:
        def __init__(self, value: str):
            self._value = value

        def isoformat(self) -> str:
            return self._value

    monkeypatch.setattr(
        trades_service.trades_repository,
        "list_trades",
        lambda status, ticker, limit, offset: (
            1,
            [
                {
                    "id": 1,
                    "ticker": "NVDA",
                    "direction": "long",
                    "entry_date": DummyDate("2026-03-11T10:00:00"),
                    "entry_price": 900.0,
                    "entry_size": 10.0,
                    "status": "open",
                    "exit_date": None,
                    "exit_price": None,
                    "pnl_dollars": None,
                    "pnl_pct": None,
                    "thesis": "test",
                    "source_type": "manual",
                }
            ],
        ),
    )
    monkeypatch.setattr(
        trades_service.trades_repository,
        "get_trade_stats",
        lambda: {
            "total_trades": 1,
            "open_trades": 1,
            "closed_trades": 0,
            "total_pnl": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "best_trade": 0,
            "worst_trade": 0,
        },
    )

    result = trades_service.list_trades(status=None, ticker=None, limit=10, offset=0)
    assert result["total"] == 1
    assert result["trades"][0]["ticker"] == "NVDA"
    assert result["stats"]["open_trades"] == 1


def test_get_trade_detail_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        trades_service.trades_repository,
        "get_trade_detail",
        lambda trade_id: None,
    )

    try:
        trades_service.get_trade_detail(42)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Trade not found"

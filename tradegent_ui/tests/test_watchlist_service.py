"""Unit tests for watchlist service layer."""

from fastapi import HTTPException

from tradegent_ui.server.services import watchlist_service


def test_delete_watchlist_blocks_default(monkeypatch) -> None:
    monkeypatch.setattr(
        watchlist_service.watchlist_repository,
        "get_watchlist_metadata",
        lambda watchlist_id: {"id": watchlist_id, "source_type": "manual", "is_default": True},
    )

    try:
        watchlist_service.delete_watchlist(1)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Default watchlist cannot be deleted"


def test_update_watchlist_conflict(monkeypatch) -> None:
    monkeypatch.setattr(
        watchlist_service.watchlist_repository,
        "watchlist_name_exists",
        lambda name, exclude_id=None: True,
    )

    try:
        watchlist_service.update_watchlist(3, {"name": "Growth"})
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail == "Watchlist name already exists"


def test_list_watchlist_entries_shapes_stats(monkeypatch) -> None:
    monkeypatch.setattr(
        watchlist_service.watchlist_repository,
        "list_watchlist_entries",
        lambda status, priority, watchlist_id, limit, offset: (
            2,
            [{"id": 1, "ticker": "NVDA"}, {"id": 2, "ticker": "AAPL"}],
            {"total": 2, "active": 1, "triggered": 1, "expired": 0, "invalidated": 0},
            {"high": 1},
        ),
    )

    result = watchlist_service.list_watchlist_entries(
        status=None,
        priority=None,
        watchlist_id=None,
        limit=50,
        offset=0,
    )

    assert result["total"] == 2
    assert result["stats"]["active"] == 1
    assert result["stats"]["by_priority"]["high"] == 1


def test_create_watchlist_entry_normalizes_ticker(monkeypatch) -> None:
    captured = {}

    def _create(payload):
        captured.update(payload)
        return {"id": 1, "ticker": payload["ticker"]}

    monkeypatch.setattr(
        watchlist_service.watchlist_repository,
        "create_watchlist_entry",
        _create,
    )

    result = watchlist_service.create_watchlist_entry(
        watchlist_id=1,
        ticker=" nvda ",
        entry_trigger="Breakout above 950",
        entry_price=950.0,
        invalidation=None,
        invalidation_price=None,
        expires_at=None,
        priority="medium",
        source="manual_form",
        source_analysis=None,
        notes=None,
    )

    assert captured["ticker"] == "NVDA"
    assert captured["entry_trigger"] == "Breakout above 950"
    assert result["id"] == 1

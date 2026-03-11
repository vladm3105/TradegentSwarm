"""Unit tests for alerts service layer."""

from fastapi import HTTPException

from tradegent_ui.server.services import alerts_service


def test_create_alert_requires_ticker_for_price() -> None:
    try:
        alerts_service.create_alert(
            user_id="u-1",
            alert_type="price",
            ticker=None,
            condition={"operator": "above", "value": 10.0, "value_type": "price"},
        )
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "requires a ticker" in str(exc.detail)


def test_delete_alert_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        alerts_service.alerts_repository,
        "delete_alert",
        lambda alert_id, user_id: False,
    )

    try:
        alerts_service.delete_alert(alert_id=9, user_id="u-1")
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Alert not found"


def test_toggle_alert_success(monkeypatch) -> None:
    monkeypatch.setattr(
        alerts_service.alerts_repository,
        "toggle_alert",
        lambda alert_id, user_id: True,
    )

    result = alerts_service.toggle_alert(alert_id=7, user_id="u-1")
    assert result == {"success": True, "is_active": True}

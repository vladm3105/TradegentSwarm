"""Unit tests for notifications service layer."""

from fastapi import HTTPException

from tradegent_ui.server.services import notifications_service


def test_get_notification_count_casts_to_int(monkeypatch) -> None:
    monkeypatch.setattr(
        notifications_service.notifications_repository,
        "get_notification_count",
        lambda user_id: {"total": 3, "unread": 2},
    )

    result = notifications_service.get_notification_count("u-1")
    assert result == {"total": 3, "unread": 2}


def test_mark_as_read_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        notifications_service.notifications_repository,
        "mark_as_read",
        lambda notification_id, user_id: False,
    )

    try:
        notifications_service.mark_as_read(notification_id=5, user_id="u-1")
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Notification not found"

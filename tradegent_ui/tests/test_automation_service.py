"""Unit tests for automation_service business logic."""
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch


def test_set_trading_mode_live_requires_confirm():
    """set_trading_mode raises 400 when mode=live without confirm."""
    with patch(
        "tradegent_ui.server.services.automation_service.automation_repository"
    ):
        from tradegent_ui.server.services.automation_service import set_trading_mode

        with pytest.raises(HTTPException) as exc_info:
            set_trading_mode("live", confirm=False)
        assert exc_info.value.status_code == 400
        assert "confirmation" in exc_info.value.detail.lower()


def test_set_trading_mode_dry_run_sets_flags():
    """set_trading_mode with dry_run passes auto_execute=false and dry_run=true."""
    with patch(
        "tradegent_ui.server.services.automation_service.automation_repository"
    ) as mock_repo:
        from tradegent_ui.server.services.automation_service import set_trading_mode

        result = set_trading_mode("dry_run", confirm=False)
        mock_repo.set_trading_mode.assert_called_once_with("dry_run", "false", "true")
        assert result["success"] is True
        assert result["mode"] == "dry_run"


def test_resume_trading_blocks_when_cb_triggered():
    """resume_trading raises 400 when circuit breaker is triggered."""
    with patch(
        "tradegent_ui.server.services.automation_service.automation_repository"
    ):
        from tradegent_ui.server.services.automation_service import resume_trading

        cb = MagicMock()
        cb.is_triggered = True

        with pytest.raises(HTTPException) as exc_info:
            resume_trading(cb)
        assert exc_info.value.status_code == 400


def test_get_circuit_breaker_settings_defaults():
    """get_circuit_breaker_settings returns correct defaults when settings missing."""
    with patch(
        "tradegent_ui.server.services.automation_service.automation_repository"
    ) as mock_repo:
        mock_repo.get_circuit_breaker_settings.return_value = {}
        from tradegent_ui.server.services.automation_service import (
            get_circuit_breaker_settings,
        )

        result = get_circuit_breaker_settings()
        assert result["enabled"] is True
        assert result["max_daily_loss"] == 1000.0
        assert result["max_daily_loss_pct"] == 5.0

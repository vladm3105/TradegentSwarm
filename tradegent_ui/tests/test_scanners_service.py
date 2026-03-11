"""Unit tests for scanners_service parsing logic."""

from tradegent_ui.server.services import scanners_service


def test_latest_candidates_deduplicates(monkeypatch):
    monkeypatch.setattr(
        scanners_service.scanners_repository,
        "list_latest_candidate_outputs",
        lambda: [
            {"candidates": [{"ticker": "NVDA", "score": 9.1}, {"ticker": "NVDA", "score": 8.9}]}
        ],
    )

    rows = scanners_service.latest_candidates(10)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "NVDA"

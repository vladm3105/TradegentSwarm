"""Tests for file-backed context retrieval in MCPToolBus."""

from __future__ import annotations

from pathlib import Path

from adk_runtime.mcp_tool_bus import MCPToolBus


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_context_retrieval_returns_latest_stock_document(tmp_path: Path) -> None:
    knowledge_root = tmp_path / "knowledge"
    stock_dir = knowledge_root / "analysis" / "stock"

    _write_yaml(
        stock_dir / "NVDA_20260305T1000.yaml",
        """
_meta:
  type: stock-analysis
  ticker: NVDA
summary:
  note: old
""".strip(),
    )
    _write_yaml(
        stock_dir / "NVDA_20260305T1100.yaml",
        """
_meta:
  type: stock-analysis
  ticker: NVDA
summary:
  note: latest
""".strip(),
    )

    bus = MCPToolBus(knowledge_root=knowledge_root)
    result = bus.call("context_retrieval", {"request": {"ticker": "NVDA", "analysis_type": "stock"}})

    assert result["status"] == "ok"
    payload = result["payload"]
    context = payload["context"]
    assert context["warnings"] == []
    assert context["latest_document"]["summary"]["note"] == "latest"
    assert context["source"].endswith("NVDA_20260305T1100.yaml")


def test_context_retrieval_handles_no_prior_document(tmp_path: Path) -> None:
    knowledge_root = tmp_path / "knowledge"
    bus = MCPToolBus(knowledge_root=knowledge_root)

    result = bus.call("context_retrieval", {"request": {"ticker": "MSFT", "analysis_type": "earnings"}})

    assert result["status"] == "ok"
    payload = result["payload"]
    context = payload["context"]
    assert context["latest_document"] is None
    assert "no_prior_document" in context["warnings"]


def test_context_retrieval_second_call_hits_cache(tmp_path: Path) -> None:
    knowledge_root = tmp_path / "knowledge"
    stock_dir = knowledge_root / "analysis" / "stock"

    _write_yaml(
        stock_dir / "NVDA_20260305T1200.yaml",
        """
_meta:
  type: stock-analysis
  ticker: NVDA
summary:
  note: latest
""".strip(),
    )

    bus = MCPToolBus(knowledge_root=knowledge_root)
    first = bus.call("context_retrieval", {"request": {"ticker": "NVDA", "analysis_type": "stock"}})
    second = bus.call("context_retrieval", {"request": {"ticker": "NVDA", "analysis_type": "stock"}})

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert first["payload"]["context"]["cache_hit"] is False
    assert second["payload"]["context"]["cache_hit"] is True


def test_context_retrieval_active_only_returns_active_doc_and_skips_non_active(
    tmp_path: Path, monkeypatch
) -> None:
    """ADK_CONTEXT_ACTIVE_ONLY=true: only status=active artifacts are retrieved."""
    monkeypatch.setenv("ADK_CONTEXT_ACTIVE_ONLY", "true")
    knowledge_root = tmp_path / "knowledge"
    stock_dir = knowledge_root / "analysis" / "stock"

    # Older active artifact — should be returned (it's the only active one).
    _write_yaml(
        stock_dir / "NVDA_20260305T0900.yaml",
        """
_meta:
  type: stock-analysis
  ticker: NVDA
  status: active
summary:
  note: active-doc
""".strip(),
    )
    # Newer non-active artifact — should be skipped.
    _write_yaml(
        stock_dir / "NVDA_20260305T1100.yaml",
        """
_meta:
  type: stock-analysis
  ticker: NVDA
  status: inactive_quality_failed
summary:
  note: non-active-doc
""".strip(),
    )

    bus = MCPToolBus(knowledge_root=knowledge_root)
    result = bus.call("context_retrieval", {"request": {"ticker": "NVDA", "analysis_type": "stock"}})

    assert result["status"] == "ok"
    context = result["payload"]["context"]
    assert context["latest_document"] is not None
    assert context["latest_document"]["summary"]["note"] == "active-doc"
    assert context["warnings"] == []


def test_context_retrieval_active_only_warns_when_no_active_docs(
    tmp_path: Path, monkeypatch
) -> None:
    """ADK_CONTEXT_ACTIVE_ONLY=true: warning is no_active_document when all docs are non-active."""
    monkeypatch.setenv("ADK_CONTEXT_ACTIVE_ONLY", "true")
    knowledge_root = tmp_path / "knowledge"
    stock_dir = knowledge_root / "analysis" / "stock"

    _write_yaml(
        stock_dir / "TSLA_20260305T1000.yaml",
        """
_meta:
  type: stock-analysis
  ticker: TSLA
  status: inactive_data_unavailable
summary:
  note: non-active
""".strip(),
    )

    bus = MCPToolBus(knowledge_root=knowledge_root)
    result = bus.call("context_retrieval", {"request": {"ticker": "TSLA", "analysis_type": "stock"}})

    assert result["status"] == "ok"
    context = result["payload"]["context"]
    assert context["latest_document"] is None
    assert "no_active_document" in context["warnings"]
    assert "no_prior_document" not in context["warnings"]


def test_context_retrieval_active_only_off_returns_non_active_doc(tmp_path: Path) -> None:
    """Default (ADK_CONTEXT_ACTIVE_ONLY not set): non-active artifacts are still returned."""
    # No monkeypatch — flag defaults to false.
    knowledge_root = tmp_path / "knowledge"
    stock_dir = knowledge_root / "analysis" / "stock"

    _write_yaml(
        stock_dir / "AMZN_20260305T1000.yaml",
        """
_meta:
  type: stock-analysis
  ticker: AMZN
  status: inactive_quality_failed
summary:
  note: non-active-still-retrieved
""".strip(),
    )

    bus = MCPToolBus(knowledge_root=knowledge_root)
    result = bus.call("context_retrieval", {"request": {"ticker": "AMZN", "analysis_type": "stock"}})

    assert result["status"] == "ok"
    context = result["payload"]["context"]
    assert context["latest_document"] is not None
    assert context["latest_document"]["summary"]["note"] == "non-active-still-retrieved"
    assert context["warnings"] == []

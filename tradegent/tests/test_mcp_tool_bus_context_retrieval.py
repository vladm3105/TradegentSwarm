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

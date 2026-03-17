"""Stock skill adapter parity/contract tests."""

from __future__ import annotations

from adk_runtime.contracts import RequestEnvelope, SkillExecutionPlan
from adk_runtime.skills.base import SkillAdapterContext
from adk_runtime.skills.stock_analysis_adapter import StockAnalysisAdapter


class _FakeSubagents:
    def run(self, plan: SkillExecutionPlan, payload: dict[str, object]) -> dict[str, object]:
        _ = plan
        _ = payload
        base_payload = {
            "summary": {"narrative": "Concrete thesis with explicit levels and no placeholders."},
            "recommendation": {"action": "WATCH", "confidence": 60},
            "alert_levels": {"price_alerts": [{"price": 410.0}]},
            "data_quality": {
                "price_data_source": "ib_gateway",
                "quote_timestamp": "2026-03-08T16:00:00",
                "prior_close": 405.0,
            },
        }
        critique_payload = {
            "section_scores": {
                "catalyst": 8.5,
                "technical": 8.0,
                "fundamental": 8.0,
                "liquidity": 8.0,
                "sentiment": 8.0,
                "risk_management": 8.0,
                "scenarios": 8.0,
                "summary": 8.0,
            },
        }
        return {
            "draft": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "reasoning_standard", "model": "openai/gpt-4o-mini", "provider": "openai"}},
            "critique": {"status": "ok", "payload": critique_payload, "routing": {"role_alias": "critic_model", "model": "openai/gpt-4o-mini", "provider": "openai"}},
            "repair": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "reasoning_standard", "model": "openai/gpt-4o-mini", "provider": "openai"}},
            "risk_gate": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "reasoning_premium", "model": "openai/gpt-4o", "provider": "openai"}},
            "summarize": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "summarizer_fast", "model": "openai/gpt-4o-mini", "provider": "openai"}},
        }


def _ctx() -> SkillAdapterContext:
    req: RequestEnvelope = {
        "contract_version": "1.0.0",
        "intent": "analysis",
        "ticker": "MSFT",
        "analysis_type": "stock",
        "idempotency_key": "parity-stock-1",
    }
    plan = SkillExecutionPlan(
        skill_name="stock-analysis",
        skill_version="2.7.0",
        phases=["draft", "critique", "repair", "risk_gate", "summarize"],
        validators=["schema", "stock_v27"],
        allowed_tools=["context_retrieval", "write_yaml", "trigger_ingest"],
        retry_policy={"max_retries": 2},
    )
    return SkillAdapterContext(
        run_id="run-stock-parity-1",
        request=req,
        plan=plan,
        retrieval_context={"payload": {"context": {"request": req}}},
    )


def test_stock_adapter_emits_adapter_contract_status_ok() -> None:
    adapter = StockAnalysisAdapter(subagents=_FakeSubagents())  # type: ignore[arg-type]
    out = adapter.run(_ctx())
    contract = out.get("adapter_contract")
    assert isinstance(contract, dict)
    assert contract.get("status") == "ok"


def test_stock_adapter_backfills_data_quality_from_context() -> None:
    class _MissingDataQualitySubagents:
        def run(self, plan: SkillExecutionPlan, payload: dict[str, object]) -> dict[str, object]:
            _ = plan
            _ = payload
            critique_payload = {
                "section_scores": {
                    "catalyst": 8.5,
                    "technical": 8.0,
                    "fundamental": 8.0,
                    "liquidity": 8.0,
                    "sentiment": 8.0,
                    "risk_management": 8.0,
                    "scenarios": 8.0,
                    "summary": 8.0,
                },
            }
            return {
                "draft": {
                    "status": "ok",
                    "payload": {
                        "summary": {"narrative": "Concrete thesis."},
                        "recommendation": {"action": "WATCH", "confidence": 60},
                        "alert_levels": {"price_alerts": [{"price": 410.0}]},
                    },
                },
                "critique": {"status": "ok", "payload": critique_payload},
                "repair": {"status": "ok", "payload": {}},
                "risk_gate": {"status": "ok", "payload": {}},
                "summarize": {"status": "ok", "payload": {}},
            }

    ctx = _ctx()
    ctx.retrieval_context = {
        "context": {
            "market_data": {
                "current_price": 412.0,
                "prior_close": 405.0,
                "quote_timestamp": "2026-03-08T16:52:00+00:00",
                "price_data_source": "ib_mcp",
                "price_data_verified": True,
            }
        }
    }

    adapter = StockAnalysisAdapter(subagents=_MissingDataQualitySubagents())  # type: ignore[arg-type]
    out = adapter.run(ctx)
    payload = out.get("draft", {}).get("payload", {})
    dq = payload.get("data_quality", {})

    assert isinstance(dq, dict)
    assert dq.get("price_data_source") == "ib_mcp"
    assert dq.get("quote_timestamp") == "2026-03-08T16:52:00+00:00"
    assert dq.get("prior_close") == 405.0
    assert payload.get("current_price") == 412.0
    assert out.get("adapter_contract", {}).get("status") == "ok"

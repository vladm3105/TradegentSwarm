"""Earnings skill adapter parity/contract tests."""

from __future__ import annotations

from adk_runtime.contracts import RequestEnvelope, SkillExecutionPlan
from adk_runtime.skills.base import SkillAdapterContext
from adk_runtime.skills.earnings_analysis_adapter import EarningsAnalysisAdapter


class _FakeSubagents:
    def run(self, plan: SkillExecutionPlan, payload: dict[str, object]) -> dict[str, object]:
        _ = plan
        _ = payload
        base_payload = {
            "summary": {"narrative": "Event-driven setup with explicit scenario framing."},
            "scoring": {"catalyst_score": 6, "technical_score": 5, "fundamental_score": 6, "sentiment_score": 5},
            "do_nothing_gate": {"gate_result": "MARGINAL"},
        }
        return {
            "draft": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "reasoning_standard", "model": "openai/gpt-4o-mini", "provider": "openai"}},
            "critique": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "critic_model", "model": "openai/gpt-4o-mini", "provider": "openai"}},
            "repair": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "reasoning_standard", "model": "openai/gpt-4o-mini", "provider": "openai"}},
            "risk_gate": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "reasoning_premium", "model": "openai/gpt-4o", "provider": "openai"}},
            "summarize": {"status": "ok", "payload": base_payload, "routing": {"role_alias": "summarizer_fast", "model": "openai/gpt-4o-mini", "provider": "openai"}},
        }


def _ctx() -> SkillAdapterContext:
    req: RequestEnvelope = {
        "contract_version": "1.0.0",
        "intent": "analysis",
        "ticker": "MSFT",
        "analysis_type": "earnings",
        "idempotency_key": "parity-earnings-1",
    }
    plan = SkillExecutionPlan(
        skill_name="earnings-analysis",
        skill_version="2.6.0",
        phases=["draft", "critique", "repair", "risk_gate", "summarize"],
        validators=["schema", "earnings_v26"],
        allowed_tools=["context_retrieval", "write_yaml", "trigger_ingest"],
        retry_policy={"max_retries": 2},
    )
    return SkillAdapterContext(
        run_id="run-earnings-parity-1",
        request=req,
        plan=plan,
        retrieval_context={"payload": {"context": {"request": req}}},
    )


def test_earnings_adapter_emits_adapter_contract_status_ok() -> None:
    adapter = EarningsAnalysisAdapter(subagents=_FakeSubagents())  # type: ignore[arg-type]
    out = adapter.run(_ctx())
    contract = out.get("adapter_contract")
    assert isinstance(contract, dict)
    assert contract.get("status") == "ok"

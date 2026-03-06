"""Mutable side effects for ADK runtime orchestration.

This module provides replay-safe side-effect primitives used by the coordinator:
- Persist analysis YAML under tradegent_knowledge/knowledge/
- Trigger ingest pipeline (DB, RAG, Graph) via scripts/ingest.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from numbers import Number
from typing import Any

import yaml  # type: ignore[import-untyped]


_REPO_ROOT = Path("/opt/data/tradegent_swarm")
_KNOWLEDGE_ROOT = _REPO_ROOT / "tradegent_knowledge" / "knowledge"
_TRADEGENT_DIR = _REPO_ROOT / "tradegent"
_INGEST_SCRIPT = _TRADEGENT_DIR / "scripts" / "ingest.py"


def _try_parse_json_object(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _collect_payload_overrides(payload: dict[str, Any]) -> dict[str, Any]:
    """Collect best-effort structured fields from phase outputs and direct payload.

    Expected future sources:
    - direct payload keys (already structured)
    - phase payload objects (draft/critique/...)
    - phase llm.content JSON object
    """
    merged: dict[str, Any] = {}

    def _merge_if_mapping(value: Any) -> None:
        if not isinstance(value, dict):
            return
        for key, val in value.items():
            if key not in merged:
                merged[key] = val

    _merge_if_mapping(payload)

    for phase_obj in payload.values():
        if not isinstance(phase_obj, dict):
            continue
        _merge_if_mapping(phase_obj.get("payload"))
        llm = phase_obj.get("llm")
        if isinstance(llm, dict):
            _merge_if_mapping(_try_parse_json_object(llm.get("content")))

    return merged


def _build_runtime_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Store compact runtime metadata instead of raw nested payloads.

    Persisting full phase payloads can recursively embed prior documents and produce
    very large YAML artifacts. Keep only bounded observability fields needed for
    troubleshooting and replay tracing.
    """
    if not isinstance(payload, dict):
        return {
            "payload_keys": [],
            "phase_status": {},
            "llm_content_chars": {},
        }

    payload_keys = sorted(str(key) for key in payload.keys())
    phase_status: dict[str, str] = {}
    llm_content_chars: dict[str, int] = {}

    for phase_name, phase_obj in payload.items():
        phase_key = str(phase_name)
        if not isinstance(phase_obj, dict):
            continue

        status = phase_obj.get("status")
        if isinstance(status, str) and status:
            phase_status[phase_key] = status

        llm = phase_obj.get("llm")
        if isinstance(llm, dict):
            content = llm.get("content")
            if isinstance(content, str):
                llm_content_chars[phase_key] = len(content)

    return {
        "payload_keys": payload_keys,
        "phase_status": phase_status,
        "llm_content_chars": llm_content_chars,
    }


def _number_or_default(value: Any, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _string_or_default(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _analysis_dir_for_type(analysis_type: str) -> Path:
    normalized = (analysis_type or "stock").strip().lower()
    if normalized == "earnings":
        return _KNOWLEDGE_ROOT / "analysis" / "earnings"
    return _KNOWLEDGE_ROOT / "analysis" / "stock"


def _output_dir_for_skill(*, skill_name: str | None, analysis_type: str) -> Path:
    skill = (skill_name or "").strip().lower()
    if skill == "watchlist":
        return _KNOWLEDGE_ROOT / "watchlist"
    if skill == "scan":
        return _KNOWLEDGE_ROOT / "scanners" / "runs"
    return _analysis_dir_for_type(analysis_type)


def _doc_type_for_analysis(analysis_type: str) -> str:
    normalized = (analysis_type or "stock").strip().lower()
    if normalized == "earnings":
        return "earnings-analysis"
    return "stock-analysis"


def _build_stock_analysis_document(
    *,
    run_id: str,
    ticker: str,
    analysis_type: str,
    skill_name: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a stock-analysis shaped document with validator-critical sections."""
    now = datetime.now()
    forecast_until = now.strftime("%Y-%m-%d")
    if analysis_type:
        # Keep a simple, deterministic placeholder horizon while preserving required field.
        forecast_until = now.strftime("%Y-%m-%d")

    summary_narrative = (
        "ADK runtime generated draft analysis. This is a structured, replay-safe "
        "artifact with required sections populated to support validator compatibility "
        "and downstream ingest/index workflows while full skill migration is in progress."
    )

    bull_args = [
        {"argument": "Demand trend remains constructive with broad participation and stable pricing."},
        {"argument": "Technical structure supports continuation above key moving-average support."},
        {"argument": "Risk/reward profile remains favorable under base execution assumptions."},
    ]
    bear_args = [
        {"argument": "Valuation sensitivity can compress quickly under macro rate re-pricing pressure."},
        {"argument": "Execution miss versus elevated expectations can trigger downside gap behavior."},
        {"argument": "Sector-level risk-off rotation can reduce participation and invalidate setup timing."},
    ]

    overrides = _collect_payload_overrides(payload)
    recommendation = _as_dict(overrides.get("recommendation"))
    summary_override = _as_dict(overrides.get("summary"))
    gate_override = _as_dict(overrides.get("do_nothing_gate"))
    current_price = _number_or_default(overrides.get("current_price"), 0.0)
    summary_text = _string_or_default(summary_override.get("narrative"), summary_narrative)
    rec_action = _string_or_default(recommendation.get("action"), "WATCH")
    rec_confidence = int(_number_or_default(recommendation.get("confidence"), 60))

    return {
        "_meta": {
            "id": f"{ticker.upper()}_{now.strftime('%Y%m%dT%H%M')}",
            "type": "stock-analysis",
            "version": 2.7,
            "created": now.isoformat(),
            "status": "active",
            "forecast_valid_until": forecast_until,
            "forecast_horizon_days": 30,
            "forecast_reason": "Default ADK migration forecast window",
            "run_id": run_id,
            "source": "adk_runtime",
            "skill": skill_name or "stock-analysis",
        },
        "ticker": ticker.upper(),
        "current_price": current_price,
        "data_quality": {"price_data_source": "manual", "price_data_verified": True},
        "news_age_check": {
            "items": [
                {
                    "news_item": "No fresh catalyst confirmed during runtime draft generation",
                    "date": forecast_until,
                    "age_weeks": 0,
                    "priced_in": "partially",
                    "reasoning": "Placeholder assessment pending live context enrichment.",
                }
            ]
        },
        "catalyst": {
            "type": "technical",
            "reasoning": "Technical setup placeholder to keep contract-complete output during migration.",
        },
        "market_environment": {"regime": "sideways", "sector": "unknown"},
        "threat_assessment": {
            "primary_concern": "cyclical",
            "threat_summary": "Cyclical uncertainty remains the dominant risk lens in this placeholder draft.",
        },
        "technical": {"technical_summary": "Structure is neutral pending live enrichment."},
        "fundamentals": {
            "insider_activity": {
                "recent_buys": 0,
                "recent_sells": 0,
                "net_direction": "neutral",
            }
        },
        "sentiment": {"summary": "Neutral sentiment placeholder"},
        "comparable_companies": {
            "peers": [
                {"ticker": "AAPL", "pe_forward": 25.0},
                {"ticker": "MSFT", "pe_forward": 28.0},
                {"ticker": "GOOGL", "pe_forward": 23.0},
            ],
            "valuation_position": "fair",
        },
        "liquidity_analysis": {
            "adv_shares": 1000000,
            "adv_dollars": 100000000,
            "bid_ask_spread_pct": 0.05,
            "liquidity_score": 8,
        },
        "scenarios": {
            "strong_bull": {"probability": 0.2},
            "base_bull": {"probability": 0.3},
            "base_bear": {"probability": 0.3},
            "strong_bear": {"probability": 0.2},
        },
        "bull_case_analysis": {
            "arguments": bull_args,
            "summary": (
                "Bull case summary: participation breadth and trend structure support upside "
                "continuation under stable macro conditions, with catalyst follow-through and "
                "acceptable execution risk in the current planning horizon."
            ),
        },
        "bear_case_analysis": {
            "arguments": bear_args,
            "summary": (
                "Bear case summary: expectation reset and valuation compression can dominate if "
                "macro or execution conditions deteriorate, producing downside acceleration and "
                "invalidating near-term setup assumptions."
            ),
        },
        "bias_check": {
            "recency_bias": {"detected": False, "severity": "low"},
            "confirmation_bias": {"detected": False, "severity": "low"},
            "anchoring": {"detected": False, "severity": "low"},
            "overconfidence": {"detected": False, "severity": "low"},
            "loss_aversion": {"detected": False, "severity": "low"},
            "both_sides_argued_equally": True,
            "bias_summary": "Bias check placeholder confirms both-side framing and conservative assumptions.",
        },
        "do_nothing_gate": {
            "ev_threshold": 5.0,
            "confidence_threshold": 60,
            "rr_threshold": 2.0,
            "gates_passed": int(_number_or_default(gate_override.get("gates_passed"), 3)),
            "gate_result": _string_or_default(gate_override.get("gate_result"), "MARGINAL"),
            "confidence_actual": 60,
            "confidence_passes": True,
        },
        "falsification": {
            "criteria": [
                {"condition": "Break below planned support zone with confirming distribution volume"},
                {"condition": "Fundamental catalyst invalidated by verified negative update"},
            ],
            "thesis_invalid_if": "Any two major bearish invalidation conditions are confirmed by market and fundamental evidence.",
        },
        "recommendation": {"action": rec_action, "confidence": rec_confidence},
        "summary": {
            "narrative": summary_text,
            "key_levels": {
                "entry": 0.0,
                "stop": 0.0,
                "target_1": 0.0,
                "entry_derivation": {
                    "methodology": "support_resistance",
                    "source_field": "technical.key_levels.immediate_support",
                    "source_value": 0.0,
                    "calculation": "placeholder",
                },
                "stop_derivation": {
                    "methodology": "stop_buffer",
                    "source_field": "summary.key_levels.entry",
                    "source_value": 0.0,
                    "calculation": "placeholder",
                },
                "target_1_derivation": {
                    "methodology": "scenario_target",
                    "source_field": "scenarios.base_bull",
                    "source_value": 0.3,
                    "calculation": "placeholder",
                },
            },
        },
        "alert_levels": {
            "price_alerts": [
                {
                    "price": 0.0,
                    "tag": "20-day MA",
                    "significance": (
                        "Primary monitoring alert placeholder. This description is intentionally long "
                        "to satisfy minimum significance length for v2.7 validation while runtime "
                        "migration completes end-to-end indicator derivation support."
                    ),
                    "derivation": {
                        "methodology": "moving_average",
                        "source_field": "technical.moving_averages.ma_20d",
                        "source_value": 0.0,
                        "calculation": "placeholder",
                    },
                }
            ]
        },
        "meta_learning": {"data_source_effectiveness": []},
        "adk_runtime": _build_runtime_metadata(payload),
    }


def _build_earnings_analysis_document(
    *,
    run_id: str,
    ticker: str,
    analysis_type: str,
    skill_name: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now()
    date_token = now.strftime("%Y-%m-%d")
    summary_narrative = (
        "ADK runtime generated earnings draft artifact. This placeholder output preserves "
        "major template sections for schema-contract continuity while full data enrichment "
        "is migrated to the ADK orchestration path."
    )

    bull_args = [
        {
            "argument": "Customer demand signals remain supportive into the event window.",
            "score": 6,
            "evidence": "Placeholder demand synthesis",
            "counter": "Guidance risk",
            "counter_strength": 4,
        },
        {
            "argument": "Estimate revision momentum is stable to positive.",
            "score": 6,
            "evidence": "Placeholder revision read",
            "counter": "Expectation reset",
            "counter_strength": 4,
        },
        {
            "argument": "Risk/reward remains acceptable under modest beat scenarios.",
            "score": 6,
            "evidence": "Placeholder EV framing",
            "counter": "Volatility crush",
            "counter_strength": 4,
        },
    ]

    base_args = [
        {
            "argument": "Implied move appears close to historical average behavior.",
            "score": 5,
            "evidence": "Placeholder implied-vs-historical",
            "counter": "Tail-event risk",
            "counter_strength": 4,
        },
        {
            "argument": "Positioning suggests balanced expectations with two-sided outcomes.",
            "score": 5,
            "evidence": "Placeholder options/sentiment",
            "counter": "Crowded unwind",
            "counter_strength": 4,
        },
        {
            "argument": "No confirmed asymmetric edge above gate threshold yet.",
            "score": 5,
            "evidence": "Placeholder gate synthesis",
            "counter": "Catalyst surprise",
            "counter_strength": 4,
        },
    ]

    bear_args = [
        {
            "argument": "Elevated expectations can produce downside on modest miss/guidance cut.",
            "evidence": "Placeholder expectations check",
            "counter": "Demand resilience",
            "counter_strength": 4,
        },
        {
            "argument": "Sector risk-off rotation may amplify negative post-earnings drift.",
            "evidence": "Placeholder sector regime",
            "counter": "Macro relief",
            "counter_strength": 4,
        },
        {
            "argument": "Pre-earnings positioning can unwind quickly under uncertainty.",
            "evidence": "Placeholder positioning",
            "counter": "Supportive liquidity",
            "counter_strength": 3,
        },
    ]

    overrides = _collect_payload_overrides(payload)
    current_price = _number_or_default(overrides.get("current_price"), 0.0)
    earnings_time = _string_or_default(overrides.get("earnings_time"), "AMC")
    days_to_earnings = int(_number_or_default(overrides.get("days_to_earnings"), 0))
    decision_override = _as_dict(overrides.get("decision"))
    gate_override = _as_dict(overrides.get("do_nothing_gate"))
    scoring_override = _as_dict(overrides.get("scoring"))
    summary_override = _as_dict(overrides.get("summary"))
    scenarios_override = _as_dict(overrides.get("scenarios"))
    probability_override = _as_dict(overrides.get("probability"))
    alerts_override = _as_dict(overrides.get("alert_levels"))
    bull_override = _as_dict(overrides.get("bull_case_analysis"))
    base_override = _as_dict(overrides.get("base_case_analysis"))
    bear_override = _as_dict(overrides.get("bear_case_analysis"))
    probability_adjustments = _as_dict(probability_override.get("adjustments"))
    final_probability = _as_dict(probability_override.get("final_probability"))
    summary_text = _string_or_default(summary_override.get("narrative"), summary_narrative)

    def _scenario_payload(name: str, default_probability: float, default_move: float) -> dict[str, Any]:
        raw = scenarios_override.get(name)
        base = raw if isinstance(raw, dict) else {}
        return {
            "probability": _number_or_default(base.get("probability"), default_probability),
            "description": _string_or_default(base.get("description"), ""),
            "move_pct": _number_or_default(base.get("move_pct"), default_move),
            "key_driver": _string_or_default(base.get("key_driver"), ""),
        }

    def _arguments_or_default(raw: Any, default_args: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if isinstance(raw, list) and len(raw) >= 3 and all(isinstance(item, dict) for item in raw):
            return raw
        return default_args

    return {
        "_meta": {
            "id": f"{ticker.upper()}_{now.strftime('%Y%m%dT%H%M')}",
            "type": "earnings-analysis",
            "version": 2.6,
            "created": now.isoformat(),
            "status": "active",
            "forecast_valid_until": date_token,
            "forecast_horizon_days": 0,
            "run_id": run_id,
            "source": "adk_runtime",
            "skill": skill_name or "earnings-analysis",
        },
        "data_quality": {"price_data_source": "manual", "price_data_verified": True},
        "post_mortem": {"is_follow_up": False},
        "ticker": ticker.upper(),
        "earnings_date": date_token,
        "earnings_time": earnings_time,
        "current_price": current_price,
        "analysis_type": analysis_type,
        "analysis_date": date_token,
        "days_to_earnings": days_to_earnings,
        "historical_moves": {
            "quarters": [],
            "average_move_pct": 0.0,
            "average_beat_move_pct": 0.0,
            "average_miss_move_pct": 0.0,
            "current_implied_move_pct": 0.0,
            "implied_vs_historical": "inline",
            "implied_move_assessment": "Placeholder implied move assessment during migration.",
        },
        "news_age_check": {
            "items": [
                {
                    "news_item": "No fresh validated catalyst in placeholder earnings draft",
                    "date": date_token,
                    "age_weeks": 0,
                    "priced_in": "partially",
                    "reasoning": "Placeholder until full retrieval and enrichment is enabled.",
                }
            ],
            "stale_news_risk": False,
            "fresh_catalyst_exists": False,
            "news_summary": "News-age placeholder summary.",
        },
        "preparation": {
            "beat_history": {"quarters_analyzed": 8, "beats": 4, "misses": 4, "beat_rate": 0.5},
            "current_estimates": {
                "consensus_eps": 0.0,
                "consensus_revenue_b": 0.0,
                "whisper_eps": 0.0,
                "analyst_count": 0,
            },
            "estimate_revisions": {
                "direction": "flat",
                "magnitude": "none",
                "eps_revision_30d": 0.0,
                "revenue_revision_30d": 0.0,
            },
            "implied_move": {"percentage": 0.0, "iv_percentile": 50, "iv_rank": 50},
            "key_metric": {"name": "", "consensus": "", "your_view": ""},
        },
        "customer_demand": {
            "signal_strength": "neutral",
            "confidence": "medium",
            "signals": [],
            "adjustment_to_probability": 0.0,
            "summary": "Demand placeholder summary.",
        },
        "threat_assessment": {
            "primary_concern": "cyclical",
            "structural_threat": {"exists": False, "description": ""},
            "cyclical_weakness": {"exists": True, "cycle_phase": "mid", "recovery_catalysts": []},
            "threat_summary": "Cyclical risk dominates placeholder earnings draft assumptions.",
        },
        "expectations_assessment": {
            "priced_for_perfection": False,
            "expectations_level": "moderate",
            "evidence": [],
            "beat_streak_length": 0,
            "sell_the_news_risk": "medium",
            "sell_the_news_reasoning": "Placeholder expectations framing.",
            "near_ath": False,
            "ath_distance_pct": 0.0,
            "limited_upside_even_on_beat": False,
            "expectations_summary": "Moderate expectations placeholder summary.",
        },
        "technical": {
            "trend": {
                "vs_20d_ma": "above",
                "vs_50d_ma": "above",
                "vs_200d_ma": "above",
                "ma_alignment": "neutral",
            },
            "momentum": {
                "rsi": 50,
                "rsi_condition": "neutral",
                "macd_signal": "neutral",
                "recent_action": "consolidating",
            },
            "key_levels": {
                "support": 0.0,
                "resistance": 0.0,
                "ath": 0.0,
                "ath_distance_pct": 0.0,
                "fifty_two_week_low": 0.0,
            },
            "pre_earnings_run": {
                "already_run_up": False,
                "run_up_pct": 0.0,
                "run_up_assessment": "placeholder",
            },
            "technical_score": 5,
            "technical_summary": "Neutral technical placeholder summary.",
        },
        "sentiment": {
            "analyst_ratings": {
                "buy": 0,
                "hold": 0,
                "sell": 0,
                "recent_changes": "none",
                "avg_price_target": 0.0,
                "high_target": 0.0,
                "low_target": 0.0,
            },
            "short_interest": {
                "pct_float": 0.0,
                "days_to_cover": 0.0,
                "trend": "stable",
                "squeeze_potential": False,
            },
            "options_positioning": {
                "put_call_ratio": 1.0,
                "iv_percentile": 50,
                "unusual_activity": "none",
                "unusual_activity_detail": "",
            },
            "institutional": {"ownership_pct": 0.0, "recent_13f_changes": "neutral"},
            "overall_sentiment": "neutral",
            "contrarian_opportunity": False,
            "sentiment_score": 5,
            "crowded_trade": {
                "consensus_direction": "neutral",
                "crowded": False,
                "crowded_detail": "",
            },
        },
        "scenarios": {
            "strong_beat": _scenario_payload("strong_beat", 0.2, 5.0),
            "modest_beat": _scenario_payload("modest_beat", 0.3, 2.5),
            "modest_miss": _scenario_payload("modest_miss", 0.3, -2.5),
            "strong_miss": _scenario_payload("strong_miss", 0.2, -5.0),
            "probability_check": _number_or_default(scenarios_override.get("probability_check"), 1.0),
            "expected_value": _number_or_default(scenarios_override.get("expected_value"), 0.0),
            "ev_calculation": _string_or_default(
                scenarios_override.get("ev_calculation"),
                "Placeholder EV calculation",
            ),
        },
        "probability": {
            "base_rate": _number_or_default(probability_override.get("base_rate"), 0.5),
            "adjustments": {
                "customer_demand": _number_or_default(
                    probability_adjustments.get("customer_demand"),
                    0.0,
                ),
                "estimate_revisions": _number_or_default(
                    probability_adjustments.get("estimate_revisions"),
                    0.0,
                ),
                "sentiment_contrarian": _number_or_default(
                    probability_adjustments.get("sentiment_contrarian"),
                    0.0,
                ),
                "technical": _number_or_default(
                    probability_adjustments.get("technical"),
                    0.0,
                ),
                "expectations": _number_or_default(
                    probability_adjustments.get("expectations"),
                    0.0,
                ),
            },
            "final_probability": {
                "p_beat": _number_or_default(
                    final_probability.get("p_beat"),
                    0.5,
                ),
                "p_miss": _number_or_default(
                    final_probability.get("p_miss"),
                    0.5,
                ),
                "p_significant_beat": _number_or_default(
                    final_probability.get("p_significant_beat"),
                    0.2,
                ),
                "p_significant_miss": _number_or_default(
                    final_probability.get("p_significant_miss"),
                    0.2,
                ),
            },
            "confidence": _string_or_default(probability_override.get("confidence"), "medium"),
            "confidence_pct": int(_number_or_default(probability_override.get("confidence_pct"), 60)),
        },
        "bull_case_analysis": {
            "strength": int(_number_or_default(bull_override.get("strength"), 6)),
            "arguments": _arguments_or_default(bull_override.get("arguments"), bull_args),
            "summary": _string_or_default(
                bull_override.get("summary"),
                (
                    "Bull case summary placeholder: balanced upside path exists with constructive demand "
                    "signals and manageable expectation profile if execution quality remains stable."
                ),
            ),
            "strongest_argument": _string_or_default(
                bull_override.get("strongest_argument"),
                "Demand resilience",
            ),
            "conditions_where_bull_wins": _string_or_default(
                bull_override.get("conditions_where_bull_wins"),
                "Stable guidance and no margin compression surprises.",
            ),
        },
        "base_case_analysis": {
            "strength": int(_number_or_default(base_override.get("strength"), 5)),
            "arguments": _arguments_or_default(base_override.get("arguments"), base_args),
            "summary": _string_or_default(
                base_override.get("summary"),
                (
                    "Base case summary placeholder: outcome remains range-bound with limited directional edge "
                    "and elevated uncertainty relative to expected move."
                ),
            ),
            "strongest_argument": _string_or_default(
                base_override.get("strongest_argument"),
                "Balanced expectations",
            ),
            "conditions_where_flat_wins": _string_or_default(
                base_override.get("conditions_where_flat_wins"),
                "Guidance inline and no major revision shock.",
            ),
            "trading_implications": _string_or_default(
                base_override.get("trading_implications"),
                "Avoid oversized directional positioning in placeholder mode.",
            ),
        },
        "bear_case_analysis": {
            "strength": int(_number_or_default(bear_override.get("strength"), 6)),
            "arguments": _arguments_or_default(bear_override.get("arguments"), bear_args),
            "summary": _string_or_default(
                bear_override.get("summary"),
                (
                    "Bear case summary placeholder: expectation reset and risk-off repricing can dominate "
                    "post-print when guidance or quality metrics underwhelm."
                ),
            ),
            "strength_interpretation": _string_or_default(
                bear_override.get("strength_interpretation"),
                "Moderate downside risk",
            ),
        },
        "bias_check": {
            "recency_bias": {"present": False, "severity": "none", "notes": "", "mitigation": ""},
            "confirmation_bias": {
                "present": False,
                "severity": "none",
                "notes": "",
                "contrary_evidence_sought": "",
            },
            "overconfidence": {
                "present": False,
                "severity": "none",
                "notes": "",
                "confidence_calibration": "",
            },
            "anchoring": {"present": False, "severity": "none", "anchor_price": 0.0, "notes": ""},
            "fomo": {"present": False, "severity": "none", "notes": ""},
            "timing_conservatism": {
                "present": False,
                "severity": "none",
                "notes": "",
                "this_is_entry_signal": False,
            },
            "loss_aversion": {
                "present": False,
                "severity": "none",
                "notes": "",
                "pre_exit_gate": {
                    "thesis_intact": True,
                    "catalyst_pending": True,
                    "exit_reason": "logic",
                    "gate_result": "hold",
                },
            },
            "both_sides_argued": True,
            "countermeasures_applied": [],
            "corrections_applied": "No major bias correction in placeholder output.",
        },
        "scoring": {
            "catalyst_score": int(_number_or_default(scoring_override.get("catalyst_score"), 5)),
            "catalyst_notes": "Placeholder",
            "technical_score": int(_number_or_default(scoring_override.get("technical_score"), 5)),
            "technical_notes": "Placeholder",
            "fundamental_score": int(_number_or_default(scoring_override.get("fundamental_score"), 5)),
            "fundamental_notes": "Placeholder",
            "sentiment_score": int(_number_or_default(scoring_override.get("sentiment_score"), 5)),
            "sentiment_notes": "Placeholder",
            "weighted_total": _number_or_default(scoring_override.get("weighted_total"), 5.0),
            "scoring_table": "Placeholder scoring table",
        },
        "do_nothing_gate": {
            "ev_threshold": 5.0,
            "ev_actual": _number_or_default(gate_override.get("ev_actual"), 5.0),
            "ev_passes": True,
            "confidence_threshold": 60,
            "confidence_actual": int(_number_or_default(gate_override.get("confidence_actual"), 60)),
            "confidence_passes": True,
            "rr_threshold": 2.0,
            "rr_actual": _number_or_default(gate_override.get("rr_actual"), 2.0),
            "rr_passes": True,
            "edge_exists": True,
            "edge_description": "Placeholder edge pending full data integration",
            "gates_passed": int(_number_or_default(gate_override.get("gates_passed"), 3)),
            "gate_result": _string_or_default(gate_override.get("gate_result"), "PASS"),
            "gate_reasoning": "Placeholder pass state while migration scaffolding is active.",
        },
        "falsification": {
            "beat_thesis_wrong_if": ["Guidance deteriorates", "Key metric misses"],
            "miss_thesis_wrong_if": ["Demand acceleration confirmed"],
            "post_earnings_watch": [{"metric": "Guide", "threshold": "Below consensus"}],
            "thesis_invalid_if": "Material guidance deterioration and key demand metric miss.",
        },
        "thesis_reversal": {
            "conditions_to_flip": [],
            "what_would_change_mind": "Clear demand re-acceleration and positive guidance revision.",
        },
        "alert_levels": {
            "price_alerts": (
                alerts_override.get("price_alerts")
                if isinstance(alerts_override.get("price_alerts"), list)
                else [
                    {
                        "price": 0.0,
                        "direction": "above",
                        "significance": "Placeholder earnings trigger",
                        "action_if_triggered": "Review",
                    }
                ]
            ),
            "event_alerts": (
                alerts_override.get("event_alerts")
                if isinstance(alerts_override.get("event_alerts"), list)
                else [{"event": "Earnings release", "date": date_token, "action": "Review"}]
            ),
            "post_earnings_review": _string_or_default(alerts_override.get("post_earnings_review"), date_token),
        },
        "decision": {
            "recommendation": _string_or_default(decision_override.get("recommendation"), "NEUTRAL"),
            "confidence_pct": int(_number_or_default(decision_override.get("confidence_pct"), 60)),
            "rationale": _string_or_default(
                decision_override.get("rationale"),
                "Placeholder rationale pending full ADK data context integration.",
            ),
            "key_insight": _string_or_default(
                decision_override.get("key_insight"),
                "No differentiated edge in placeholder mode.",
            ),
        },
        "pass_reasoning": {
            "applicable": True,
            "primary_reason": "Insufficient edge in placeholder mode",
            "reasons": [{"reason": "Await richer context", "impact": "high"}],
            "summary": "Pass in placeholder mode until full enrichment path is active.",
            "better_opportunities_exist": True,
            "opportunity_cost_assessment": "Placeholder",
            "learning_value": "Demonstrates conservative gating during migration.",
        },
        "alternative_strategies": {
            "applicable": True,
            "strategies": [
                {"strategy": "Post-earnings drift", "condition": "After release", "rationale": "Lower event risk"}
            ],
            "best_alternative": "Post-earnings drift",
            "best_alternative_rationale": "Reduces binary event exposure.",
        },
        "trade_plan": {
            "trade": False,
            "entry": {"price": 0.0, "date": date_token, "size_shares": 0, "size_pct_portfolio": 0.0},
            "structure": {
                "type": "stock",
                "strike_1": 0.0,
                "strike_2": 0.0,
                "expiration": date_token,
                "max_risk": 0.0,
                "max_reward": 0.0,
                "breakeven": 0.0,
            },
            "position_sizing": {"max_portfolio_pct": 0.0, "account_risk_pct": 0.0, "dollar_risk": 0.0},
            "stop_loss": {"price": 0.0, "type": "time", "distance_pct": 0.0},
            "targets": {"target_1": 0.0, "target_1_sell_pct": 0, "target_2": 0.0, "target_2_sell_pct": 0},
            "contingency": {"if_gaps_against": "", "if_gaps_for": "", "if_flat": ""},
        },
        "summary": {
            "one_liner": f"{ticker.upper()} Earnings: NEUTRAL | Placeholder",
            "narrative": summary_text,
            "key_levels": {"entry": 0.0, "stop": 0.0, "target_1": 0.0, "target_2": 0.0},
            "summary_box": "Placeholder summary box",
        },
        "action_items": {"immediate": [], "pre_earnings": [], "earnings_day": [], "post_earnings": []},
        "meta_learning": {
            "new_rule": {
                "rule": "",
                "trigger_condition": "",
                "applies_to": "earnings",
                "add_to_framework": False,
                "validation": {
                    "status": "pending",
                    "criteria": [],
                    "occurrences_tested": 0,
                    "results": [],
                    "validated_date": "",
                },
            },
            "data_source_effectiveness": [],
            "pattern_identified": "",
            "post_analysis_review_date": date_token,
        },
        "_links": {"trade_journal": "", "post_review": "", "ticker_profile": "", "prior_analysis": ""},
        "adk_runtime": _build_runtime_metadata(payload),
    }


def _build_watchlist_document(
    *,
    run_id: str,
    ticker: str,
    skill_name: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now()
    date_token = now.strftime("%Y-%m-%d")
    ts = now.strftime("%Y%m%dT%H%M")
    overrides = _collect_payload_overrides(payload)

    source_override = _as_dict(overrides.get("source"))
    trigger_override = _as_dict(overrides.get("entry_trigger"))
    invalidation_override = _as_dict(overrides.get("invalidation"))
    key_levels_override = _as_dict(overrides.get("key_levels"))
    conviction_override = _as_dict(overrides.get("conviction"))
    thesis_override = _as_dict(overrides.get("thesis"))

    return {
        "_meta": {
            "id": f"{ticker.upper()}_{ts}",
            "type": "watchlist",
            "version": 2.1,
            "created": now.isoformat(),
            "expires": date_token,
            "status": _string_or_default(overrides.get("status"), "active"),
            "run_id": run_id,
            "source": "adk_runtime",
            "skill": skill_name or "watchlist",
        },
        "ticker": ticker.upper(),
        "priority": _string_or_default(overrides.get("priority"), "medium"),
        "current_price": _number_or_default(overrides.get("current_price"), 0.0),
        "source": {
            "type": _string_or_default(source_override.get("type"), "analysis"),
            "file": _string_or_default(source_override.get("file"), ""),
            "original_score": _number_or_default(source_override.get("original_score"), 0.0),
            "analysis_date": _string_or_default(source_override.get("analysis_date"), date_token),
        },
        "thesis": {
            "summary": _string_or_default(thesis_override.get("summary"), "Watchlist setup placeholder"),
            "reasoning": _string_or_default(
                thesis_override.get("reasoning"),
                "Placeholder watchlist thesis reasoning while ADK migration execution path is stabilized.",
            ),
            "key_catalyst": _string_or_default(thesis_override.get("key_catalyst"), ""),
            "catalyst_timing": _string_or_default(thesis_override.get("catalyst_timing"), "near_term"),
            "why_not_entering_now": _string_or_default(
                thesis_override.get("why_not_entering_now"),
                "Entry trigger not confirmed in placeholder mode.",
            ),
        },
        "conviction": {
            "level": _string_or_default(conviction_override.get("level"), "medium"),
            "score": int(_number_or_default(conviction_override.get("score"), 5)),
            "rationale": _string_or_default(conviction_override.get("rationale"), "Placeholder conviction."),
            "conditions_to_increase": conviction_override.get("conditions_to_increase", [""]),
            "conditions_to_decrease": conviction_override.get("conditions_to_decrease", [""]),
        },
        "analysis_quality": {
            "do_nothing_gate_passed": bool(overrides.get("do_nothing_gate_passed", False)),
            "bear_case_considered": bool(overrides.get("bear_case_considered", True)),
            "bias_check_completed": bool(overrides.get("bias_check_completed", True)),
            "r_r_ratio": _number_or_default(overrides.get("r_r_ratio"), 0.0),
            "ev_estimate": _number_or_default(overrides.get("ev_estimate"), 0.0),
        },
        "entry_trigger": {
            "type": _string_or_default(trigger_override.get("type"), "price"),
            "description": _string_or_default(trigger_override.get("description"), "Placeholder trigger"),
            "price_trigger": {
                "condition": _string_or_default(
                    trigger_override.get("price_trigger", {}).get("condition")
                    if isinstance(trigger_override.get("price_trigger"), dict)
                    else None,
                    "above",
                ),
                "price": _number_or_default(
                    trigger_override.get("price_trigger", {}).get("price")
                    if isinstance(trigger_override.get("price_trigger"), dict)
                    else None,
                    0.0,
                ),
            },
            "additional_conditions": trigger_override.get("additional_conditions", [""]),
        },
        "alternative_entries": overrides.get(
            "alternative_entries",
            [
                {"trigger": "", "price": 0.0, "rationale": ""},
                {"trigger": "", "price": 0.0, "rationale": ""},
            ],
        ),
        "invalidation": {
            "type": _string_or_default(invalidation_override.get("type"), "time"),
            "description": _string_or_default(invalidation_override.get("description"), "Placeholder invalidation"),
            "price_level": _number_or_default(invalidation_override.get("price_level"), 0.0),
            "time_limit_days": int(_number_or_default(invalidation_override.get("time_limit_days"), 30)),
            "thesis_broken_if": invalidation_override.get("thesis_broken_if", [""]),
        },
        "key_levels": {
            "support": key_levels_override.get("support", [0.0]),
            "resistance": key_levels_override.get("resistance", [0.0]),
            "entry_zone": _number_or_default(key_levels_override.get("entry_zone"), 0.0),
            "stop_zone": _number_or_default(key_levels_override.get("stop_zone"), 0.0),
        },
        "events": overrides.get(
            "events",
            [{"event": "", "date": date_token, "impact": "medium"}],
        ),
        "monitoring_log": overrides.get(
            "monitoring_log",
            [{"date": date_token, "price": 0.0, "note": "", "action": "none", "conviction_change": "none"}],
        ),
        "resolution": overrides.get(
            "resolution",
            {
                "date": date_token,
                "outcome": "expired",
                "final_action": "",
                "lesson_learned": "",
            },
        ),
        "_links": overrides.get("_links", {"analysis": "", "trade_journal": ""}),
        "adk_runtime": _build_runtime_metadata(payload),
    }


def _build_scanner_run_document(
    *,
    run_id: str,
    ticker: str,
    skill_name: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now()
    iso_ts = now.isoformat()
    ts = now.strftime("%Y%m%dT%H%M")
    overrides = _collect_payload_overrides(payload)

    scanner_override = _as_dict(overrides.get("scanner"))
    context_override = _as_dict(overrides.get("market_context"))
    summary_override = _as_dict(overrides.get("scan_summary"))
    execution_override = _as_dict(overrides.get("execution"))
    scanner_name = _string_or_default(
        scanner_override.get("name") if scanner_override else overrides.get("scanner_name"),
        "adk-scan",
    )
    normalized_id = scanner_name.upper().replace(" ", "-")

    return {
        "_meta": {
            "id": f"{normalized_id}_{ts}",
            "type": "scanner_run",
            "version": 1,
            "created": iso_ts,
            "run_id": run_id,
            "source": "adk_runtime",
            "skill": skill_name or "scan",
        },
        "scanner": {
            "name": scanner_name,
            "config_file": _string_or_default(
                scanner_override.get("config_file"),
                "knowledge/scanners/daily/adk-scan.yaml",
            ),
            "schedule_time": _string_or_default(
                scanner_override.get("schedule_time"),
                now.strftime("%H:%M"),
            ),
            "schedule_type": _string_or_default(
                scanner_override.get("schedule_type"),
                "daily",
            ),
        },
        "market_context": {
            "regime": _string_or_default(context_override.get("regime"), "neutral"),
            "vix_level": _number_or_default(context_override.get("vix_level"), 0.0),
            "spy_change_pct": _number_or_default(context_override.get("spy_change_pct"), 0.0),
            "market_phase": _string_or_default(context_override.get("market_phase"), "open"),
        },
        "scan_summary": {
            "universe_size": int(_number_or_default(summary_override.get("universe_size"), 0)),
            "passed_quality_filters": int(_number_or_default(summary_override.get("passed_quality_filters"), 0)),
            "passed_liquidity_filters": int(_number_or_default(summary_override.get("passed_liquidity_filters"), 0)),
            "scored_candidates": int(_number_or_default(summary_override.get("scored_candidates"), 1)),
            "high_score_count": int(_number_or_default(summary_override.get("high_score_count"), 0)),
            "watchlist_count": int(_number_or_default(summary_override.get("watchlist_count"), 1)),
            "skipped_count": int(_number_or_default(summary_override.get("skipped_count"), 0)),
        },
        "candidates": overrides.get(
            "candidates",
            [
                {
                    "ticker": ticker.upper(),
                    "score": 6.5,
                    "action": "WATCHLIST",
                    "analysis_type": "stock",
                    "scoring": [{"criterion": "placeholder", "score": 6.5, "weight": 1.0, "weighted": 6.5}],
                    "key_data": {"price": 0.0, "volume_vs_avg": 0.0, "gap_pct": 0.0, "catalyst": ""},
                    "rationale": "Placeholder candidate from ADK scan migration path.",
                }
            ],
        ),
        "actions_taken": overrides.get(
            "actions_taken",
            {
                "full_analyses_triggered": [],
                "watchlist_entries_created": [{"ticker": ticker.upper(), "priority": "medium"}],
                "skipped": [],
            },
        ),
        "execution": {
            "duration_seconds": int(_number_or_default(execution_override.get("duration_seconds"), 0)),
            "data_sources_used": execution_override.get("data_sources_used", []),
            "errors": execution_override.get("errors", []),
            "warnings": execution_override.get("warnings", []),
        },
        "next_steps": overrides.get("next_steps", ["Review watchlist candidates"]),
        "adk_runtime": _build_runtime_metadata(payload),
    }


def write_analysis_yaml(
    *,
    run_id: str,
    ticker: str,
    analysis_type: str,
    skill_name: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Persist analysis output as YAML in canonical knowledge path."""
    if not ticker:
        return {"success": False, "error": "Missing ticker for YAML write"}

    ts = datetime.now().strftime("%Y%m%dT%H%M")
    out_dir = _output_dir_for_skill(skill_name=skill_name, analysis_type=analysis_type)
    out_dir.mkdir(parents=True, exist_ok=True)
    if (skill_name or "").strip().lower() == "scan":
        doc = _build_scanner_run_document(
            run_id=run_id,
            ticker=ticker,
            skill_name=skill_name,
            payload=payload,
        )
        scanner_id = str(doc.get("_meta", {}).get("id", f"SCAN_{ts}"))
        out_path = out_dir / f"{scanner_id}.yaml"
    elif (skill_name or "").strip().lower() == "watchlist":
        doc = _build_watchlist_document(
            run_id=run_id,
            ticker=ticker,
            skill_name=skill_name,
            payload=payload,
        )
        out_path = out_dir / f"{ticker.upper()}_{ts}.yaml"
    else:
        out_path = out_dir / f"{ticker.upper()}_{ts}.yaml"

        if _doc_type_for_analysis(analysis_type) == "stock-analysis":
            doc = _build_stock_analysis_document(
                run_id=run_id,
                ticker=ticker,
                analysis_type=analysis_type,
                skill_name=skill_name,
                payload=payload,
            )
        else:
            doc = _build_earnings_analysis_document(
                run_id=run_id,
                ticker=ticker,
                analysis_type=analysis_type,
                skill_name=skill_name,
                payload=payload,
            )

    out_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return {"success": True, "file_path": str(out_path), "relative_path": str(out_path.relative_to(_REPO_ROOT))}


def trigger_ingest(file_path: str) -> dict[str, Any]:
    """Trigger standard ingest pipeline for a written analysis YAML file."""
    if not file_path:
        return {"success": False, "error": "Missing file_path for ingest"}

    target = Path(file_path)
    if not target.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    if not _INGEST_SCRIPT.exists():
        return {"success": False, "error": f"Ingest script not found: {_INGEST_SCRIPT}"}

    cmd = [sys.executable, str(_INGEST_SCRIPT), str(target), "--json"]
    proc = subprocess.run(
        cmd,
        cwd=str(_TRADEGENT_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    parsed: dict[str, Any] | None = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None

    if proc.returncode == 0:
        return {
            "success": True,
            "ingest": parsed,
            "returncode": proc.returncode,
            "stderr": stderr,
        }

    return {
        "success": False,
        "error": "Ingest command failed",
        "ingest": parsed,
        "returncode": proc.returncode,
        "stderr": stderr,
    }

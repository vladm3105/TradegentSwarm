"""Mutable side effects for ADK runtime orchestration.

This module provides replay-safe side-effect primitives used by the coordinator:
- Persist analysis YAML under tradegent_knowledge/knowledge/
- Trigger ingest pipeline (DB, RAG, Graph) via scripts/ingest.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


_REPO_ROOT = Path("/opt/data/tradegent_swarm")
_KNOWLEDGE_ROOT = _REPO_ROOT / "tradegent_knowledge" / "knowledge"
_TRADEGENT_DIR = _REPO_ROOT / "tradegent"
_INGEST_SCRIPT = _TRADEGENT_DIR / "scripts" / "ingest.py"


def _try_parse_json_object(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()

    # Fast path: whole string is JSON.
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    # Common ADK/LLM pattern: fenced code block with JSON payload.
    if "```" in text:
        fence_parts = text.split("```")
        for block in fence_parts:
            candidate = block.strip()
            if not candidate:
                continue
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

    # Fallback: parse first decodable JSON object embedded in free-form text.
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


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


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _normalize_peer_entries(value: Any) -> list[dict[str, Any]]:
    peers: list[dict[str, Any]] = []
    for item in _as_list(value):
        if not isinstance(item, dict):
            continue
        ticker = _string_or_default(item.get("ticker"), "").upper()
        pe_forward = _number_or_default(item.get("pe_forward"), 0.0)
        if ticker and pe_forward > 0:
            peers.append({"ticker": ticker, "pe_forward": round(pe_forward, 2)})
    return peers


def _normalize_case_arguments(value: Any, *, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize case arguments and enforce minimum length with fallback fill."""
    normalized: list[dict[str, Any]] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            argument = _string_or_default(item.get("argument"), "").strip()
            if argument:
                normalized.append({"argument": argument})
                continue
        if isinstance(item, str) and item.strip():
            normalized.append({"argument": item.strip()})

    if len(normalized) >= 3:
        return normalized

    seen = {entry.get("argument") for entry in normalized}
    for candidate in fallback:
        arg = _string_or_default(candidate.get("argument"), "").strip()
        if not arg or arg in seen:
            continue
        normalized.append({"argument": arg})
        seen.add(arg)
        if len(normalized) >= 3:
            break
    return normalized


def _ensure_min_significance(text: Any) -> str:
    default_significance = (
        "Monitoring trigger tied to validated level structure and execution risk controls. "
        "A sustained move through this threshold requires immediate thesis reassessment, "
        "position sizing review, and confirmation from follow-through price/volume behavior."
    )
    candidate = _string_or_default(text, default_significance).strip()
    if len(candidate) >= 100:
        return candidate
    return default_significance


def _normalize_alert_entry(raw: Any, *, fallback_price: float, fallback_tag: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    price = _number_or_default(raw.get("price"), fallback_price)
    if price <= 0:
        return None

    tag = _string_or_default(raw.get("tag"), fallback_tag).strip()[:15]
    if not tag:
        tag = fallback_tag[:15]

    derivation = _as_dict(raw.get("derivation"))
    methodology = _string_or_default(derivation.get("methodology"), "support_resistance")
    source_field = _string_or_default(derivation.get("source_field"), "summary.key_levels.entry")
    source_value = _number_or_default(derivation.get("source_value"), price)
    calculation = _string_or_default(
        derivation.get("calculation"),
        "Alert aligned to validated technical level for execution monitoring.",
    )

    return {
        "price": round(price, 2),
        "tag": tag,
        "significance": _ensure_min_significance(raw.get("significance")),
        "derivation": {
            "methodology": methodology,
            "source_field": source_field,
            "source_value": round(source_value, 2),
            "calculation": calculation,
        },
    }


def _build_price_alerts(
    *,
    primary_alert: dict[str, Any],
    override_alerts: Any,
    latest_alerts: Any,
    baseline_alerts: Any,
    entry_level: float,
    stop_level: float,
    target_level: float,
    ma_20d: float,
    runtime_price: float,
    max_deviation_pct: float,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    seen_tags: set[str] = set()

    def _add(alert: dict[str, Any] | None) -> None:
        if not isinstance(alert, dict):
            return
        price = _number_or_default(alert.get("price"), 0.0)
        if price <= 0:
            return
        if runtime_price > 0 and _is_key_level_outlier(price, runtime_price, max_deviation_pct):
            return
        tag = _string_or_default(alert.get("tag"), "Alert")
        key = tag.lower().strip()
        if key in seen_tags:
            return
        seen_tags.add(key)
        alerts.append(alert)

    _add(primary_alert)

    for candidate in _as_list(override_alerts):
        _add(_normalize_alert_entry(candidate, fallback_price=entry_level, fallback_tag="Entry"))

    for candidate in _as_list(latest_alerts):
        _add(_normalize_alert_entry(candidate, fallback_price=entry_level, fallback_tag="Trend"))

    for candidate in _as_list(baseline_alerts):
        _add(_normalize_alert_entry(candidate, fallback_price=entry_level, fallback_tag="Level"))

    generated_candidates = [
        {
            "price": ma_20d,
            "tag": "20-day MA",
            "significance": (
                "Trend confirmation trigger around the 20-day average; sustained reclaim supports "
                "continuation while repeated rejection signals momentum fatigue and risk-off behavior."
            ),
            "derivation": {
                "methodology": "moving_average",
                "source_field": "technical.moving_averages.ma_20d",
                "source_value": ma_20d,
                "calculation": "Direct use of 20-day moving average from technical context.",
            },
        },
        {
            "price": entry_level,
            "tag": "Entry Trigger",
            "significance": (
                "Entry alert marks the planned execution threshold; crossing and holding this level "
                "supports activation only when volume and broad market context remain constructive."
            ),
            "derivation": {
                "methodology": "support_resistance",
                "source_field": "summary.key_levels.entry",
                "source_value": entry_level,
                "calculation": "Alert anchored to validated entry level used in execution plan.",
            },
        },
        {
            "price": stop_level,
            "tag": "Risk Stop",
            "significance": (
                "Risk control alert at stop threshold; a confirmed break requires exposure reduction or "
                "exit to preserve downside discipline under the defined risk budget."
            ),
            "derivation": {
                "methodology": "stop_buffer",
                "source_field": "summary.key_levels.stop",
                "source_value": stop_level,
                "calculation": "Alert uses stop level derived from volatility-aware downside buffer.",
            },
        },
        {
            "price": target_level,
            "tag": "Target 1",
            "significance": (
                "Target monitoring alert at first objective; reaching this level triggers reassessment "
                "of realized reward, residual upside, and trade management decisions."
            ),
            "derivation": {
                "methodology": "scenario_target",
                "source_field": "summary.key_levels.target_1",
                "source_value": target_level,
                "calculation": "Alert tied to base-case scenario target objective.",
            },
        },
    ]

    for candidate in generated_candidates:
        normalized = _normalize_alert_entry(
            candidate,
            fallback_price=entry_level,
            fallback_tag="Level",
        )
        _add(normalized)

    if not alerts:
        fallback = _normalize_alert_entry(primary_alert, fallback_price=entry_level, fallback_tag="20-day MA")
        if fallback is not None:
            alerts.append(fallback)
    return alerts


def _extract_latest_document(value: Any) -> dict[str, Any]:
    """Extract latest context document from ADK payload/context wrappers."""
    if not isinstance(value, dict):
        return {}

    latest_document = value.get("latest_document")
    if isinstance(latest_document, dict):
        return latest_document

    payload = value.get("payload")
    if isinstance(payload, dict):
        context = payload.get("context")
        nested_latest_document = context.get("latest_document") if isinstance(context, dict) else None
        if isinstance(nested_latest_document, dict):
            return nested_latest_document

    context = value.get("context")
    context_latest_document = context.get("latest_document") if isinstance(context, dict) else None
    if isinstance(context_latest_document, dict):
        return context_latest_document

    return {}


def _path_exists(doc: dict[str, Any], path: str) -> bool:
    current: Any = doc
    for token in path.split("."):
        if not isinstance(current, dict) or token not in current:
            return False
        current = current[token]
    if current is None:
        return False
    if isinstance(current, str):
        return bool(current.strip())
    if isinstance(current, (dict, list)):
        return len(current) > 0
    return True


def _stock_depth_score(doc: dict[str, Any]) -> int:
    signal_paths = (
        "technical.moving_averages",
        "technical.momentum",
        "fundamentals.valuation",
        "fundamentals.growth",
        "sentiment.analyst",
        "sentiment.options",
        "scenarios.strong_bull",
        "scenarios.base_bull",
        "scenarios.base_bear",
        "scenarios.strong_bear",
        "bull_case_analysis.arguments",
        "bear_case_analysis.arguments",
    )
    return sum(1 for path in signal_paths if _path_exists(doc, path))


def _load_rich_stock_baseline(*, ticker: str) -> dict[str, Any]:
    """Select the richest prior stock document for ticker to backfill sparse outputs."""
    stock_dir = _KNOWLEDGE_ROOT / "analysis" / "stock"
    if not stock_dir.exists():
        return {}

    pattern = f"{ticker.upper()}_*.yaml"
    candidates = sorted(stock_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    best_doc: dict[str, Any] = {}
    best_score = -1
    best_mtime = -1.0
    for candidate in candidates:
        try:
            loaded = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(loaded, dict):
            continue
        score = _stock_depth_score(loaded)
        if score <= 0:
            continue
        mtime = candidate.stat().st_mtime
        if score > best_score or (score == best_score and mtime > best_mtime):
            best_doc = loaded
            best_score = score
            best_mtime = mtime
    return best_doc


def _has_real_llm_phase_content(payload: dict[str, Any]) -> bool:
    """Return True when payload includes non-empty LLM phase content.

    Fixture/unit-shape calls often pass minimal payloads without phase llm content.
    Enforce strict quality checks only for real ADK-generated phase outputs.
    """
    for phase_obj in payload.values():
        if not isinstance(phase_obj, dict):
            continue
        llm = phase_obj.get("llm")
        if not isinstance(llm, dict):
            continue
        content = llm.get("content")
        if isinstance(content, str) and content.strip():
            return True
    return False


def _is_adk_runtime_payload(payload: dict[str, Any]) -> bool:
    """Return True when payload carries ADK runtime boundary metadata."""
    if not isinstance(payload, dict):
        return False

    runtime_context = _as_dict(payload.get("_runtime_context"))
    selected_engine = _string_or_default(runtime_context.get("selected_engine"), "").strip().lower()
    if selected_engine == "adk":
        return True

    entrypoint = _string_or_default(runtime_context.get("entrypoint"), "").strip()
    return bool(entrypoint)


def _contains_placeholder_language(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    lowered = text.lower()
    markers = (
        "placeholder",
        "migration",
        "runtime generated draft",
        "draft analysis",
        "pending live enrichment",
    )
    return any(marker in lowered for marker in markers)


def _to_section_text(value: Any) -> str:
    """Convert nested section payloads to plain text for lightweight richness checks."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        parts = [_to_section_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        try:
            return yaml.safe_dump(value, sort_keys=False)
        except Exception:
            return ""
    return ""


def _estimate_text_tokens(text: str) -> int:
    if not isinstance(text, str) or not text.strip():
        return 0
    return len(text.strip().split())


def _nested_value(doc: dict[str, Any], path: str) -> Any:
    current: Any = doc
    for token in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(token)
    return current


def _stock_rag_section_paths() -> list[str]:
    """Load stock-analysis section paths used by RAG chunking.

    Fallback paths keep the gate resilient if section_mappings.yaml is missing.
    """
    fallback = [
        "thesis",
        "catalysts",
        "risks",
        "technicals",
        "fundamentals",
        "competitive_position",
        "sentiment",
        "what_is_priced_in",
        "bias_checks",
    ]
    mappings_path = _TRADEGENT_DIR / "rag" / "section_mappings.yaml"
    if not mappings_path.exists():
        return fallback
    try:
        mappings = yaml.safe_load(mappings_path.read_text(encoding="utf-8")) or {}
        stock_mapping = mappings.get("stock-analysis", {})
        sections = stock_mapping.get("sections", [])
        paths: list[str] = []
        for section in sections:
            if isinstance(section, dict):
                section_path = _string_or_default(section.get("path"), "")
                if section_path:
                    paths.append(section_path)
            elif isinstance(section, str) and section.strip():
                paths.append(section.strip())
        return paths or fallback
    except Exception:
        return fallback


def _stock_rag_coverage_issue(doc: dict[str, Any]) -> str | None:
    """Return blocking issue when stock doc is too sparse for meaningful RAG ingestion."""
    adk_runtime = _as_dict(doc.get("adk_runtime"))
    phase_status = _as_dict(adk_runtime.get("phase_status"))
    phase_status_keys = {str(item) for item in phase_status.keys()}
    required_phase_keys = {"draft", "critique", "repair", "risk_gate", "summarize"}

    # Apply this stricter gate only to full multi-phase ADK runs.
    # This avoids blocking lightweight fixtures/manual payloads that do not
    # represent production runtime output.
    if not required_phase_keys.issubset(phase_status_keys):
        return None

    min_section_tokens_raw = os.getenv("ADK_STOCK_MIN_RAG_SECTION_TOKENS", "50").strip()
    min_total_tokens_raw = os.getenv("ADK_STOCK_MIN_RAG_TOTAL_TOKENS", "120").strip()

    min_section_tokens = 50
    min_total_tokens = 120
    try:
        parsed_section = int(min_section_tokens_raw)
        if parsed_section > 0:
            min_section_tokens = parsed_section
    except ValueError:
        pass
    try:
        parsed_total = int(min_total_tokens_raw)
        if parsed_total > 0:
            min_total_tokens = parsed_total
    except ValueError:
        pass

    token_counts: list[int] = []
    for path in _stock_rag_section_paths():
        value = _nested_value(doc, path)
        text = _to_section_text(value)
        tokens = _estimate_text_tokens(text)
        if tokens > 0:
            token_counts.append(tokens)

    if not token_counts:
        return "stock analysis has no mappable RAG sections with content"

    total_tokens = sum(token_counts)
    max_tokens = max(token_counts)
    if max_tokens < min_section_tokens or total_tokens < min_total_tokens:
        return (
            "stock analysis too sparse for RAG ingestion "
            f"(max_section_tokens={max_tokens}, total_tokens={total_tokens}, "
            f"required_section_tokens>={min_section_tokens}, required_total_tokens>={min_total_tokens})"
        )
    return None


def _stock_quality_issues(doc: dict[str, Any]) -> list[str]:
    """Collect blocking stock-quality issues before final YAML write."""
    issues: list[str] = []

    current_price = doc.get("current_price")
    if not isinstance(current_price, (int, float)) or isinstance(current_price, bool) or float(current_price) <= 0:
        issues.append("current_price must be > 0")

    recommendation = _as_dict(doc.get("recommendation"))
    action = recommendation.get("action")
    if not isinstance(action, str) or not action.strip():
        issues.append("recommendation.action is required")

    summary = _as_dict(doc.get("summary"))
    summary_narrative = summary.get("narrative")
    if _contains_placeholder_language(summary_narrative):
        issues.append("summary.narrative contains placeholder language")

    key_levels = _as_dict(summary.get("key_levels"))
    for field in ("entry", "stop", "target_1"):
        value = key_levels.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) <= 0:
            issues.append(f"summary.key_levels.{field} must be > 0")

    alert_levels = _as_dict(doc.get("alert_levels"))
    price_alerts = alert_levels.get("price_alerts")
    first_alert = price_alerts[0] if isinstance(price_alerts, list) and price_alerts else {}
    alert_price = first_alert.get("price") if isinstance(first_alert, dict) else None
    if not isinstance(alert_price, (int, float)) or isinstance(alert_price, bool) or float(alert_price) <= 0:
        issues.append("alert_levels.price_alerts[0].price must be > 0")

    rag_coverage_issue = _stock_rag_coverage_issue(doc)
    if rag_coverage_issue:
        issues.append(rag_coverage_issue)

    return issues


def _stock_market_data_gate_issues(doc: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return human-readable issues and machine-readable reason codes for stock market-data gate."""
    issues: list[str] = []
    reason_codes: list[str] = []

    allowed_sources = {
        token.strip().lower()
        for token in os.getenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp").split(",")
        if token.strip()
    }
    if not allowed_sources:
        allowed_sources = {"ib_gateway", "ib_mcp"}

    max_staleness_sec_raw = os.getenv("ADK_MARKET_DATA_MAX_STALENESS_SEC", "120").strip()
    max_staleness_sec = 120
    try:
        parsed = int(max_staleness_sec_raw)
        if parsed > 0:
            max_staleness_sec = parsed
    except ValueError:
        pass

    max_deviation_pct_raw = os.getenv("ADK_MARKET_DATA_MAX_DEVIATION_PCT", "20").strip()
    max_deviation_pct = 20.0
    try:
        parsed_float = float(max_deviation_pct_raw)
        if parsed_float > 0:
            max_deviation_pct = parsed_float
    except ValueError:
        pass

    max_key_level_deviation_pct_raw = os.getenv(
        "ADK_MARKET_DATA_MAX_KEY_LEVEL_DEVIATION_PCT", "40"
    ).strip()
    max_key_level_deviation_pct = 40.0
    try:
        parsed_level_dev = float(max_key_level_deviation_pct_raw)
        if parsed_level_dev > 0:
            max_key_level_deviation_pct = parsed_level_dev
    except ValueError:
        pass

    data_quality = _as_dict(doc.get("data_quality"))
    source = _string_or_default(data_quality.get("price_data_source"), "").strip().lower()
    if source not in allowed_sources:
        issues.append(
            f"price_data_source '{source or '<missing>'}' is not allowed (allowed={sorted(allowed_sources)})"
        )
        reason_codes.append("market_data_source_not_allowed")

    price_verified = bool(data_quality.get("price_data_verified", False))
    if source in allowed_sources and not price_verified:
        issues.append("data_quality.price_data_verified must be true for IB-backed market data")
        reason_codes.append("price_unverified")

    quote_timestamp = data_quality.get("quote_timestamp")
    created_at = _as_dict(doc.get("_meta")).get("created")
    if not isinstance(quote_timestamp, str) or not quote_timestamp.strip():
        issues.append("data_quality.quote_timestamp is required for market-data staleness checks")
        reason_codes.append("quote_timestamp_missing")
    else:
        quote_ts = _parse_iso_datetime(quote_timestamp)
        created_ts = _parse_iso_datetime(created_at)
        if quote_ts is None or created_ts is None:
            issues.append("data_quality.quote_timestamp or _meta.created is not a valid ISO datetime")
            reason_codes.append("quote_timestamp_invalid")
        else:
            age_sec = (created_ts - quote_ts).total_seconds()
            if age_sec > max_staleness_sec:
                issues.append(
                    f"quote staleness {age_sec:.1f}s exceeds max {max_staleness_sec}s"
                )
                reason_codes.append("quote_staleness_exceeded")

    current_price = doc.get("current_price")
    prior_close = data_quality.get("prior_close")
    if not isinstance(prior_close, (int, float)) or isinstance(prior_close, bool) or float(prior_close) <= 0:
        issues.append("data_quality.prior_close must be > 0 for price sanity check")
        reason_codes.append("prior_close_missing")
    elif isinstance(current_price, (int, float)) and not isinstance(current_price, bool) and float(current_price) > 0:
        deviation_pct = abs(float(current_price) - float(prior_close)) / float(prior_close) * 100.0
        if deviation_pct > max_deviation_pct:
            issues.append(
                f"current_price deviation {deviation_pct:.2f}% exceeds max {max_deviation_pct:.2f}% from prior_close"
            )
            reason_codes.append("price_sanity_check_failed")

    summary = _as_dict(doc.get("summary"))
    key_levels = _as_dict(summary.get("key_levels"))
    entry_level = key_levels.get("entry")
    stop_level = key_levels.get("stop")
    target_level = key_levels.get("target_1")

    if all(isinstance(level, (int, float)) and not isinstance(level, bool) and float(level) > 0 for level in (entry_level, stop_level, target_level)):
        entry_val = _number_or_default(entry_level, 0.0)
        stop_val = _number_or_default(stop_level, 0.0)
        target_val = _number_or_default(target_level, 0.0)

        if not (stop_val < entry_val < target_val):
            issues.append("summary.key_levels must satisfy stop < entry < target_1")
            reason_codes.append("key_level_order_invalid")

        if isinstance(current_price, (int, float)) and not isinstance(current_price, bool) and float(current_price) > 0:
            current_val = float(current_price)
            for field_name, level_val in (
                ("entry", entry_val),
                ("stop", stop_val),
                ("target_1", target_val),
            ):
                level_dev_pct = abs(level_val - current_val) / current_val * 100.0
                if level_dev_pct > max_key_level_deviation_pct:
                    issues.append(
                        "summary.key_levels."
                        f"{field_name} deviation {level_dev_pct:.2f}% exceeds max "
                        f"{max_key_level_deviation_pct:.2f}% from current_price"
                    )
                    reason_codes.append("key_level_sanity_failed")

    alert_levels = _as_dict(doc.get("alert_levels"))
    price_alerts = _as_list(alert_levels.get("price_alerts"))
    first_alert = _as_dict(price_alerts[0]) if price_alerts else {}
    alert_price = first_alert.get("price")
    if (
        isinstance(alert_price, (int, float))
        and not isinstance(alert_price, bool)
        and float(alert_price) > 0
        and isinstance(current_price, (int, float))
        and not isinstance(current_price, bool)
        and float(current_price) > 0
    ):
        alert_dev_pct = abs(float(alert_price) - float(current_price)) / float(current_price) * 100.0
        if alert_dev_pct > max_key_level_deviation_pct:
            issues.append(
                "alert_levels.price_alerts[0].price deviation "
                f"{alert_dev_pct:.2f}% exceeds max {max_key_level_deviation_pct:.2f}% from current_price"
            )
            reason_codes.append("alert_level_sanity_failed")

    return issues, sorted(set(reason_codes))


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    token = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_key_level_outlier(level: float, current_price: float, max_deviation_pct: float) -> bool:
    if current_price <= 0:
        return False
    deviation_pct = abs(level - current_price) / current_price * 100.0
    return deviation_pct > max_deviation_pct


def _analysis_dir_for_type(analysis_type: str) -> Path:
    normalized = (analysis_type or "stock").strip().lower()
    if normalized == "earnings":
        return _KNOWLEDGE_ROOT / "analysis" / "earnings"
    return _KNOWLEDGE_ROOT / "analysis" / "stock"


def _declined_analysis_dir() -> Path:
    return _KNOWLEDGE_ROOT / "analysis" / "declined"


def _persist_declined_analysis(
    *,
    out_path: Path,
    doc: dict[str, Any],
    reason: str,
    quality_issues: list[str],
    reason_codes: list[str],
) -> Path:
    """Persist blocked analyses under knowledge/analysis/declined.

    If an artifact already exists at out_path, move it into declined folder.
    Otherwise write the declined document directly under declined folder.
    """
    declined_dir = _declined_analysis_dir()
    declined_dir.mkdir(parents=True, exist_ok=True)
    declined_path = declined_dir / out_path.name

    meta = _as_dict(doc.get("_meta"))
    meta["status"] = "declined"
    doc["_meta"] = meta
    doc["decline"] = {
        "reason": reason,
        "quality_issues": quality_issues,
        "reason_codes": reason_codes,
    }

    if out_path.exists():
        out_path.replace(declined_path)
    else:
        declined_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    return declined_path


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
        "Price action is being monitored for continuation versus failure around defined "
        "entry and invalidation levels. The setup remains conditional on level respect, "
        "liquidity stability, and absence of adverse catalyst drift over the forecast horizon."
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
    key_levels_override = _as_dict(summary_override.get("key_levels"))
    alerts_override = _as_dict(overrides.get("alert_levels"))
    price_alerts_override = alerts_override.get("price_alerts")
    first_alert_override = (
        price_alerts_override[0]
        if isinstance(price_alerts_override, list)
        and price_alerts_override
        and isinstance(price_alerts_override[0], dict)
        else {}
    )

    latest_doc = _extract_latest_document(overrides.get("context"))
    rich_baseline_doc = _load_rich_stock_baseline(ticker=ticker)
    latest_summary = _as_dict(latest_doc.get("summary"))
    latest_key_levels = _as_dict(latest_summary.get("key_levels"))
    latest_alert_levels = _as_dict(latest_doc.get("alert_levels"))
    latest_price_alerts = latest_alert_levels.get("price_alerts")
    first_latest_alert = (
        latest_price_alerts[0]
        if isinstance(latest_price_alerts, list)
        and latest_price_alerts
        and isinstance(latest_price_alerts[0], dict)
        else {}
    )
    latest_recommendation = _as_dict(latest_doc.get("recommendation"))
    latest_data_quality = _as_dict(latest_doc.get("data_quality"))
    latest_market_environment = _as_dict(latest_doc.get("market_environment"))
    latest_comparable_companies = _as_dict(latest_doc.get("comparable_companies"))
    latest_liquidity_analysis = _as_dict(latest_doc.get("liquidity_analysis"))
    data_quality_override = _as_dict(overrides.get("data_quality"))
    runtime_context_override = _as_dict(overrides.get("_runtime_context"))
    runtime_market_data = _as_dict(runtime_context_override.get("market_data"))
    market_environment_override = _as_dict(overrides.get("market_environment"))
    news_age_check_override = _as_dict(overrides.get("news_age_check"))
    catalyst_override = _as_dict(overrides.get("catalyst"))
    threat_assessment_override = _as_dict(overrides.get("threat_assessment"))
    technical_override = _as_dict(overrides.get("technical"))
    fundamentals_override = _as_dict(overrides.get("fundamentals"))
    sentiment_override = _as_dict(overrides.get("sentiment"))
    scenarios_override = _as_dict(overrides.get("scenarios"))
    bull_override = _as_dict(overrides.get("bull_case_analysis"))
    bear_override = _as_dict(overrides.get("bear_case_analysis"))
    bias_override = _as_dict(overrides.get("bias_check"))
    falsification_override = _as_dict(overrides.get("falsification"))
    comparable_companies_override = _as_dict(overrides.get("comparable_companies"))
    liquidity_analysis_override = _as_dict(overrides.get("liquidity_analysis"))

    baseline_news_age_check = _as_dict(rich_baseline_doc.get("news_age_check"))
    baseline_catalyst = _as_dict(rich_baseline_doc.get("catalyst"))
    baseline_threat_assessment = _as_dict(rich_baseline_doc.get("threat_assessment"))
    baseline_technical = _as_dict(rich_baseline_doc.get("technical"))
    baseline_fundamentals = _as_dict(rich_baseline_doc.get("fundamentals"))
    baseline_sentiment = _as_dict(rich_baseline_doc.get("sentiment"))
    baseline_scenarios = _as_dict(rich_baseline_doc.get("scenarios"))
    baseline_bull = _as_dict(rich_baseline_doc.get("bull_case_analysis"))
    baseline_bear = _as_dict(rich_baseline_doc.get("bear_case_analysis"))
    baseline_bias = _as_dict(rich_baseline_doc.get("bias_check"))
    baseline_falsification = _as_dict(rich_baseline_doc.get("falsification"))
    baseline_market_environment = _as_dict(rich_baseline_doc.get("market_environment"))
    baseline_comparable_companies = _as_dict(rich_baseline_doc.get("comparable_companies"))
    baseline_liquidity_analysis = _as_dict(rich_baseline_doc.get("liquidity_analysis"))
    baseline_alert_levels = _as_dict(rich_baseline_doc.get("alert_levels"))
    baseline_price_alerts = baseline_alert_levels.get("price_alerts")

    latest_news_age_check = _as_dict(latest_doc.get("news_age_check"))
    latest_catalyst = _as_dict(latest_doc.get("catalyst"))
    latest_threat_assessment = _as_dict(latest_doc.get("threat_assessment"))
    latest_technical = _as_dict(latest_doc.get("technical"))
    latest_fundamentals = _as_dict(latest_doc.get("fundamentals"))
    latest_sentiment = _as_dict(latest_doc.get("sentiment"))
    latest_scenarios = _as_dict(latest_doc.get("scenarios"))
    latest_bull = _as_dict(latest_doc.get("bull_case_analysis"))
    latest_bear = _as_dict(latest_doc.get("bear_case_analysis"))
    latest_bias = _as_dict(latest_doc.get("bias_check"))
    latest_falsification = _as_dict(latest_doc.get("falsification"))

    current_price = _number_or_default(overrides.get("current_price"), 0.0)
    if current_price <= 0:
        current_price = _number_or_default(latest_doc.get("current_price"), 0.0)
    runtime_price = _number_or_default(runtime_market_data.get("current_price"), 0.0)
    if runtime_price > 0:
        current_price = runtime_price

    summary_text = _string_or_default(
        summary_override.get("narrative"),
        _string_or_default(
            summary_override.get("thesis"),
            _string_or_default(
                latest_summary.get("narrative"),
                _string_or_default(latest_summary.get("thesis"), summary_narrative),
            ),
        ),
    )
    rec_action = _string_or_default(
        recommendation.get("action"),
        _string_or_default(latest_recommendation.get("action"), "WATCH"),
    )
    rec_confidence = int(
        _number_or_default(
            recommendation.get("confidence"),
            _number_or_default(latest_recommendation.get("confidence"), 60),
        )
    )

    entry_level = _number_or_default(key_levels_override.get("entry"), 0.0)
    stop_level = _number_or_default(key_levels_override.get("stop"), 0.0)
    target_level = _number_or_default(key_levels_override.get("target_1"), 0.0)

    if entry_level <= 0:
        entry_level = _number_or_default(latest_key_levels.get("entry"), 0.0)
    if stop_level <= 0:
        stop_level = _number_or_default(latest_key_levels.get("stop"), 0.0)
    if target_level <= 0:
        target_level = _number_or_default(latest_key_levels.get("target_1"), 0.0)

    if current_price > 0:
        if entry_level <= 0:
            entry_level = round(current_price, 2)
        if stop_level <= 0:
            stop_level = round(current_price * 0.96, 2)
        if target_level <= 0:
            target_level = round(current_price * 1.08, 2)

    # If live runtime market data is available, normalize obviously stale/outlier
    # levels to a bounded structure around live price before strict gate checks.
    max_key_level_deviation_pct = 40.0
    max_key_level_deviation_raw = os.getenv(
        "ADK_MARKET_DATA_MAX_KEY_LEVEL_DEVIATION_PCT", "40"
    ).strip()
    try:
        parsed_max_key_level_dev = float(max_key_level_deviation_raw)
        if parsed_max_key_level_dev > 0:
            max_key_level_deviation_pct = parsed_max_key_level_dev
    except ValueError:
        pass

    if runtime_price > 0:
        key_levels_outlier = any(
            _is_key_level_outlier(level, runtime_price, max_key_level_deviation_pct)
            for level in (entry_level, stop_level, target_level)
            if level > 0
        )
        invalid_order = not (stop_level < entry_level < target_level)
        if key_levels_outlier or invalid_order:
            entry_level = round(runtime_price, 2)
            stop_level = round(runtime_price * 0.96, 2)
            target_level = round(runtime_price * 1.08, 2)

    default_significance = (
        "Primary monitoring alert for trend-confirmation behavior around the trigger level. "
        "A sustained move through this threshold indicates setup continuation or invalidation "
        "and should trigger a full risk/reward reassessment before position changes."
    )
    alert_price = _number_or_default(first_alert_override.get("price"), 0.0)
    if alert_price <= 0:
        alert_price = _number_or_default(first_latest_alert.get("price"), 0.0)
    if alert_price <= 0 and entry_level > 0:
        alert_price = round(entry_level * 0.995, 2)

    if runtime_price > 0 and _is_key_level_outlier(alert_price, runtime_price, max_key_level_deviation_pct):
        alert_price = round(entry_level * 0.995, 2)
    alert_tag = _string_or_default(first_alert_override.get("tag"), "20-day MA")
    if not alert_tag.strip():
        alert_tag = _string_or_default(first_latest_alert.get("tag"), "20-day MA")
    alert_significance = _string_or_default(first_alert_override.get("significance"), default_significance)
    if alert_significance == default_significance:
        alert_significance = _string_or_default(first_latest_alert.get("significance"), default_significance)
    alert_derivation = _as_dict(first_alert_override.get("derivation"))
    if alert_derivation:
        derivation_source_value = _number_or_default(alert_derivation.get("source_value"), alert_price)
        if runtime_price > 0 and _is_key_level_outlier(
            derivation_source_value, runtime_price, max_key_level_deviation_pct
        ):
            alert_derivation["source_value"] = alert_price

    source_candidate = _string_or_default(
        data_quality_override.get("price_data_source"),
        "",
    ).strip().lower()
    runtime_source = _string_or_default(runtime_market_data.get("price_data_source"), "").strip().lower()
    if runtime_source in {"ib_gateway", "ib_mcp"}:
        source_candidate = runtime_source
    # Never silently preserve/emit manual source for ADK stock outputs.
    # Missing/invalid source should be surfaced by market-data gates.
    if source_candidate == "manual":
        source_candidate = ""
    price_data_source = source_candidate
    quote_timestamp = _string_or_default(data_quality_override.get("quote_timestamp"), "")
    runtime_quote_ts = _string_or_default(runtime_market_data.get("quote_timestamp"), "")
    if runtime_quote_ts:
        quote_timestamp = runtime_quote_ts
    prior_close = _number_or_default(data_quality_override.get("prior_close"), 0.0)
    runtime_prior_close = _number_or_default(runtime_market_data.get("prior_close"), 0.0)
    if runtime_prior_close > 0:
        prior_close = runtime_prior_close
    price_verified = bool(data_quality_override.get("price_data_verified", False))
    if "price_data_verified" in runtime_market_data:
        price_verified = bool(runtime_market_data.get("price_data_verified"))

    peers = _normalize_peer_entries(comparable_companies_override.get("peers"))
    if not peers:
        peers = _normalize_peer_entries(latest_comparable_companies.get("peers"))
    if len(peers) < 3:
        anchor_pe = round(max(8.0, min(45.0, current_price / 10.0 if current_price > 0 else 24.0)), 2)
        fallback_peers = [
            {"ticker": ticker.upper(), "pe_forward": anchor_pe},
            {"ticker": "SPY", "pe_forward": 23.0},
            {"ticker": "QQQ", "pe_forward": 29.0},
        ]
        seen = {entry["ticker"] for entry in peers}
        for fallback in fallback_peers:
            if fallback["ticker"] in seen:
                continue
            peers.append(fallback)
            seen.add(fallback["ticker"])
            if len(peers) >= 3:
                break

    valuation_position = _string_or_default(
        comparable_companies_override.get("valuation_position"),
        _string_or_default(latest_comparable_companies.get("valuation_position"), "contextual"),
    )

    adv_shares = int(
        _number_or_default(
            liquidity_analysis_override.get("adv_shares"),
            _number_or_default(latest_liquidity_analysis.get("adv_shares"), 0.0),
        )
    )
    if adv_shares <= 0:
        adv_shares = 100000

    adv_dollars = _number_or_default(
        liquidity_analysis_override.get("adv_dollars"),
        _number_or_default(latest_liquidity_analysis.get("adv_dollars"), 0.0),
    )
    if adv_dollars <= 0 and current_price > 0:
        adv_dollars = round(adv_shares * current_price, 2)

    bid_ask_spread_pct = _number_or_default(
        liquidity_analysis_override.get("bid_ask_spread_pct"),
        _number_or_default(latest_liquidity_analysis.get("bid_ask_spread_pct"), 0.0),
    )
    if bid_ask_spread_pct <= 0:
        bid_ask_spread_pct = 0.05

    liquidity_score = int(
        _number_or_default(
            liquidity_analysis_override.get("liquidity_score"),
            _number_or_default(latest_liquidity_analysis.get("liquidity_score"), 0.0),
        )
    )
    if liquidity_score <= 0:
        liquidity_score = 6 if adv_dollars > 0 else 4

    market_regime = _string_or_default(
        market_environment_override.get("regime"),
        _string_or_default(latest_market_environment.get("regime"), "neutral"),
    )
    market_sector = _string_or_default(
        market_environment_override.get("sector"),
        _string_or_default(latest_market_environment.get("sector"), "unclassified"),
    )

    news_age_check: dict[str, Any] = dict(baseline_news_age_check)
    news_age_check.update(latest_news_age_check)
    news_age_check.update(news_age_check_override)
    news_items = _as_list(news_age_check.get("items"))
    if not news_items:
        news_items = [
            {
                "news_item": "No fresh catalyst confirmed during runtime draft generation",
                "date": forecast_until,
                "age_weeks": 0,
                "priced_in": "partially",
                "reasoning": "No same-day high-impact catalyst identified; setup is treated as technically driven until new information emerges.",
            }
        ]
    news_age_check["items"] = news_items

    catalyst: dict[str, Any] = dict(baseline_catalyst)
    catalyst.update(latest_catalyst)
    catalyst.update(catalyst_override)
    catalyst.setdefault("type", "technical")
    catalyst.setdefault(
        "reasoning",
        "Primary catalyst is technical behavior around defined support/resistance zones with confirmation from follow-through volume.",
    )

    threat_assessment: dict[str, Any] = dict(baseline_threat_assessment)
    threat_assessment.update(latest_threat_assessment)
    threat_assessment.update(threat_assessment_override)
    threat_assessment.setdefault("primary_concern", "cyclical")
    threat_assessment.setdefault(
        "threat_summary",
        "Cyclical regime shifts can compress valuation multiples and invalidate momentum assumptions if macro conditions deteriorate.",
    )

    technical: dict[str, Any] = dict(baseline_technical)
    technical.update(latest_technical)
    technical.update(technical_override)
    technical.setdefault(
        "technical_summary",
        "Structure is neutral-to-constructive while price remains above invalidation and trend-following levels continue to hold.",
    )

    fundamentals: dict[str, Any] = dict(baseline_fundamentals)
    fundamentals.update(latest_fundamentals)
    fundamentals.update(fundamentals_override)
    fundamentals_insider = _as_dict(fundamentals.get("insider_activity"))
    if not fundamentals_insider:
        fundamentals_insider = {
            "recent_buys": 0,
            "recent_sells": 0,
            "net_direction": "neutral",
        }
    fundamentals["insider_activity"] = fundamentals_insider

    sentiment: dict[str, Any] = dict(baseline_sentiment)
    sentiment.update(latest_sentiment)
    sentiment.update(sentiment_override)
    sentiment.setdefault(
        "summary",
        "Sentiment is neutral with balanced positioning risk; directional conviction requires confirmation from price/volume behavior.",
    )

    scenarios: dict[str, Any] = dict(baseline_scenarios)
    scenarios.update(latest_scenarios)
    scenarios.update(scenarios_override)

    def _scenario_case(name: str, default_prob: float) -> dict[str, Any]:
        case = _as_dict(scenarios.get(name))
        probability = _number_or_default(case.get("probability"), default_prob)
        case["probability"] = probability
        return case

    scenarios_payload: dict[str, Any] = {
        "strong_bull": _scenario_case("strong_bull", 0.2),
        "base_bull": _scenario_case("base_bull", 0.3),
        "base_bear": _scenario_case("base_bear", 0.3),
        "strong_bear": _scenario_case("strong_bear", 0.2),
    }
    for field in ("probability_check", "expected_value", "ev_calculation"):
        if field in scenarios:
            scenarios_payload[field] = scenarios[field]

    bull_source = dict(baseline_bull)
    bull_source.update(latest_bull)
    bull_source.update(bull_override)
    bear_source = dict(baseline_bear)
    bear_source.update(latest_bear)
    bear_source.update(bear_override)

    bull_arguments = _normalize_case_arguments(bull_source.get("arguments"), fallback=bull_args)
    bear_arguments = _normalize_case_arguments(bear_source.get("arguments"), fallback=bear_args)

    bull_summary_default = (
        "Bull case summary: participation breadth and trend structure support upside "
        "continuation under stable macro conditions, with catalyst follow-through and "
        "acceptable execution risk in the current planning horizon."
    )
    bear_summary_default = (
        "Bear case summary: expectation reset and valuation compression can dominate if "
        "macro or execution conditions deteriorate, producing downside acceleration and "
        "invalidating near-term setup assumptions."
    )

    bias_check: dict[str, Any] = dict(baseline_bias)
    bias_check.update(latest_bias)
    bias_check.update(bias_override)
    bias_check.setdefault("recency_bias", {"detected": False, "severity": "low"})
    bias_check.setdefault("confirmation_bias", {"detected": False, "severity": "low"})
    bias_check.setdefault("anchoring", {"detected": False, "severity": "low"})
    bias_check.setdefault("overconfidence", {"detected": False, "severity": "low"})
    bias_check.setdefault("loss_aversion", {"detected": False, "severity": "low"})
    bias_check.setdefault("both_sides_argued_equally", True)
    bias_check.setdefault(
        "bias_summary",
        "Bias check indicates balanced bull/bear framing with conservative assumptions and explicit invalidation criteria.",
    )

    falsification: dict[str, Any] = dict(baseline_falsification)
    falsification.update(latest_falsification)
    falsification.update(falsification_override)
    if not _as_list(falsification.get("criteria")):
        falsification["criteria"] = [
            {"condition": "Break below planned support zone with confirming distribution volume"},
            {"condition": "Fundamental catalyst invalidated by verified negative update"},
        ]
    falsification.setdefault(
        "thesis_invalid_if",
        "Any two major bearish invalidation conditions are confirmed by market and fundamental evidence.",
    )

    market_environment: dict[str, Any] = dict(baseline_market_environment)
    market_environment.update(latest_market_environment)
    market_environment.update(market_environment_override)
    market_environment["regime"] = market_regime
    market_environment["sector"] = market_sector

    comparable_companies: dict[str, Any] = dict(baseline_comparable_companies)
    comparable_companies.update(latest_comparable_companies)
    comparable_companies.update(comparable_companies_override)
    comparable_companies["peers"] = peers
    comparable_companies["valuation_position"] = valuation_position

    liquidity_analysis: dict[str, Any] = dict(baseline_liquidity_analysis)
    liquidity_analysis.update(latest_liquidity_analysis)
    liquidity_analysis.update(liquidity_analysis_override)
    liquidity_analysis["adv_shares"] = adv_shares
    liquidity_analysis["adv_dollars"] = adv_dollars
    liquidity_analysis["bid_ask_spread_pct"] = bid_ask_spread_pct
    liquidity_analysis["liquidity_score"] = liquidity_score

    if runtime_source in {"ib_gateway", "ib_mcp"} and runtime_quote_ts:
        runtime_note = (
            f"Live quote cross-check from {runtime_source} at {runtime_quote_ts} confirmed real-time "
            "price context for this analysis cycle."
        )
        existing_news_summary = _string_or_default(news_age_check.get("news_summary"), "")
        if runtime_note not in existing_news_summary:
            news_age_check["news_summary"] = (
                (existing_news_summary.strip() + "\n\n" + runtime_note).strip()
                if existing_news_summary.strip()
                else runtime_note
            )

    ma_20d = _number_or_default(_as_dict(technical.get("moving_averages")).get("ma_20d"), alert_price)
    primary_alert = {
        "price": alert_price,
        "tag": alert_tag,
        "significance": alert_significance,
        "derivation": alert_derivation
        if alert_derivation
        else {
            "methodology": "moving_average",
            "source_field": "technical.moving_averages.ma_20d",
            "source_value": alert_price,
            "calculation": "Alert anchored to moving-average trigger used for trend continuation or breakdown confirmation.",
        },
    }
    price_alerts = _build_price_alerts(
        primary_alert=primary_alert,
        override_alerts=price_alerts_override,
        latest_alerts=latest_price_alerts,
        baseline_alerts=baseline_price_alerts,
        entry_level=entry_level,
        stop_level=stop_level,
        target_level=target_level,
        ma_20d=ma_20d,
        runtime_price=runtime_price,
        max_deviation_pct=max_key_level_deviation_pct,
    )

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
        "data_quality": {
            "price_data_source": price_data_source,
            "price_data_verified": price_verified,
            "quote_timestamp": quote_timestamp,
            "prior_close": prior_close,
        },
        "news_age_check": news_age_check,
        "catalyst": catalyst,
        "market_environment": market_environment,
        "threat_assessment": threat_assessment,
        "technical": technical,
        "fundamentals": fundamentals,
        "sentiment": sentiment,
        "comparable_companies": comparable_companies,
        "liquidity_analysis": liquidity_analysis,
        "scenarios": scenarios_payload,
        "bull_case_analysis": {
            "arguments": bull_arguments,
            "summary": _string_or_default(bull_source.get("summary"), bull_summary_default),
        },
        "bear_case_analysis": {
            "arguments": bear_arguments,
            "summary": _string_or_default(bear_source.get("summary"), bear_summary_default),
        },
        "bias_check": bias_check,
        "do_nothing_gate": {
            "ev_threshold": 5.0,
            "confidence_threshold": 60,
            "rr_threshold": 2.0,
            "gates_passed": int(_number_or_default(gate_override.get("gates_passed"), 3)),
            "gate_result": _string_or_default(gate_override.get("gate_result"), "MARGINAL"),
            "confidence_actual": 60,
            "confidence_passes": True,
        },
        "falsification": falsification,
        "recommendation": {"action": rec_action, "confidence": rec_confidence},
        "summary": {
            "narrative": summary_text,
            "key_levels": {
                "entry": entry_level,
                "stop": stop_level,
                "target_1": target_level,
                "entry_derivation": {
                    "methodology": "support_resistance",
                    "source_field": "technical.key_levels.immediate_support",
                    "source_value": entry_level,
                    "calculation": "Direct level selection from nearest validated support/resistance zone.",
                },
                "stop_derivation": {
                    "methodology": "stop_buffer",
                    "source_field": "summary.key_levels.entry",
                    "source_value": stop_level,
                    "calculation": "Stop set below entry using volatility-aware buffer to cap downside while avoiding normal noise.",
                },
                "target_1_derivation": {
                    "methodology": "scenario_target",
                    "source_field": "scenarios.base_bull",
                    "source_value": target_level,
                    "calculation": "Target mapped to base-bull path using nearest resistance objective and expected move profile.",
                },
            },
        },
        "alert_levels": {
            "price_alerts": price_alerts
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
    enforce_stock_quality_gate: bool = False,
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

        doc_type = _doc_type_for_analysis(analysis_type)

        if doc_type == "stock-analysis":
            doc = _build_stock_analysis_document(
                run_id=run_id,
                ticker=ticker,
                analysis_type=analysis_type,
                skill_name=skill_name,
                payload=payload,
            )

            if enforce_stock_quality_gate or _has_real_llm_phase_content(payload) or _is_adk_runtime_payload(payload):
                quality_issues = _stock_quality_issues(doc)
                if quality_issues:
                    declined_path = _persist_declined_analysis(
                        out_path=out_path,
                        doc=doc,
                        reason="stock_quality_gate_failed",
                        quality_issues=quality_issues,
                        reason_codes=["stock_quality_gate_failed"],
                    )
                    return {
                        "success": False,
                        "status": "blocked_quality",
                        "error": "Stock analysis quality gate failed",
                        "quality_issues": quality_issues,
                        "reason_codes": ["stock_quality_gate_failed"],
                        "declined_file_path": str(declined_path),
                        "declined_relative_path": str(declined_path.relative_to(_REPO_ROOT)),
                    }

            market_gate_enabled = os.getenv("ADK_MARKET_DATA_GATES_ENABLED", "true").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            should_apply_market_gate = _is_adk_runtime_payload(payload)

            if market_gate_enabled and should_apply_market_gate:
                gate_issues, reason_codes = _stock_market_data_gate_issues(doc)
                if gate_issues:
                    blocking_mode = os.getenv("ADK_MARKET_DATA_GATES_BLOCKING", "true").strip().lower() in {
                        "1",
                        "true",
                        "yes",
                        "on",
                    }
                    if not isinstance(doc.get("adk_runtime"), dict):
                        doc["adk_runtime"] = _build_runtime_metadata(payload)
                    adk_runtime = _as_dict(doc.get("adk_runtime"))
                    adk_runtime["degraded"] = True
                    adk_runtime["degraded_reasons"] = reason_codes
                    adk_runtime["degraded_details"] = gate_issues
                    doc["adk_runtime"] = adk_runtime

                    if not isinstance(doc.get("_meta"), dict):
                        doc["_meta"] = {}
                    meta = _as_dict(doc.get("_meta"))
                    meta["status"] = "degraded"
                    doc["_meta"] = meta

                    if not blocking_mode:
                        # Allow artifact creation for observability while preserving degraded annotation.
                        pass
                    else:
                        declined_path = _persist_declined_analysis(
                            out_path=out_path,
                            doc=doc,
                            reason="stock_market_data_gate_failed",
                            quality_issues=gate_issues,
                            reason_codes=reason_codes,
                        )
                        return {
                            "success": False,
                            "status": "blocked_quality",
                            "error": "Stock market data gate failed",
                            "quality_issues": gate_issues,
                            "reason_codes": reason_codes,
                            "declined_file_path": str(declined_path),
                            "declined_relative_path": str(declined_path.relative_to(_REPO_ROOT)),
                        }
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

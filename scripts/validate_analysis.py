#!/usr/bin/env python3
"""
Stock Analysis Validator v2.6

Validates stock analysis reports against the v2.6 schema requirements.
Blocks reports missing required professional sections.

Usage:
    python scripts/validate_analysis.py <file.yaml>
    python scripts/validate_analysis.py --all  # Validate all in knowledge/analysis/stock/

Requirements:
    pip install pyyaml jsonschema

Exit codes:
    0 = Valid
    1 = Validation failed
    2 = File/schema error
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Try to import jsonschema, provide helpful error if missing
try:
    from jsonschema import validate, ValidationError, Draft202012Validator
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(2)


# ============================================================
# CONFIGURATION
# ============================================================

MIN_VERSION = 2.6
SCHEMA_PATH = Path(__file__).parent.parent / "tradegent_knowledge/workflows/.github/schemas/stock-analysis.json"

# Required sections for v2.6
REQUIRED_SECTIONS = [
    "_meta",
    "ticker",
    "current_price",
    "data_quality",
    "news_age_check",
    "catalyst",
    "market_environment",
    "threat_assessment",
    "technical",
    "fundamentals",
    "sentiment",
    "comparable_companies",  # NEW in v2.6
    "liquidity_analysis",    # NEW in v2.6
    "scenarios",
    "bull_case_analysis",
    "bear_case_analysis",
    "bias_check",
    "do_nothing_gate",
    "falsification",
    "recommendation",
    "summary",
]

# Minimum content requirements
MIN_ARGUMENTS_BULL_BEAR = 3
MIN_PEERS = 3
MIN_FALSIFICATION_CRITERIA = 2

# Normalized thresholds (v2.6)
GATE_THRESHOLDS = {
    "ev_threshold": 5.0,
    "confidence_threshold": 60,
    "rr_threshold": 2.0,
}

# v2.7 Derivation validation
VALID_DERIVATION_METHODS = {
    "support_resistance",
    "moving_average",
    "pivot_point",
    "round_number",
    "stop_buffer",
    "scenario_target",
    "peer_valuation"
}

MIN_SIGNIFICANCE_LENGTH = 100


# ============================================================
# VALIDATION FUNCTIONS
# ============================================================

class ValidationResult:
    """Structured validation result."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.version: Optional[float] = None
        self.ticker: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def print_report(self):
        """Print validation report."""
        print(f"\n{'=' * 60}")
        print(f"VALIDATION REPORT: {self.file_path}")
        print(f"{'=' * 60}")

        if self.ticker:
            print(f"Ticker: {self.ticker}")
        if self.version:
            print(f"Version: {self.version}")

        if self.is_valid:
            print(f"\n[PASS] Document is valid v2.6 stock analysis")
        else:
            print(f"\n[FAIL] {len(self.errors)} validation error(s)")

        if self.errors:
            print(f"\nERRORS:")
            for i, err in enumerate(self.errors, 1):
                print(f"  {i}. {err}")

        if self.warnings:
            print(f"\nWARNINGS:")
            for i, warn in enumerate(self.warnings, 1):
                print(f"  {i}. {warn}")

        print(f"{'=' * 60}\n")


def load_yaml(file_path: Path) -> dict:
    """Load YAML document."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def load_schema() -> dict:
    """Load JSON schema."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")

    with open(SCHEMA_PATH, 'r') as f:
        return json.load(f)


def validate_version(doc: dict, result: ValidationResult):
    """Check document version."""
    meta = doc.get("_meta", {})
    version = meta.get("version")

    if version is None:
        result.add_error("Missing _meta.version field")
        return

    result.version = float(version)

    if result.version < MIN_VERSION:
        result.add_error(
            f"Version {result.version} is deprecated. "
            f"Minimum required: {MIN_VERSION}"
        )


def validate_required_sections(doc: dict, result: ValidationResult):
    """Check all required sections are present."""
    for section in REQUIRED_SECTIONS:
        if section not in doc:
            result.add_error(f"Missing required section: {section}")
        elif doc[section] is None:
            result.add_error(f"Section '{section}' is null (must have content)")


def validate_comparable_companies(doc: dict, result: ValidationResult):
    """Validate comparable_companies section (NEW v2.6)."""
    comp = doc.get("comparable_companies", {})

    if not comp:
        result.add_error("comparable_companies section is required in v2.6")
        return

    peers = comp.get("peers", [])
    valid_peers = [p for p in peers if p.get("ticker") and p.get("pe_forward")]

    if len(valid_peers) < MIN_PEERS:
        result.add_error(
            f"comparable_companies.peers requires minimum {MIN_PEERS} peers "
            f"with ticker and pe_forward (found {len(valid_peers)})"
        )

    if not comp.get("valuation_position"):
        result.add_error("comparable_companies.valuation_position is required")


def validate_liquidity_analysis(doc: dict, result: ValidationResult):
    """Validate liquidity_analysis section (NEW v2.6)."""
    liq = doc.get("liquidity_analysis", {})

    if not liq:
        result.add_error("liquidity_analysis section is required in v2.6")
        return

    required_fields = ["adv_shares", "adv_dollars", "bid_ask_spread_pct", "liquidity_score"]
    for field in required_fields:
        if field not in liq or liq[field] is None:
            result.add_error(f"liquidity_analysis.{field} is required")

    # Validate liquidity score range
    score = liq.get("liquidity_score", 0)
    if not (1 <= score <= 10):
        result.add_error(f"liquidity_analysis.liquidity_score must be 1-10 (found {score})")


def validate_bull_bear_arguments(doc: dict, result: ValidationResult):
    """Validate bull and bear case have minimum arguments."""
    for case in ["bull_case_analysis", "bear_case_analysis"]:
        section = doc.get(case, {})
        args = section.get("arguments", [])

        # Filter out empty argument placeholders
        valid_args = [a for a in args if a.get("argument") and len(a.get("argument", "")) > 5]

        if len(valid_args) < MIN_ARGUMENTS_BULL_BEAR:
            result.add_error(
                f"{case}.arguments requires minimum {MIN_ARGUMENTS_BULL_BEAR} "
                f"non-empty arguments (found {len(valid_args)})"
            )

        # Check summary length
        summary = section.get("summary", "")
        if len(summary) < 100:
            result.add_error(
                f"{case}.summary must be at least 100 characters (found {len(summary)})"
            )


def validate_do_nothing_gate(doc: dict, result: ValidationResult):
    """Validate Do Nothing gate thresholds (v2.6 normalized)."""
    gate = doc.get("do_nothing_gate", {})

    if not gate:
        result.add_error("do_nothing_gate section is required")
        return

    # Check thresholds match v2.6 standards
    for key, expected in GATE_THRESHOLDS.items():
        actual = gate.get(key)
        if actual != expected:
            result.add_warning(
                f"do_nothing_gate.{key} should be {expected} (found {actual})"
            )

    # Validate gate result consistency
    gates_passed = gate.get("gates_passed", 0)
    gate_result = gate.get("gate_result", "")

    if gates_passed >= 4 and gate_result != "PASS":
        result.add_error(
            f"Gate inconsistency: gates_passed={gates_passed} but gate_result={gate_result}"
        )
    elif gates_passed == 3 and gate_result not in ["MARGINAL", "PASS"]:
        result.add_warning(
            f"Gate result should be MARGINAL or PASS when 3/4 gates pass"
        )
    elif gates_passed < 3 and gate_result == "PASS":
        result.add_error(
            f"Gate inconsistency: gates_passed={gates_passed} but gate_result=PASS"
        )

    # Validate confidence consistency
    confidence_actual = gate.get("confidence_actual", 0)
    confidence_passes = gate.get("confidence_passes", False)

    if confidence_actual >= 60 and not confidence_passes:
        result.add_error(
            f"Confidence inconsistency: {confidence_actual}% >= 60% but confidence_passes=false"
        )
    elif confidence_actual < 60 and confidence_passes:
        result.add_error(
            f"Confidence inconsistency: {confidence_actual}% < 60% but confidence_passes=true"
        )


def validate_falsification(doc: dict, result: ValidationResult):
    """Validate falsification criteria."""
    fals = doc.get("falsification", {})
    criteria = fals.get("criteria", [])

    valid_criteria = [c for c in criteria if c.get("condition")]

    if len(valid_criteria) < MIN_FALSIFICATION_CRITERIA:
        result.add_error(
            f"falsification.criteria requires minimum {MIN_FALSIFICATION_CRITERIA} "
            f"conditions (found {len(valid_criteria)})"
        )

    thesis_invalid = fals.get("thesis_invalid_if", "")
    if len(thesis_invalid) < 20:
        result.add_error(
            f"falsification.thesis_invalid_if must be at least 20 characters"
        )


def validate_bias_check(doc: dict, result: ValidationResult):
    """Validate bias check section."""
    bias = doc.get("bias_check", {})

    required_biases = [
        "recency_bias", "confirmation_bias", "anchoring",
        "overconfidence", "loss_aversion"
    ]

    for bias_type in required_biases:
        if bias_type not in bias:
            result.add_error(f"bias_check.{bias_type} is required")
        else:
            bias_entry = bias.get(bias_type, {})
            if "detected" not in bias_entry or "severity" not in bias_entry:
                result.add_error(
                    f"bias_check.{bias_type} must have 'detected' and 'severity' fields"
                )

    if not bias.get("both_sides_argued_equally"):
        result.add_warning("bias_check.both_sides_argued_equally is false")

    summary = bias.get("bias_summary", "")
    if len(summary) < 50:
        result.add_error(
            f"bias_check.bias_summary must be at least 50 characters"
        )


def validate_insider_activity(doc: dict, result: ValidationResult):
    """Validate enhanced insider activity (v2.6)."""
    fundamentals = doc.get("fundamentals", {})
    insider = fundamentals.get("insider_activity", {})

    required = ["recent_buys", "recent_sells", "net_direction"]
    for field in required:
        if field not in insider:
            result.add_error(f"fundamentals.insider_activity.{field} is required")


def validate_news_age_check(doc: dict, result: ValidationResult):
    """Validate news age check has actual items."""
    news = doc.get("news_age_check", {})
    items = news.get("items", [])

    valid_items = [i for i in items if i.get("news_item") and i.get("priced_in")]

    if len(valid_items) < 1:
        result.add_error(
            "news_age_check.items requires at least 1 news item with priced_in assessment"
        )


def validate_scenarios(doc: dict, result: ValidationResult):
    """Validate scenario probabilities sum to 100%."""
    scenarios = doc.get("scenarios", {})

    prob_sum = 0
    for case in ["strong_bull", "base_bull", "base_bear", "strong_bear"]:
        prob = scenarios.get(case, {}).get("probability", 0)
        # Handle both decimal (0.25) and percentage (25) formats
        if prob > 1:
            prob = prob / 100
        prob_sum += prob

    # Allow for rounding (0.99 to 1.01)
    if not (0.99 <= prob_sum <= 1.01):
        result.add_error(
            f"Scenario probabilities must sum to 100% (found {prob_sum * 100:.1f}%)"
        )


def validate_forecast_validity(doc: dict, result: ValidationResult):
    """Validate forecast_valid_until field in _meta (v2.6 required).

    After forecast_valid_until date, the analysis becomes historical-only
    and should not be used for trading decisions.
    """
    meta = doc.get("_meta", {})
    forecast_date = meta.get("forecast_valid_until")

    if not forecast_date:
        result.add_error(
            "_meta.forecast_valid_until is required (YYYY-MM-DD format). "
            "After this date, analysis is historical only."
        )
        return

    # Validate date format
    try:
        parsed_date = datetime.strptime(str(forecast_date), "%Y-%m-%d")

        # Check if date is in the past (warning, not error - may be reviewing old analysis)
        if parsed_date.date() < datetime.now().date():
            result.add_warning(
                f"forecast_valid_until ({forecast_date}) is in the past. "
                "This analysis is historical-only and should not be used for trading."
            )

    except ValueError:
        result.add_error(
            f"_meta.forecast_valid_until must be YYYY-MM-DD format (found: {forecast_date})"
        )

    # Check forecast_reason is provided (required for v2.6)
    forecast_reason = meta.get("forecast_reason", "")
    if not forecast_reason or len(str(forecast_reason).strip()) < 5:
        result.add_error(
            "_meta.forecast_reason is required. Explain why this expiration date "
            "(e.g., 'Earnings 2026-03-15', 'FDA decision', 'Breakout window 7d')"
        )

    # Optional: check forecast_horizon_days consistency
    horizon_days = meta.get("forecast_horizon_days")
    if horizon_days is not None:
        if not isinstance(horizon_days, int) or horizon_days < 0:
            result.add_warning(
                f"_meta.forecast_horizon_days should be a positive integer (found: {horizon_days})"
            )


def _validate_derivation_fields(derivation: dict, prefix: str, strict: bool, result: ValidationResult):
    """Validate a derivation object structure."""
    methodology = derivation.get("methodology", "")
    if methodology and methodology not in VALID_DERIVATION_METHODS:
        msg = f"{prefix}.derivation.methodology '{methodology}' not valid"
        if strict:
            result.add_error(msg)
        else:
            result.add_warning(msg)

    required_fields = ["source_field", "calculation"]
    for field in required_fields:
        if not derivation.get(field):
            msg = f"{prefix}.derivation.{field} is required"
            if strict:
                result.add_error(msg)
            else:
                result.add_warning(msg)

    # source_value can be 0, so check for None specifically
    if derivation.get("source_value") is None:
        msg = f"{prefix}.derivation.source_value is required"
        if strict:
            result.add_error(msg)
        else:
            result.add_warning(msg)


def validate_alert_levels_derivations(doc: dict, result: ValidationResult):
    """Validate alert_levels.price_alerts have proper derivations (v2.7)."""
    version = result.version or 2.6
    is_v27_plus = version >= 2.7

    alert_levels = doc.get("alert_levels", {})
    price_alerts = alert_levels.get("price_alerts", [])

    for i, alert in enumerate(price_alerts):
        # Skip empty placeholder alerts
        if not alert.get("price") and not alert.get("significance"):
            continue

        prefix = f"alert_levels.price_alerts[{i}]"

        # Check significance length
        significance = alert.get("significance", "")
        if len(str(significance)) < MIN_SIGNIFICANCE_LENGTH:
            msg = f"{prefix}.significance too short ({len(str(significance))} chars, min {MIN_SIGNIFICANCE_LENGTH})"
            if is_v27_plus:
                result.add_error(msg)
            else:
                result.add_warning(msg)

        # Check derivation object exists
        derivation = alert.get("derivation")
        if not derivation:
            msg = f"{prefix} missing derivation object"
            if is_v27_plus:
                result.add_error(msg)
            else:
                result.add_warning(msg)
            continue

        # Validate derivation fields
        _validate_derivation_fields(derivation, prefix, is_v27_plus, result)


def validate_summary_key_levels(doc: dict, result: ValidationResult):
    """Validate summary.key_levels have derivation objects (v2.7)."""
    version = result.version or 2.6
    is_v27_plus = version >= 2.7

    summary = doc.get("summary", {})
    key_levels = summary.get("key_levels", {})

    if not key_levels:
        return  # No key_levels section - other validators handle this

    required_levels = ["entry", "stop", "target_1"]
    optional_levels = ["hard_stop", "target_2"]

    for level in required_levels:
        if level not in key_levels:
            # Required level missing - handled by other validators
            continue

        derivation_key = f"{level}_derivation"
        if derivation_key not in key_levels:
            msg = f"summary.key_levels.{derivation_key} is required for v2.7"
            if is_v27_plus:
                result.add_error(msg)
            else:
                result.add_warning(msg)
        else:
            derivation = key_levels[derivation_key]
            if isinstance(derivation, dict):
                _validate_derivation_fields(
                    derivation,
                    f"summary.key_levels.{derivation_key}",
                    is_v27_plus,
                    result
                )

    for level in optional_levels:
        if level in key_levels and key_levels[level]:
            derivation_key = f"{level}_derivation"
            if derivation_key not in key_levels:
                result.add_warning(
                    f"summary.key_levels.{derivation_key} recommended when {level} is set"
                )


def validate_document(file_path: Path) -> ValidationResult:
    """Main validation function."""
    result = ValidationResult(str(file_path))

    try:
        doc = load_yaml(file_path)
    except yaml.YAMLError as e:
        result.add_error(f"YAML parse error: {e}")
        return result
    except Exception as e:
        result.add_error(f"File read error: {e}")
        return result

    if doc is None:
        result.add_error("Empty document")
        return result

    result.ticker = doc.get("ticker")

    # Run all validators
    validate_version(doc, result)
    validate_required_sections(doc, result)
    validate_comparable_companies(doc, result)
    validate_liquidity_analysis(doc, result)
    validate_bull_bear_arguments(doc, result)
    validate_do_nothing_gate(doc, result)
    validate_falsification(doc, result)
    validate_bias_check(doc, result)
    validate_insider_activity(doc, result)
    validate_news_age_check(doc, result)
    validate_scenarios(doc, result)
    validate_forecast_validity(doc, result)

    # v2.7 derivation requirements
    validate_alert_levels_derivations(doc, result)
    validate_summary_key_levels(doc, result)

    return result


def validate_with_schema(file_path: Path, result: ValidationResult):
    """Optional: Validate against JSON schema."""
    try:
        schema = load_schema()
        doc = load_yaml(file_path)

        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(doc))

        for error in errors[:5]:  # Limit to first 5 schema errors
            result.add_error(f"Schema: {error.message}")

        if len(errors) > 5:
            result.add_error(f"Schema: ... and {len(errors) - 5} more errors")

    except FileNotFoundError:
        result.add_warning(f"Schema file not found, skipping schema validation")
    except Exception as e:
        result.add_warning(f"Schema validation error: {e}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Validate stock analysis reports (v2.6)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/validate_analysis.py path/to/MSFT_20260221T1715.yaml
    python scripts/validate_analysis.py --all
    python scripts/validate_analysis.py --schema path/to/file.yaml
        """
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="YAML file to validate"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all files in knowledge/analysis/stock/"
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Also validate against JSON schema"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors, not full report"
    )

    args = parser.parse_args()

    if args.all:
        # Validate all stock analyses
        base_path = Path(__file__).parent.parent / "tradegent_knowledge/knowledge/analysis/stock"
        files = list(base_path.glob("*.yaml"))

        if not files:
            print(f"No YAML files found in {base_path}")
            sys.exit(2)

        results = []
        for f in sorted(files):
            result = validate_document(f)
            if args.schema:
                validate_with_schema(f, result)
            results.append(result)

            if not args.quiet:
                result.print_report()

        # Summary
        valid_count = sum(1 for r in results if r.is_valid)
        total_count = len(results)

        print(f"\n{'=' * 60}")
        print(f"VALIDATION SUMMARY: {valid_count}/{total_count} files valid")
        print(f"{'=' * 60}")

        if valid_count < total_count:
            print("\nInvalid files:")
            for r in results:
                if not r.is_valid:
                    print(f"  - {r.file_path}: {len(r.errors)} errors")
            sys.exit(1)
        else:
            print("\nAll files pass v2.6 validation.")
            sys.exit(0)

    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}")
            sys.exit(2)

        result = validate_document(file_path)
        if args.schema:
            validate_with_schema(file_path, result)

        result.print_report()

        sys.exit(0 if result.is_valid else 1)

    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()

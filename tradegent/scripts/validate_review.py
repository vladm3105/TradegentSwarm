#!/usr/bin/env python3
"""
Schema validation for post-earnings reviews and report validations.

Usage:
    python scripts/validate_review.py <file.yaml>
    python scripts/validate_review.py --all  # Validate all reviews
    python scripts/validate_review.py --json <file.yaml>  # JSON output
"""

import json
import sys
from pathlib import Path

import yaml


REQUIRED_POST_EARNINGS_FIELDS = [
    "_meta.id",
    "_meta.type",
    "_meta.version",
    "prior_analysis.file",
    "prior_analysis.recommendation",
    "actual_results.eps.actual",
    "actual_results.revenue.actual_b",
    "scenario_outcome.which_occurred",
    "implied_vs_actual.implied_move_pct",
    "implied_vs_actual.actual_move_day1_pct",
    "forecast_vs_actual",  # Must be list with >= 3 elements
    "customer_demand_validation.signal_was_correct",
    "data_source_effectiveness",  # Must be list with >= 3 sources
    "thesis_accuracy.grade",
    "thesis_accuracy.rationale",
    "confidence_calibration.stated_confidence",
    "framework_lesson.primary",
]

REQUIRED_VALIDATION_FIELDS = [
    "_meta.id",
    "_meta.type",
    "_meta.version",
    "prior_analysis.file",
    "prior_analysis.recommendation",
    "new_analysis.file",
    "new_analysis.recommendation",
    "validation_result",
    "validation_reasoning",
    "thesis_comparison",  # Must be list with >= 5 aspects
    "falsification_check.any_triggered",
]

VALID_GRADES = ["A", "B", "C", "D", "F"]
VALID_VALIDATION_RESULTS = ["CONFIRM", "SUPERSEDE", "INVALIDATE"]


def get_nested(data: dict, path: str):
    """Get nested dict value by dot-separated path."""
    keys = path.split(".")
    val = data
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def validate_post_earnings_review(data: dict) -> tuple[bool, list[str]]:
    """Validate a post-earnings review file."""
    errors = []

    # Check required fields
    for field in REQUIRED_POST_EARNINGS_FIELDS:
        val = get_nested(data, field)
        if val is None or val == "":
            errors.append(f"Missing or empty required field: {field}")

    # Check forecast_vs_actual has >= 3 elements
    fva = data.get("forecast_vs_actual", [])
    if not isinstance(fva, list):
        errors.append("forecast_vs_actual must be a list")
    elif len(fva) < 3:
        errors.append(f"forecast_vs_actual must have >= 3 elements, got {len(fva)}")

    # Check data_source_effectiveness has >= 3 sources
    dse = data.get("data_source_effectiveness", [])
    if not isinstance(dse, list):
        errors.append("data_source_effectiveness must be a list")
    elif len(dse) < 3:
        errors.append(f"data_source_effectiveness must have >= 3 elements, got {len(dse)}")

    # Check thesis_accuracy.grade is valid
    grade = get_nested(data, "thesis_accuracy.grade")
    if grade and grade not in VALID_GRADES:
        errors.append(f"Invalid thesis_accuracy.grade: {grade}. Must be one of {VALID_GRADES}")

    # Check scenario_outcome.which_occurred is valid
    scenario = get_nested(data, "scenario_outcome.which_occurred")
    valid_scenarios = ["strong_beat", "modest_beat", "modest_miss", "strong_miss"]
    if scenario and scenario not in valid_scenarios:
        errors.append(f"Invalid scenario_outcome.which_occurred: {scenario}")

    # Check bias_check has at least one entry
    bias_check = data.get("bias_check", {})
    if not isinstance(bias_check, dict) or len(bias_check) == 0:
        errors.append("bias_check must have at least one bias entry")

    return len(errors) == 0, errors


def validate_report_validation(data: dict) -> tuple[bool, list[str]]:
    """Validate a report validation file."""
    errors = []

    # Check required fields
    for field in REQUIRED_VALIDATION_FIELDS:
        val = get_nested(data, field)
        if val is None or val == "":
            errors.append(f"Missing or empty required field: {field}")

    # Check validation_result is valid
    result = data.get("validation_result", "")
    if result not in VALID_VALIDATION_RESULTS:
        errors.append(f"Invalid validation_result: {result}. Must be one of {VALID_VALIDATION_RESULTS}")

    # Check thesis_comparison has >= 5 aspects
    tc = data.get("thesis_comparison", [])
    if not isinstance(tc, list):
        errors.append("thesis_comparison must be a list")
    elif len(tc) < 5:
        errors.append(f"thesis_comparison must have >= 5 aspects, got {len(tc)}")

    # If INVALIDATE, check invalidation_details
    if result == "INVALIDATE":
        inv = data.get("invalidation_details", {})
        if not inv.get("applicable", False):
            errors.append("INVALIDATE requires invalidation_details.applicable = true")
        if not inv.get("reason"):
            errors.append("INVALIDATE requires invalidation_details.reason")
        if not inv.get("alert_generated"):
            # This is a warning, not an error
            pass

    # Check falsification_check has at least one criterion
    fc = get_nested(data, "falsification_check.prior_falsification_criteria")
    if fc is not None and isinstance(fc, list) and len(fc) == 0:
        errors.append("falsification_check.prior_falsification_criteria should have at least one criterion")

    return len(errors) == 0, errors


def validate_review(file_path: str) -> tuple[bool, list[str], str]:
    """
    Validate a review file against schema.

    Returns:
        (is_valid, errors, review_type)
    """
    errors = []

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return False, [f"Invalid YAML: {e}"], "unknown"
    except FileNotFoundError:
        return False, [f"File not found: {file_path}"], "unknown"

    if not isinstance(data, dict):
        return False, ["File content is not a YAML dictionary"], "unknown"

    # Determine review type
    review_type = get_nested(data, "_meta.type") or ""

    if review_type == "post-earnings-review":
        valid, errors = validate_post_earnings_review(data)
    elif review_type == "report-validation":
        valid, errors = validate_report_validation(data)
    else:
        return False, [f"Unknown review type: {review_type}"], review_type

    return valid, errors, review_type


def validate_all_reviews(base_path: str = None) -> dict:
    """Validate all review files in the knowledge base."""
    if base_path is None:
        base_path = Path(__file__).parent.parent.parent / "tradegent_knowledge" / "knowledge" / "reviews"
    else:
        base_path = Path(base_path)

    results = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "files": []
    }

    for review_dir in ["post-earnings", "validation"]:
        dir_path = base_path / review_dir
        if not dir_path.exists():
            continue

        for yaml_file in dir_path.glob("*.yaml"):
            results["total"] += 1
            valid, errors, review_type = validate_review(str(yaml_file))

            file_result = {
                "file": str(yaml_file),
                "type": review_type,
                "valid": valid,
                "errors": errors
            }
            results["files"].append(file_result)

            if valid:
                results["valid"] += 1
            else:
                results["invalid"] += 1

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_review.py <file.yaml>")
        print("       validate_review.py --all")
        print("       validate_review.py --json <file.yaml>")
        sys.exit(1)

    json_output = False
    args = sys.argv[1:]

    if args[0] == "--json":
        json_output = True
        args = args[1:]

    if not args:
        print("Error: No file specified")
        sys.exit(1)

    if args[0] == "--all":
        results = validate_all_reviews()

        if json_output:
            print(json.dumps(results, indent=2))
        else:
            print(f"\nValidation Results:")
            print(f"  Total: {results['total']}")
            print(f"  Valid: {results['valid']}")
            print(f"  Invalid: {results['invalid']}")

            for f in results["files"]:
                status = "VALID" if f["valid"] else "INVALID"
                print(f"\n  {status}: {f['file']}")
                if not f["valid"]:
                    for e in f["errors"]:
                        print(f"    - {e}")

        sys.exit(0 if results["invalid"] == 0 else 1)

    file_path = args[0]
    valid, errors, review_type = validate_review(file_path)

    if json_output:
        result = {
            "file": file_path,
            "type": review_type,
            "valid": valid,
            "errors": errors
        }
        print(json.dumps(result, indent=2))
    else:
        if valid:
            print(f"VALID {file_path} ({review_type})")
        else:
            print(f"INVALID {file_path} ({review_type})")
            print(f"  {len(errors)} errors:")
            for e in errors:
                print(f"    - {e}")

    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()

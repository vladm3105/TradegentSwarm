"""Shared utilities for trading_light_pilot."""

import re
from pathlib import Path

# ISO 8601 date pattern for real document detection (case-insensitive)
REAL_DOC_PATTERN = re.compile(r"\d{8}[Tt]\d{4}")
TEMPLATE_NAMES = {"template", "sample", "example", "test"}


def is_real_document(file_path: str) -> bool:
    """
    Check if file is a real document (not a template).

    Real document criteria:
    1. Filename not in TEMPLATE_NAMES
    2. Contains ISO 8601 date pattern (YYYYMMDDTHHMM)

    Args:
        file_path: Path to the file to check

    Returns:
        True if file appears to be a real document, False otherwise
    """
    filename = Path(file_path).stem.lower()

    # Reject known template names
    if filename in TEMPLATE_NAMES:
        return False

    # Check for template-like names
    for template_name in TEMPLATE_NAMES:
        if template_name in filename:
            return False

    # Require ISO 8601 date pattern
    return bool(REAL_DOC_PATTERN.search(filename))

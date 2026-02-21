"""Shared utilities for trading_light_pilot."""

import re
from pathlib import Path

# ISO 8601 date pattern for real document detection (case-insensitive)
REAL_DOC_PATTERN = re.compile(r"\d{8}[Tt]\d{4}")
# Alternate date patterns for reviews (YYYYMMDD without time)
ALTERNATE_DATE_PATTERN = re.compile(r"\d{8}")
TEMPLATE_NAMES = {"template", "sample", "example", "test"}

# Document types that don't require date patterns
NO_DATE_REQUIRED_DIRS = {"learnings", "strategies", "reference"}


def is_real_document(file_path: str) -> bool:
    """
    Check if file is a real document (not a template).

    Real document criteria:
    1. Filename not in TEMPLATE_NAMES
    2. Either:
       a. Contains ISO 8601 date pattern (YYYYMMDDTHHMM), or
       b. Is in a directory that doesn't require date patterns (learnings/, strategies/), or
       c. Contains alternate date pattern (YYYYMMDD) with _review suffix

    Args:
        file_path: Path to the file to check

    Returns:
        True if file appears to be a real document, False otherwise
    """
    path = Path(file_path)
    filename = path.stem.lower()

    # Reject known template names
    if filename in TEMPLATE_NAMES:
        return False

    # Check for template-like names
    for template_name in TEMPLATE_NAMES:
        if template_name in filename:
            return False

    # Check if in a directory that doesn't require date patterns
    path_parts = set(p.lower() for p in path.parts)
    for no_date_dir in NO_DATE_REQUIRED_DIRS:
        if no_date_dir in path_parts:
            return True

    # Accept files with _review suffix and date pattern (YYYYMMDD)
    if "_review" in filename and ALTERNATE_DATE_PATTERN.search(filename):
        return True

    # Require ISO 8601 date pattern for other documents
    return bool(REAL_DOC_PATTERN.search(filename))
